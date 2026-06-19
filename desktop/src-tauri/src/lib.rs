use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Manager, State};

mod sidecar;
mod tray;
mod updater;

use sidecar::SidecarInfo;

pub struct SidecarState(pub Mutex<Option<SidecarInfo>>);

#[tauri::command]
async fn get_sidecar_info(state: State<'_, SidecarState>) -> Result<SidecarInfo, String> {
    let guard = state.0.lock().map_err(|e| e.to_string())?;
    guard.clone().ok_or_else(|| "sidecar not ready yet".to_string())
}

async fn setup_sidecar(app: AppHandle) {
    match sidecar::spawn_and_wait(&app).await {
        Ok(info) => {
            // Store info in managed state
            if let Some(state) = app.try_state::<SidecarState>() {
                let mut guard = state.0.lock().unwrap();
                *guard = Some(info.clone());
            }
            // Notify the frontend
            app.emit("sidecar-ready", &info).ok();
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
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(SidecarState(Mutex::new(None)))
        .manage(updater::PendingUpdate(Mutex::new(None)))
        .setup(|app| {
            // Tray + minimise-to-tray must be installed before the
            // window opens so the very first close event is captured.
            tray::install(&app.handle())?;

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                setup_sidecar(handle).await;
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_sidecar_info,
            updater::fetch_update,
            updater::install_update,
            tray::hide_to_tray
        ])
        .run(tauri::generate_context!())
        .expect("error while running Devo");
}
