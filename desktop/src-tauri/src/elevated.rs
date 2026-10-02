// ponytail: runs `args` elevated via ShellExecuteExW + lpVerb="runas" and
// waits on the process handle for the exit code. When devo-elevate.exe (a
// tiny helper in the workspace) sits next to the app binary we launch it
// instead and it runs `args` as a child — its embedded manifest
// (assemblyIdentity name="Devo") makes the UAC prompt say "Devo". The
// helper is not bundled in installed builds, so there we elevate `args[0]`
// directly. Linux/macOS keep the existing sidecar sudo flow.
#![cfg(windows)]

use std::path::PathBuf;
use std::time::Duration;
use thiserror::Error;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{CloseHandle, HANDLE};
use windows::Win32::System::Threading::{GetExitCodeProcess, WaitForSingleObject};
use windows::Win32::UI::Shell::{ShellExecuteExW, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW};

const ELEVATION_TIMEOUT_MS: u32 = 120_000;
const HELPER_EXE: &str = "devo-elevate.exe";

#[derive(Debug, Error)]
pub enum ElevationError {
    #[error("no command given to elevate")]
    EmptyCommand,
    #[error("ShellExecuteEx failed: {0}")]
    ShellExecute(String),
    #[error("timed out waiting for elevated command after {0:?}")]
    Timeout(Duration),
    #[error("UAC prompt was cancelled or access denied")]
    Cancelled,
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn find_helper() -> Option<PathBuf> {
    // Same dir as the main app binary (workspace shares target/).
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    let candidate = dir.join(HELPER_EXE);
    if candidate.exists() {
        Some(candidate)
    } else {
        None
    }
}

/// Quotes one argument per the CommandLineToArgvW rules, so paths with
/// spaces (e.g. under `C:\Users\First Last`) survive as one argv entry.
fn quote_arg(arg: &str) -> String {
    if !arg.is_empty() && !arg.contains([' ', '\t', '\n', '"']) {
        return arg.to_string();
    }
    let mut out = String::from('"');
    let mut backslashes = 0;
    for c in arg.chars() {
        match c {
            '\\' => backslashes += 1,
            '"' => {
                out.push_str(&"\\".repeat(backslashes * 2 + 1));
                out.push('"');
                backslashes = 0;
            }
            _ => {
                out.push_str(&"\\".repeat(backslashes));
                out.push(c);
                backslashes = 0;
            }
        }
    }
    out.push_str(&"\\".repeat(backslashes * 2));
    out.push('"');
    out
}

fn join_args(args: &[String]) -> String {
    args.iter().map(|a| quote_arg(a)).collect::<Vec<_>>().join(" ")
}

pub fn run_elevated(args: &[String]) -> Result<u32, ElevationError> {
    if args.is_empty() {
        return Err(ElevationError::EmptyCommand);
    }
    // The helper receives the whole command as argv and spawns it; without
    // the helper, elevate the command's own executable.
    let (program, params) = match find_helper() {
        Some(helper) => (helper.to_string_lossy().into_owned(), join_args(args)),
        None => (args[0].clone(), join_args(&args[1..])),
    };

    let verb = wide("runas");
    let file = wide(&program);
    let params_w = wide(&params);

    let mut info = SHELLEXECUTEINFOW {
        cbSize: std::mem::size_of::<SHELLEXECUTEINFOW>() as u32,
        fMask: SEE_MASK_NOCLOSEPROCESS,
        lpVerb: PCWSTR(verb.as_ptr()),
        lpFile: PCWSTR(file.as_ptr()),
        lpParameters: PCWSTR(params_w.as_ptr()),
        nShow: 0, // SW_HIDE
        ..unsafe { std::mem::zeroed() }
    };

    let result = unsafe { ShellExecuteExW(&mut info) };
    if let Err(e) = result {
        // HRESULT_FROM_WIN32: ERROR_CANCELLED (1223) → 0x800704C7, E_ACCESSDENIED (5) → 0x80070005
        let h = e.code().0 as u32;
        if h == 0x800704C7 || h == 0x80070005 {
            return Err(ElevationError::Cancelled);
        }
        return Err(ElevationError::ShellExecute(e.message().into()));
    }

    let proc: HANDLE = info.hProcess;
    let wait = unsafe { WaitForSingleObject(proc, ELEVATION_TIMEOUT_MS) };
    if wait.0 != 0 {
        // Don't leak the process handle on timeout.
        unsafe { CloseHandle(proc).ok() };
        return Err(ElevationError::Timeout(Duration::from_millis(
            ELEVATION_TIMEOUT_MS as u64,
        )));
    }

    let mut exit_code: u32 = 1;
    let exit_result = unsafe { GetExitCodeProcess(proc, &mut exit_code) };
    // Close the handle regardless of whether GetExitCodeProcess succeeded —
    // the process is gone either way.
    unsafe { CloseHandle(proc).ok() };
    exit_result.map_err(|e| ElevationError::ShellExecute(e.message().into()))?;
    Ok(exit_code)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn helper_exe_name() {
        assert_eq!(HELPER_EXE, "devo-elevate.exe");
    }

    #[test]
    fn quote_arg_leaves_plain_args_alone() {
        assert_eq!(quote_arg("ssm"), "ssm");
        assert_eq!(quote_arg(r"C:\Users\edu\devo.exe"), r"C:\Users\edu\devo.exe");
    }

    #[test]
    fn quote_arg_wraps_spaces_and_empty() {
        assert_eq!(quote_arg(r"C:\First Last\a.exe"), r#""C:\First Last\a.exe""#);
        assert_eq!(quote_arg(""), r#""""#);
    }

    #[test]
    fn quote_arg_escapes_quotes_and_trailing_backslashes() {
        assert_eq!(quote_arg(r#"a"b"#), r#""a\"b""#);
        assert_eq!(quote_arg(r"C:\dir x\"), r#""C:\dir x\\""#);
    }
}
