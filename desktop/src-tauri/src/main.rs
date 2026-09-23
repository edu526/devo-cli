// Prevents additional console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // WebKitGTK >= 2.42 defaults to a DMABUF renderer that needs a GBM EGL
    // display. On NVIDIA proprietary drivers, VMs and some X11 setups that
    // display can't be created and WebKit aborts the whole process with
    // "Could not create GBM EGL display: EGL_NOT_INITIALIZED". Must be set
    // before GTK/WebKit initialise. Respect an explicit user value.
    #[cfg(target_os = "linux")]
    if std::env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }

    devo_lib::run();
}
