// ponytail: launches devo-elevate.exe (a tiny helper in the workspace) with
// ShellExecuteExW + lpVerb="runas". The helper has an embedded manifest
// (assemblyIdentity name="Devo" + requireAdministrator) so the UAC prompt
// says "Devo" instead of "cmd.exe", and the process auto-elevates. The
// helper then runs the .venv devo CLI as a child (inherits the admin
// token) and we wait on the process handle for the exit code.
// Linux/macOS keep the existing sidecar sudo flow.
#![cfg(windows)]

use std::path::PathBuf;
use std::time::Duration;
use thiserror::Error;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{CloseHandle, HANDLE};
use windows::Win32::System::Threading::{
    GetExitCodeProcess, WaitForSingleObject,
};
use windows::Win32::UI::Shell::{ShellExecuteExW, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW};

const ELEVATION_TIMEOUT_MS: u32 = 120_000;
const HELPER_EXE: &str = "devo-elevate.exe";

#[derive(Debug, Error)]
pub enum ElevationError {
    #[error("could not locate {HELPER_EXE} next to devo.exe")]
    HelperNotFound,
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
    // Same dir as the main devo.exe (workspace shares target/).
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    let candidate = dir.join(HELPER_EXE);
    if candidate.exists() {
        Some(candidate)
    } else {
        None
    }
}

pub fn run_elevated(args: &[String]) -> Result<u32, ElevationError> {
    let helper = find_helper().ok_or(ElevationError::HelperNotFound)?;
    // lpParameters is the args string for the helper. The helper receives
    // them as argv (skipping its own path) and forwards to devo.exe.
    let params = args.join(" ");

    let verb = wide("runas");
    let file = wide(&helper.to_string_lossy());
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
        return Err(ElevationError::Timeout(Duration::from_millis(ELEVATION_TIMEOUT_MS as u64)));
    }

    let mut exit_code: u32 = 1;
    unsafe { GetExitCodeProcess(proc, &mut exit_code) }
        .map_err(|e| ElevationError::ShellExecute(e.message().into()))?;
    unsafe { CloseHandle(proc).ok() };
    Ok(exit_code)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn helper_exe_name() {
        assert_eq!(HELPER_EXE, "devo-elevate.exe");
    }
}
