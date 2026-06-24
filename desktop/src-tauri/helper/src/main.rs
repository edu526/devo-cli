// ponytail: this binary exists ONLY to give the UAC consent prompt a proper
// name ("Devo" instead of "Windows Command Processor") and to ensure
// auto-elevation. The manifest is embedded via build.rs and declares
// requireAdministrator. The Tauri main process spawns this with
// ShellExecuteExW + lpVerb="runas", which triggers the UAC prompt. The
// child devo.exe inherits the admin token, so it can write the hosts file.
//
// On non-Windows this is a no-op stub so the workspace still builds.
#![cfg_attr(not(windows), allow(dead_code))]

use std::path::{Path, PathBuf};
use std::process::Command;

#[cfg(windows)]
fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let devo = match find_devo() {
        Some(p) => p,
        None => {
            eprintln!("devo-elevate: could not locate .venv\\Scripts\\devo.exe");
            std::process::exit(2);
        }
    };
    let status = match Command::new(&devo).args(&args).status() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("devo-elevate: failed to spawn devo: {e}");
            std::process::exit(3);
        }
    };
    std::process::exit(status.code().unwrap_or(1));
}

#[cfg(not(windows))]
fn main() {}

fn find_devo() -> Option<PathBuf> {
    let start = std::env::current_dir().ok()?;
    walk_up(&start)
}

fn walk_up(start: &Path) -> Option<PathBuf> {
    let mut dir: Option<&Path> = Some(start);
    while let Some(d) = dir {
        let candidate = d.join(".venv").join("Scripts").join("devo.exe");
        if candidate.exists() {
            return Some(candidate);
        }
        dir = d.parent();
    }
    None
}
