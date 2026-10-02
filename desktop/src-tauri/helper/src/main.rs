// ponytail: this binary exists ONLY to give the UAC consent prompt a proper
// name ("Devo" instead of the elevated program's own name). The manifest is
// embedded via build.rs and declares requireAdministrator. The Tauri main
// process spawns this with ShellExecuteExW + lpVerb="runas", passing the
// full command as argv; we run it as a child, which inherits the admin
// token, and forward its exit code.
//
// On non-Windows this is a no-op stub so the workspace still builds.

#[cfg(windows)]
fn main() {
    let mut args = std::env::args().skip(1);
    let Some(program) = args.next() else {
        eprintln!("devo-elevate: no command given");
        std::process::exit(2);
    };
    let status = match std::process::Command::new(&program).args(args).status() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("devo-elevate: failed to spawn {program}: {e}");
            std::process::exit(3);
        }
    };
    std::process::exit(status.code().unwrap_or(1));
}

#[cfg(not(windows))]
fn main() {}
