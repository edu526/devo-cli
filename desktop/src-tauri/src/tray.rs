// Tray icon: minimise-to-tray with Show / Quit menu and click-to-restore.
//
// Single-instance is enforced by `tauri-plugin-single-instance` so spawning
// the binary twice focuses the existing window instead of opening a new
// one. The tray is built once in `setup()` and lives for the entire
// process lifetime.

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, WindowEvent,
};

const TRAY_ID: &str = "devo-tray";

pub fn install(app: &AppHandle) -> tauri::Result<()> {
    let show_item = MenuItem::with_id(app, "show", "Show Devo", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show_item, &separator, &quit_item])?;

    TrayIconBuilder::with_id(TRAY_ID)
        .tooltip("Devo Desktop")
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                show_main_window(app);
            }
            "quit" => {
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            // Left click toggles the main window visibility.
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        })
        .build(app)?;

    // Override the default close behaviour: clicking the X hides the
    // window instead of exiting the process. The user quits via the
    // tray menu so the sidecar is still accessible from the next
    // "Show" call.
    if let Some(window) = app.get_webview_window("main") {
        let app_clone = app.clone();
        window.on_window_event(move |event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if let Some(w) = app_clone.get_webview_window("main") {
                    let _ = w.hide();
                }
                api.prevent_close();
            }
        });
    }

    Ok(())
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

/// Frontend-facing command: hide the window (same effect as clicking X).
/// Exposed so the UI can offer a "Hide to tray" button in the future.
#[tauri::command]
pub fn hide_to_tray(app: AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}
