// Lifecycle of the sidecar *process*: remembering which one is ours, killing
// it on exit/restart, and cleaning up orphans left by a crashed run.
//
// Killing by image name (`taskkill /IM devo-sidecar.exe`) is wrong whenever
// two Devo instances run at once (e.g. an installed build plus a dev build):
// quitting one used to take down the other one's sidecar. So an instance only
// ever kills the sidecar it spawned (by PID), and at startup it only removes
// sidecars whose parent process no longer exists.

use std::sync::atomic::{AtomicU32, Ordering};

static OWN_SIDECAR_PID: AtomicU32 = AtomicU32::new(0);

/// Remember the PID of the sidecar this instance spawned.
pub(crate) fn register_sidecar_pid(pid: u32) {
    OWN_SIDECAR_PID.store(pid, Ordering::SeqCst);
}

/// Force-kills the sidecar this instance spawned (and its children), so it
/// doesn't outlive the app — otherwise the running `devo-sidecar.exe` stays
/// locked and an installer upgrading the app fails with "Error opening file
/// for writing" on Windows.
pub(crate) fn kill_own_sidecar() {
    #[cfg(windows)]
    {
        let pid = OWN_SIDECAR_PID.swap(0, Ordering::SeqCst);
        if pid == 0 || os_is_shutting_down() {
            return;
        }
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .output();
    }

    #[cfg(not(windows))]
    {
        OWN_SIDECAR_PID.store(0, Ordering::SeqCst);
        let _ = std::process::Command::new("pkill")
            .args(["-f", "devo-sidecar"])
            .output();
    }
}

/// Removes sidecars left behind by a previous run that crashed (their parent
/// app process is gone). Sidecars belonging to another running Devo instance
/// are left alone.
pub(crate) fn kill_orphaned_sidecars() {
    #[cfg(windows)]
    kill_orphans_windows();

    #[cfg(not(windows))]
    let _ = std::process::Command::new("pkill")
        .args(["-f", "devo-sidecar"])
        .output();
}

#[cfg(windows)]
fn os_is_shutting_down() -> bool {
    // During an OS shutdown/restart the session is already tearing down and
    // spawning taskkill.exe fails to load its DLLs (0xc0000142), which pops a
    // modal error that blocks the shutdown. Windows kills every process of
    // the session anyway, so there is nothing to do.
    use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_SHUTTINGDOWN};
    unsafe { GetSystemMetrics(SM_SHUTTINGDOWN) != 0 }
}

/// PIDs of `image` processes that are orphaned. `procs` maps
/// pid -> (parent pid, lowercase image name).
///
/// The PyInstaller one-file bootloader spawns a child with the same image
/// name, so walk up through same-named parents to the topmost one; that
/// "root" is an orphan when *its* parent process no longer exists. A sidecar
/// whose parent is a live process (another running Devo) is never an orphan.
#[cfg_attr(not(windows), allow(dead_code))]
fn find_orphans(procs: &std::collections::HashMap<u32, (u32, String)>, image: &str) -> Vec<u32> {
    let is_orphan = |start: u32| -> bool {
        let mut pid = start;
        loop {
            let Some((ppid, _)) = procs.get(&pid) else {
                return false;
            };
            match procs.get(ppid) {
                Some((_, name)) if name == image => pid = *ppid,
                Some(_) => return false, // parent app is alive
                None => return true,     // parent is gone
            }
        }
    };

    let mut orphans: Vec<u32> = procs
        .iter()
        .filter(|(_, (_, name))| name == image)
        .map(|(pid, _)| *pid)
        .filter(|pid| is_orphan(*pid))
        .collect();
    orphans.sort_unstable();
    orphans
}

#[cfg(windows)]
fn kill_orphans_windows() {
    use std::collections::HashMap;
    use windows::Win32::Foundation::CloseHandle;
    use windows::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W,
        TH32CS_SNAPPROCESS,
    };
    use windows::Win32::System::Threading::{OpenProcess, TerminateProcess, PROCESS_TERMINATE};

    const SIDECAR: &str = "devo-sidecar.exe";

    // pid -> (parent pid, lowercase image name)
    let mut procs: HashMap<u32, (u32, String)> = HashMap::new();
    unsafe {
        let Ok(snap) = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) else {
            return;
        };
        let mut entry = PROCESSENTRY32W {
            dwSize: std::mem::size_of::<PROCESSENTRY32W>() as u32,
            ..Default::default()
        };
        if Process32FirstW(snap, &mut entry).is_ok() {
            loop {
                let len = entry
                    .szExeFile
                    .iter()
                    .position(|&c| c == 0)
                    .unwrap_or(entry.szExeFile.len());
                let name = String::from_utf16_lossy(&entry.szExeFile[..len]).to_lowercase();
                procs.insert(entry.th32ProcessID, (entry.th32ParentProcessID, name));
                if Process32NextW(snap, &mut entry).is_err() {
                    break;
                }
            }
        }
        let _ = CloseHandle(snap);
    }

    for pid in find_orphans(&procs, SIDECAR) {
        unsafe {
            if let Ok(handle) = OpenProcess(PROCESS_TERMINATE, false, pid) {
                let _ = TerminateProcess(handle, 1);
                let _ = CloseHandle(handle);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    const IMG: &str = "devo-sidecar.exe";

    fn procs(entries: &[(u32, u32, &str)]) -> HashMap<u32, (u32, String)> {
        entries
            .iter()
            .map(|(pid, ppid, name)| (*pid, (*ppid, name.to_string())))
            .collect()
    }

    #[test]
    fn sidecar_with_live_app_parent_is_not_an_orphan() {
        // another running Devo instance (pid 10) owns sidecar 20
        let p = procs(&[(10, 1, "devo.exe"), (20, 10, IMG)]);
        assert!(find_orphans(&p, IMG).is_empty());
    }

    #[test]
    fn sidecar_whose_parent_died_is_an_orphan() {
        let p = procs(&[(20, 999, IMG)]);
        assert_eq!(find_orphans(&p, IMG), vec![20]);
    }

    #[test]
    fn onefile_bootloader_pair_is_judged_by_the_root_parent() {
        // live app: bootloader 20 and its same-named child 21 are both safe
        let live = procs(&[(10, 1, "devo.exe"), (20, 10, IMG), (21, 20, IMG)]);
        assert!(find_orphans(&live, IMG).is_empty());

        // dead app: both the bootloader and its child are orphans
        let dead = procs(&[(20, 999, IMG), (21, 20, IMG)]);
        assert_eq!(find_orphans(&dead, IMG), vec![20, 21]);
    }

    #[test]
    fn only_the_matching_image_is_considered() {
        let p = procs(&[(30, 999, "something-else.exe")]);
        assert!(find_orphans(&p, IMG).is_empty());
    }

    #[test]
    fn mixed_instances_only_orphans_are_returned() {
        let p = procs(&[
            (10, 1, "devo-desktop.exe"),
            (20, 10, IMG),  // installed instance, alive
            (50, 777, IMG), // leftover from a crashed run
        ]);
        assert_eq!(find_orphans(&p, IMG), vec![50]);
    }
}
