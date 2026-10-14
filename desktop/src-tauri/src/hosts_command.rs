//! What Devo runs as administrator: `devo ssm hosts …`, to edit the hosts file.
//!
//! The webview only names an action. The command line is built here from the
//! sidecar's own executable (announced on its stdout at boot) and validated
//! values, so a page that runs code it shouldn't (a compromised dependency,
//! an XSS) still can't run anything else with administrator rights.

use std::path::Path;

use crate::sidecar::HostsCli;

#[derive(serde::Deserialize, Debug, PartialEq)]
#[serde(tag = "action", rename_all = "kebab-case")]
pub enum HostsCommand {
    /// Map these databases' hostnames (every forwarded one when empty).
    Setup {
        #[serde(default)]
        db_names: Vec<String>,
    },
    /// Map the missing ones and remove the stale entries.
    Sync,
    /// Remove every Devo entry.
    Clear,
    /// Remove one hostname's entry.
    Remove { hostname: String },
}

/// argv for the elevated `devo ssm hosts` command.
///
/// `unix`: pkexec and osascript start from a clean environment, so the config
/// dir is passed through `env`.
pub fn build_args(command: &HostsCommand, cli: &HostsCli, log_file: &Path, unix: bool) -> Result<Vec<String>, String> {
    let mut args: Vec<String> = Vec::new();
    if unix {
        args.push("/usr/bin/env".into());
        args.push(format!("DEVO_CONFIG_DIR={}", cli.config_dir));
    }
    args.extend([cli.exe.clone(), "-m".into(), "cli_tool.cli".into(), "ssm".into(), "hosts".into()]);
    // the command runs in a hidden window: its outcome goes to the sidecar's log
    args.extend(["--log-file".into(), log_file.to_string_lossy().into_owned()]);
    match command {
        HostsCommand::Setup { db_names } => {
            if let Some(bad) = db_names.iter().find(|n| !is_db_name(n)) {
                return Err(format!("Invalid database name: {bad:?}"));
            }
            // "--": a name starting with "-" is still a name, not an option
            args.extend(["setup".into(), "--".into()]);
            args.extend(db_names.iter().cloned());
        }
        HostsCommand::Sync => args.push("sync".into()),
        HostsCommand::Clear => args.extend(["clear".into(), "--yes".into()]),
        HostsCommand::Remove { hostname } => {
            if !is_hostname(hostname) {
                return Err(format!("Invalid hostname: {hostname:?}"));
            }
            args.extend(["remove-manual".into(), hostname.clone()]);
        }
    }
    Ok(args)
}

/// Same rule as the database form: letters, digits, `_` and `-`.
fn is_db_name(name: &str) -> bool {
    (1..=64).contains(&name.len()) && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
}

/// Same rule as HostsManager: dot-separated labels of letters, digits and inner `-`.
fn is_hostname(host: &str) -> bool {
    !host.is_empty()
        && host.len() <= 253
        && host.split('.').all(|label| {
            (1..=63).contains(&label.len())
                && label.chars().all(|c| c.is_ascii_alphanumeric() || c == '-')
                && !label.starts_with('-')
                && !label.ends_with('-')
        })
}

/// One argument for `sh -c` (macOS `do shell script`): quoted unless it's plain.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
pub fn shell_quote(arg: &str) -> String {
    let plain = !arg.is_empty() && arg.chars().all(|c| c.is_ascii_alphanumeric() || "_-./=:,@+".contains(c));
    if plain {
        arg.to_string()
    } else {
        format!("'{}'", arg.replace('\'', r"'\''"))
    }
}

/// Text for inside an AppleScript string literal.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
pub fn applescript_escape(text: &str) -> String {
    text.replace('\\', r"\\").replace('"', r#"\""#)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn cli() -> HostsCli {
        HostsCli { exe: r"C:\Program Files\Devo\devo-sidecar.exe".into(), config_dir: "/home/u/.devo".into() }
    }

    fn log() -> PathBuf {
        PathBuf::from("/home/u/.devo/sidecar.log")
    }

    fn tail(command: HostsCommand) -> Vec<String> {
        build_args(&command, &cli(), &log(), false).unwrap()[7..].to_vec()
    }

    #[test]
    fn builds_the_command_from_the_sidecar_executable() {
        let args = build_args(&HostsCommand::Sync, &cli(), &log(), false).unwrap();
        assert_eq!(
            args,
            [r"C:\Program Files\Devo\devo-sidecar.exe", "-m", "cli_tool.cli", "ssm", "hosts", "--log-file", "/home/u/.devo/sidecar.log", "sync"]
        );
    }

    #[test]
    fn passes_the_config_dir_through_env_on_unix() {
        let args = build_args(&HostsCommand::Clear, &cli(), &log(), true).unwrap();
        assert_eq!(&args[..2], ["/usr/bin/env", "DEVO_CONFIG_DIR=/home/u/.devo"]);
    }

    #[test]
    fn each_action() {
        assert_eq!(tail(HostsCommand::Clear), ["clear", "--yes"]);
        assert_eq!(tail(HostsCommand::Setup { db_names: vec![] }), ["setup", "--"]);
        assert_eq!(tail(HostsCommand::Setup { db_names: vec!["nemt-qa".into(), "-odd".into()] }), ["setup", "--", "nemt-qa", "-odd"]);
        assert_eq!(tail(HostsCommand::Remove { hostname: "db.abc.us-east-1.rds.amazonaws.com".into() }), [
            "remove-manual",
            "db.abc.us-east-1.rds.amazonaws.com"
        ]);
    }

    #[test]
    fn refuses_values_that_could_be_anything_else() {
        for name in ["", "a b", "a;rm -rf /", "../x", "x\"y", &"x".repeat(65)] {
            let command = HostsCommand::Setup { db_names: vec![name.into()] };
            assert!(build_args(&command, &cli(), &log(), false).is_err(), "db name {name:?}");
        }
        for host in ["", "-rf", "a b", "a/b", "a;b", "x\"y", "a..b", "a.-b"] {
            let command = HostsCommand::Remove { hostname: host.into() };
            assert!(build_args(&command, &cli(), &log(), false).is_err(), "hostname {host:?}");
        }
    }

    #[test]
    fn deserializes_what_the_webview_sends() {
        let command: HostsCommand = serde_json::from_str(r#"{"action":"setup","db_names":["a"]}"#).unwrap();
        assert_eq!(command, HostsCommand::Setup { db_names: vec!["a".into()] });
        let command: HostsCommand = serde_json::from_str(r#"{"action":"remove","hostname":"a.b"}"#).unwrap();
        assert_eq!(command, HostsCommand::Remove { hostname: "a.b".into() });
        assert!(serde_json::from_str::<HostsCommand>(r#"{"action":"run","args":["rm"]}"#).is_err());
    }

    #[test]
    fn shell_quote_leaves_plain_args_and_quotes_the_rest() {
        assert_eq!(shell_quote("/usr/bin/env"), "/usr/bin/env");
        assert_eq!(shell_quote("DEVO_CONFIG_DIR=/Users/u/.devo"), "DEVO_CONFIG_DIR=/Users/u/.devo");
        assert_eq!(shell_quote("/Users/First Last/.devo/sidecar.log"), "'/Users/First Last/.devo/sidecar.log'");
        assert_eq!(shell_quote("it's"), r"'it'\''s'");
        assert_eq!(shell_quote(""), "''");
    }

    #[test]
    fn applescript_escape_handles_quotes_and_backslashes() {
        assert_eq!(applescript_escape(r#"say "hi" \ bye"#), r#"say \"hi\" \\ bye"#);
    }
}
