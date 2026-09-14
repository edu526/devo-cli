use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Manager, State};

mod sidecar;
mod tray;
mod updater;

use sidecar::SidecarInfo;

#[cfg(windows)]
mod elevated;

const SIDECAR_VERSION: &str = env!("SIDECAR_VERSION");

pub struct SidecarState(pub Mutex<Option<SidecarInfo>>);

#[derive(Clone, Debug, serde::Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum BootStatus {
    Loading,
    Ready {
        sidecar_info: SidecarInfo,
        version: String,
        launched_via_autostart: bool,
    },
}

pub struct BootState(pub Mutex<BootStatus>);

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
    #[cfg(target_os = "macos")]
    {
        let cmd = args.join(" ");
        let script = format!(
            "do shell script \"{}\" with administrator privileges",
            cmd.replace("\"", "\\\"")
        );
        let status = std::process::Command::new("osascript")
            .arg("-e")
            .arg(&script)
            .status()
            .map_err(|e| e.to_string())?;

        if status.success() {
            Ok(0)
        } else {
            Err(format!("osascript failed with status: {}", status))
        }
    }
    #[cfg(target_os = "linux")]
    {
        let mut child = std::process::Command::new("pkexec")
            .args(&args)
            .spawn()
            .or_else(|e| {
                if e.kind() == std::io::ErrorKind::NotFound {
                    // Fallback to sudo if pkexec is not installed (e.g. WSL)
                    std::process::Command::new("sudo").args(&args).spawn()
                } else {
                    Err(e)
                }
            })
            .map_err(|e| e.to_string())?;

        let status = child.wait().map_err(|e| e.to_string())?;

        if status.success() {
            Ok(0)
        } else {
            Err(format!("elevation command failed with status: {}", status))
        }
    }
    #[cfg(not(any(windows, target_os = "macos", target_os = "linux")))]
    {
        let _ = args;
        Err("run_elevated: not implemented for this platform".to_string())
    }
}

async fn setup_sidecar(app: AppHandle, launched_via_autostart: bool) {
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
                    version: SIDECAR_VERSION.to_string(),
                    launched_via_autostart,
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
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--autostart"]),
        ))
        .manage(SidecarState(Mutex::new(None)))
        .manage(BootState(Mutex::new(BootStatus::Loading)))
        .manage(updater::PendingUpdate(Mutex::new(None)))
        .setup(|app| {
            // Tray + minimise-to-tray must be installed before the
            // window opens so the very first close event is captured.
            tray::install(app.handle())?;

            let handle = app.handle().clone();
            let launched_via_autostart = std::env::args().any(|a| a == "--autostart");
            tauri::async_runtime::spawn(async move {
                setup_sidecar(handle, launched_via_autostart).await;
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
