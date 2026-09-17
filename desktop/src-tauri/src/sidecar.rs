use std::time::Duration;
use tauri::AppHandle;
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;
use tokio::time::timeout;

#[derive(Clone, serde::Serialize, serde::Deserialize, Debug)]
pub struct SidecarInfo {
    pub port: u16,
    pub token: String,
}

fn parse_ready_line(line: &str) -> Option<SidecarInfo> {
    // Expected: "DEVO_SIDECAR_READY port=N token=X"
    if !line.starts_with("DEVO_SIDECAR_READY") {
        return None;
    }
    let mut port: Option<u16> = None;
    let mut token: Option<String> = None;
    for part in line.split_whitespace().skip(1) {
        if let Some(v) = part.strip_prefix("port=") {
            port = v.parse().ok();
        } else if let Some(v) = part.strip_prefix("token=") {
            token = Some(v.to_string());
        }
    }
    match (port, token) {
        (Some(port), Some(token)) => Some(SidecarInfo { port, token }),
        _ => None,
    }
}

/// macOS apps launched from Finder/Dock/Spotlight (LaunchServices) get a
/// minimal PATH (`/usr/bin:/bin:/usr/sbin:/sbin`) that skips Homebrew
/// (`/opt/homebrew/bin`, `/usr/local/bin`) and anything a shell rc file
/// puts on PATH (pyenv, nvm, asdf, ...). That PATH is inherited by the
/// sidecar and every subprocess it spawns (`aws`, `session-manager-plugin`),
/// so `aws sso login` etc. fail with FileNotFoundError even though the CLI
/// is installed. Resolve the user's real PATH via their login shell and
/// merge it in before spawning. No-op on Windows/Linux, where this doesn't
/// happen.
#[cfg(target_os = "macos")]
async fn resolve_login_shell_path() -> Option<String> {
    // Bracket the PATH with markers so noise from interactive-shell startup
    // (MOTD, oh-my-zsh banners, nvm/asdf output) can't be mistaken for it.
    const START: &str = "__DEVO_PATH_START__";
    const END: &str = "__DEVO_PATH_END__";

    let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_string());
    let script = format!("echo \"{START}$PATH{END}\"");

    // -i -l sources the same rc/profile files a real terminal would
    // (.zprofile, .zshrc, ...), which is where Homebrew's `shellenv` and
    // version-manager shims usually get added to PATH.
    let output = timeout(
        Duration::from_secs(5),
        tokio::process::Command::new(&shell)
            .args(["-ilc", script.as_str()])
            .output(),
    )
    .await
    .ok()?
    .ok()?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let start = stdout.find(START)? + START.len();
    let end = stdout.find(END)?;
    if end <= start {
        return None;
    }
    let path = stdout[start..end].trim();
    if path.is_empty() {
        None
    } else {
        Some(path.to_string())
    }
}

/// Covers the two dominant `aws` CLI install methods on macOS (Homebrew and
/// the official .pkg installer) unconditionally, so the fix doesn't depend
/// entirely on login-shell resolution succeeding — that resolution turned
/// out to silently produce no override for at least one real user, which
/// left PATH untouched. This is the floor; `resolve_login_shell_path`
/// layers on top of it for anything more exotic (pyenv, nvm, custom dirs).
#[cfg(target_os = "macos")]
fn known_macos_path_dirs() -> Vec<String> {
    let mut dirs = vec![
        "/opt/homebrew/bin".to_string(),
        "/opt/homebrew/sbin".to_string(),
        "/usr/local/bin".to_string(),
        "/usr/local/sbin".to_string(),
    ];
    if let Ok(home) = std::env::var("HOME") {
        dirs.push(format!("{home}/.local/bin"));
    }
    dirs
}

#[cfg(target_os = "macos")]
fn merge_path_entries(parts: &[&str]) -> String {
    let mut seen = std::collections::HashSet::new();
    let mut merged = Vec::new();
    // Earlier parts win priority over later ones.
    for part in parts {
        for entry in part.split(':') {
            if !entry.is_empty() && seen.insert(entry) {
                merged.push(entry);
            }
        }
    }
    merged.join(":")
}

/// Appends one line to sidecar.log in the same format the sidecar's own
/// output uses, so the outcome of the PATH fix is visible in the Logs page
/// without needing terminal access to the user's Mac.
#[cfg(target_os = "macos")]
fn append_log_line(log_path: &std::path::Path, msg: &str) {
    use std::fs::OpenOptions;
    use std::io::Write;
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
        let _ = writeln!(file, "{now} WARN [macos-path-fix] {msg}");
    }
}

/// PATH override to apply to the spawned sidecar's environment, or empty
/// if none is needed (non-macOS, where LaunchServices doesn't truncate PATH).
async fn sidecar_env_overrides(log_path: &std::path::Path) -> Vec<(String, String)> {
    #[cfg(target_os = "macos")]
    {
        let current = std::env::var("PATH").unwrap_or_default();
        let shell_path = resolve_login_shell_path().await;
        let known = known_macos_path_dirs().join(":");

        let note = match &shell_path {
            Some(p) => format!(
                "resolved login-shell PATH ({} entries); also adding known Homebrew/local-bin dirs",
                p.split(':').filter(|s| !s.is_empty()).count()
            ),
            None => "login-shell PATH resolution failed or timed out; falling back to known Homebrew/local-bin dirs only".to_string(),
        };
        append_log_line(log_path, &note);

        let merged = match &shell_path {
            Some(p) => merge_path_entries(&[p.as_str(), known.as_str(), current.as_str()]),
            None => merge_path_entries(&[known.as_str(), current.as_str()]),
        };
        vec![("PATH".to_string(), merged)]
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = log_path;
        Vec::new()
    }
}

pub async fn spawn_and_wait(app: &AppHandle) -> Result<SidecarInfo, String> {
    use tauri::Manager;

    // Ponytail log rotation: keep log under 5MB by rotating on startup
    let log_path = app.path().home_dir()
        .map(|h| h.join(".devo").join("sidecar.log"))
        .unwrap_or_else(|_| std::path::PathBuf::from(".devo/sidecar.log"));

    if let Ok(meta) = std::fs::metadata(&log_path) {
        if meta.len() > 5 * 1024 * 1024 {
            let mut old_log = log_path.clone();
            old_log.set_extension("old.log");
            let _ = std::fs::rename(&log_path, &old_log);
        }
    }

    let env_overrides = sidecar_env_overrides(&log_path).await;

    let (mut rx, child) = {
        #[cfg(debug_assertions)]
        {
            // Dev: the `scripts/build_sidecar_placeholder.sh` wrapper
            // sits at `binaries/devo-sidecar-<triple>`. Tauri resolves
            // it via the `externalBin` config and exec's the script.
            app.shell()
                .sidecar("devo-sidecar")
                .map_err(|e| format!("sidecar placeholder not found: {e}"))?
                .args(["--port", "0", "--log-level", "info"])
                .envs(env_overrides)
                .spawn()
                .map_err(|e| format!("failed to spawn sidecar: {e}"))?
        }
        #[cfg(not(debug_assertions))]
        {
            // Release: bundled sidecar binary (built by PyInstaller, named devo-sidecar)
            app.shell()
                .sidecar("devo-sidecar")
                .map_err(|e| format!("sidecar not found: {e}"))?
                .args(["--port", "0"])
                .envs(env_overrides)
                .spawn()
                .map_err(|e| format!("failed to spawn sidecar: {e}"))?
        }
    };

    // Keep the child in an Option so we can guarantee it gets killed on
    // every error path below (timeout, sidecar error, terminated early,
    // stdout-closed-before-ready). Without this, a failing boot would
    // leave a zombie sidecar holding port 8000 and the next retry would
    // hit EADDRINUSE.
    let mut child = Some(child);

    let deadline = Duration::from_secs(30);
    let result = timeout(deadline, async {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes);
                    let line = line.trim();
                    if let Some(info) = parse_ready_line(line) {
                        return Ok(info);
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    // Log stderr but do not fail on it
                    let msg = String::from_utf8_lossy(&bytes);
                    eprintln!("[sidecar stderr] {msg}");
                }
                CommandEvent::Error(e) => {
                    return Err(format!("sidecar error: {e}"));
                }
                CommandEvent::Terminated(status) => {
                    return Err(format!(
                        "sidecar exited before ready (code={:?})",
                        status.code
                    ));
                }
                _ => {}
            }
        }
        Err("sidecar stdout closed before DEVO_SIDECAR_READY".to_string())
    })
    .await;

    match result {
        Ok(Ok(info)) => {
            // Once ready, spawn a background task to consume the rest of stdout/stderr
            // so we don't block the pipe and we capture unhandled Python crashes.
            use tauri::Manager;
            use std::fs::OpenOptions;
            use std::io::Write;

            let app_handle = app.clone();
            // Hand the child over to the keepalive task — drops here would
            // kill the sidecar. The error arms below explicitly kill it.
            let keepalive_child = child.take().expect("child present on success path");
            tauri::async_runtime::spawn(async move {
                // Keep `child` alive for the lifetime of this task
                let mut _keepalive_child = keepalive_child;

                // log_path was already computed in spawn_and_wait, but we recompute it
                // here for the background thread to avoid moving it if not needed.
                let log_path = app_handle.path().home_dir()
                    .map(|h| h.join(".devo").join("sidecar.log"))
                    .unwrap_or_else(|_| std::path::PathBuf::from(".devo/sidecar.log"));

                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
                            let msg = String::from_utf8_lossy(&bytes);
                            let msg_trimmed = msg.trim();
                            if msg_trimmed.is_empty() {
                                continue;
                            }

                            // Write to the UI console for local debugging
                            eprintln!("[sidecar] {}", msg_trimmed);

                            // Append to sidecar.log so the LogsPage UI can pick it up
                            if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&log_path) {
                                let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
                                for line in msg_trimmed.lines() {
                                    let line = line.trim_end(); // only trim end to keep indentation
                                    if line.is_empty() {
                                        continue;
                                    }
                                    let has_timestamp = line.len() > 10 && line.chars().nth(4) == Some('-') && line.chars().nth(7) == Some('-');
                                    if has_timestamp {
                                        let _ = writeln!(file, "{}", line);
                                    } else if line.starts_with("INFO:") {
                                        let _ = writeln!(file, "{} INFO [console] {}", now, line);
                                    } else if line.starts_with("WARNING:") {
                                        let _ = writeln!(file, "{} WARN [console] {}", now, line);
                                    } else if line.starts_with("ERROR:") {
                                        let _ = writeln!(file, "{} ERROR [console] {}", now, line);
                                    } else {
                                        // Raw line (e.g. stacktrace or standard print), write as is
                                        // so the UI can group it with the previous log entry.
                                        let _ = writeln!(file, "{}", line);
                                    }
                                }
                            }
                        }
                        CommandEvent::Terminated(_) => {
                            eprintln!("[sidecar] Terminated");
                            break;
                        }
                        CommandEvent::Error(e) => {
                            eprintln!("[sidecar] Error: {}", e);
                            break;
                        }
                        _ => {}
                    }
                }

                // Explicitly kill if the loop breaks
                let _ = _keepalive_child.kill();
            });

            Ok(info)
        },
        Ok(Err(e)) => {
            if let Some(c) = child.take() {
                let _ = c.kill();
            }
            Err(e)
        }
        Err(_) => {
            if let Some(c) = child.take() {
                let _ = c.kill();
            }
            Err("timed out waiting for DEVO_SIDECAR_READY (30s)".to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_valid_ready_line() {
        let info = parse_ready_line("DEVO_SIDECAR_READY port=54321 token=abc123").unwrap();
        assert_eq!(info.port, 54321);
        assert_eq!(info.token, "abc123");
    }

    #[test]
    fn parse_ignores_unrelated_lines() {
        assert!(parse_ready_line("INFO:     Started server").is_none());
        assert!(parse_ready_line("").is_none());
    }

    #[test]
    fn parse_missing_token_returns_none() {
        assert!(parse_ready_line("DEVO_SIDECAR_READY port=8000").is_none());
    }

    #[test]
    fn parse_missing_port_returns_none() {
        assert!(parse_ready_line("DEVO_SIDECAR_READY token=abc").is_none());
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn merge_path_prioritizes_earlier_parts_and_dedupes() {
        let merged = merge_path_entries(&[
            "/opt/homebrew/bin:/usr/local/bin:/usr/bin",
            "/usr/bin:/bin:/opt/homebrew/bin",
        ]);
        assert_eq!(merged, "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn merge_path_ignores_empty_segments() {
        let merged = merge_path_entries(&["/opt/homebrew/bin:", "/usr/bin::/bin"]);
        assert_eq!(merged, "/opt/homebrew/bin:/usr/bin:/bin");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn known_dirs_cover_homebrew_and_local_bin() {
        let dirs = known_macos_path_dirs();
        assert!(dirs.contains(&"/opt/homebrew/bin".to_string()));
        assert!(dirs.contains(&"/usr/local/bin".to_string()));
    }
}
