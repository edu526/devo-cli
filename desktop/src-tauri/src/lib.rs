use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Manager, State};

mod sidecar;
mod tray;
mod updater;

use sidecar::SidecarInfo;

#[cfg(windows)]
mod elevated;

pub const MIN_DEVO_CLI_VERSION: &str = env!("DEVO_CLI_MIN_VERSION");
const DEVO_CLI_VERSION: &str = env!("DEVO_CLI_VERSION");

pub struct SidecarState(pub Mutex<Option<SidecarInfo>>);

#[derive(Clone, Debug, serde::Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum BootStatus {
    Loading,
    Ready {
        sidecar_info: SidecarInfo,
        version: String,
    },
    VersionError {
        required: String,
        found: String,
    },
}

pub struct BootState(pub Mutex<BootStatus>);

fn parse_version(v: &str) -> Option<(u32, u32, u32)> {
    let cleaned = v.split('+').next()?.split(".dev").next()?;
    let mut parts = cleaned.split('.');
    Some((
        parts.next()?.parse().ok()?,
        parts.next()?.parse().ok()?,
        parts.next()?.parse().ok()?,
    ))
}

fn is_at_least(version: &str, min: &str) -> bool {
    if version.contains(".dev") {
        return true;
    }
    matches!((parse_version(version), parse_version(min)), (Some(v), Some(m)) if v >= m)
}

#[tauri::command]
async fn get_sidecar_info(state: State<'_, SidecarState>) -> Result<SidecarInfo, String> {
    let guard = state.0.lock().map_err(|e| e.to_string())?;
    guard
        .clone()
        .ok_or_else(|| "sidecar not ready yet".to_string())
}

#[tauri::command]
fn get_boot_status(state: State<'_, BootState>) -> BootStatus {
    state.0.lock().unwrap().clone()
}

#[tauri::command]
fn run_elevated(args: Vec<String>) -> Result<u32, String> {
    #[cfg(windows)]
    {
        elevated::run_elevated(&args).map_err(|e| e.to_string())
    }
    #[cfg(not(windows))]
    {
        let _ = args;
        Err("run_elevated: only implemented on Windows".to_string())
    }
}

async fn setup_sidecar(app: AppHandle) {
    // Kill any orphaned sidecars from previous crashes before spawning a new one
    #[cfg(windows)]
    let _ = std::process::Command::new("taskkill")
        .args(["/F", "/IM", "devo-sidecar*.exe", "/T"])
        .output();

    #[cfg(not(windows))]
    let _ = std::process::Command::new("pkill")
        .args(["-f", "devo-sidecar"])
        .output();

    match sidecar::spawn_and_wait(&app).await {
        Ok(info) => {
            if let Some(state) = app.try_state::<SidecarState>() {
                let mut guard = state.0.lock().unwrap();
                *guard = Some(info.clone());
            }
            if let Some(boot) = app.try_state::<BootState>() {
                let mut guard = boot.0.lock().unwrap();
                *guard = BootStatus::Ready {
                    sidecar_info: info,
                    version: DEVO_CLI_VERSION.to_string(),
                };
            }
            app.emit("sidecar-ready", ()).ok();
        }
        Err(e) => {
            eprintln!("[devo] sidecar failed to start: {e}");
            app.emit("sidecar-error", e).ok();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(SidecarState(Mutex::new(None)))
        .manage(BootState(Mutex::new(BootStatus::Loading)))
        .manage(updater::PendingUpdate(Mutex::new(None)))
        .setup(|app| {
            // Tray + minimise-to-tray must be installed before the
            // window opens so the very first close event is captured.
            tray::install(app.handle())?;

            let found = DEVO_CLI_VERSION;
            if !is_at_least(found, MIN_DEVO_CLI_VERSION) {
                eprintln!(
                    "[devo] CLI {found} below minimum {}; blocking sidecar spawn",
                    MIN_DEVO_CLI_VERSION
                );
                let state = app.state::<BootState>();
                *state.0.lock().unwrap() = BootStatus::VersionError {
                    required: MIN_DEVO_CLI_VERSION.to_string(),
                    found: found.to_string(),
                };
                return Ok(());
            }

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                setup_sidecar(handle).await;
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_sidecar_info,
            get_boot_status,
            updater::fetch_update,
            updater::install_update,
            tray::hide_to_tray,
            run_elevated
        ])
        .run(tauri::generate_context!())
        .expect("error while running Devo");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_at_least() {
        assert!(is_at_least("3.10.0", "3.10.0"));
        assert!(is_at_least("3.10.1", "3.10.0"));
        assert!(is_at_least("3.11.0", "3.10.0"));
        assert!(is_at_least("4.0.0", "3.10.0"));
        assert!(is_at_least("3.10.0+abc", "3.10.0"));
        assert!(is_at_least("3.10.0.dev5", "3.10.0"));
        assert!(!is_at_least("3.9.9", "3.10.0"));
        assert!(!is_at_least("3.9.0", "3.10.0"));
        assert!(!is_at_least("2.99.99", "3.10.0"));
        assert!(!is_at_least("garbage", "3.10.0"));
        assert!(!is_at_least("3.10.0", "garbage"));
    }

    #[test]
    fn version_parse_strips_suffixes() {
        assert_eq!(parse_version("3.10.0+abc123"), Some((3, 10, 0)));
        assert_eq!(parse_version("3.10.0.dev5"), Some((3, 10, 0)));
        assert_eq!(parse_version("1.2.3"), Some((1, 2, 3)));
        assert_eq!(parse_version("v1.0"), None);
    }

    #[test]
    fn dev_versions_bypass_check() {
        assert!(is_at_least("3.9.1.dev11+ge2096b2e6.d20260619", "3.10.0"));
        assert!(is_at_least("0.0.1.dev1", "3.10.0"));
        assert!(is_at_least("2.0.0.dev0", "99.0.0"));
    }
}
