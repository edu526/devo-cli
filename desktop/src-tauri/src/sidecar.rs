use std::time::Duration;
use tauri::AppHandle;
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;
use tokio::time::timeout;

#[derive(Clone, serde::Serialize, serde::Deserialize, Debug)]
pub struct SidecarInfo {
    pub port: u16,
    pub token: String,
}

fn parse_ready_line(line: &str) -> Option<SidecarInfo> {
    // Expected: "DEVO_SIDECAR_READY port=N token=X"
    if !line.starts_with("DEVO_SIDECAR_READY") {
        return None;
    }
    let mut port: Option<u16> = None;
    let mut token: Option<String> = None;
    for part in line.split_whitespace().skip(1) {
        if let Some(v) = part.strip_prefix("port=") {
            port = v.parse().ok();
        } else if let Some(v) = part.strip_prefix("token=") {
            token = Some(v.to_string());
        }
    }
    match (port, token) {
        (Some(port), Some(token)) => Some(SidecarInfo { port, token }),
        _ => None,
    }
}

pub async fn spawn_and_wait(app: &AppHandle) -> Result<SidecarInfo, String> {
    use tauri::Manager;

    // Ponytail log rotation: keep log under 5MB by rotating on startup
    let log_path = app.path().home_dir()
        .map(|h| h.join(".devo").join("sidecar.log"))
        .unwrap_or_else(|_| std::path::PathBuf::from(".devo/sidecar.log"));

    if let Ok(meta) = std::fs::metadata(&log_path) {
        if meta.len() > 5 * 1024 * 1024 {
            let mut old_log = log_path.clone();
            old_log.set_extension("old.log");
            let _ = std::fs::rename(&log_path, &old_log);
        }
    }

    let (mut rx, child) = {
        #[cfg(debug_assertions)]
        {
            // Dev: the `scripts/build_sidecar_placeholder.sh` wrapper
            // sits at `binaries/devo-sidecar-<triple>`. Tauri resolves
            // it via the `externalBin` config and exec's the script.
            app.shell()
                .sidecar("devo-sidecar")
                .map_err(|e| format!("sidecar placeholder not found: {e}"))?
                .args(["--port", "0", "--log-level", "info"])
                .spawn()
                .map_err(|e| format!("failed to spawn sidecar: {e}"))?
        }
        #[cfg(not(debug_assertions))]
        {
            // Release: bundled sidecar binary (built by PyInstaller, named devo-sidecar)
            app.shell()
                .sidecar("devo-sidecar")
                .map_err(|e| format!("sidecar not found: {e}"))?
                .args(["--port", "0"])
                .spawn()
                .map_err(|e| format!("failed to spawn sidecar: {e}"))?
        }
    };

    let deadline = Duration::from_secs(30);
    let result = timeout(deadline, async {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes);
                    let line = line.trim();
                    if let Some(info) = parse_ready_line(line) {
                        return Ok(info);
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    // Log stderr but do not fail on it
                    let msg = String::from_utf8_lossy(&bytes);
                    eprintln!("[sidecar stderr] {msg}");
                }
                CommandEvent::Error(e) => {
                    return Err(format!("sidecar error: {e}"));
                }
                CommandEvent::Terminated(status) => {
                    return Err(format!(
                        "sidecar exited before ready (code={:?})",
                        status.code
                    ));
                }
                _ => {}
            }
        }
        Err("sidecar stdout closed before DEVO_SIDECAR_READY".to_string())
    })
    .await;

    match result {
        Ok(Ok(info)) => {
            // Once ready, spawn a background task to consume the rest of stdout/stderr
            // so we don't block the pipe and we capture unhandled Python crashes.
            use tauri::Manager;
            use std::fs::OpenOptions;
            use std::io::Write;

            let app_handle = app.clone();
            tauri::async_runtime::spawn(async move {
                // Keep `child` alive for the lifetime of this task
                let mut _keepalive_child = child;

                // log_path was already computed in spawn_and_wait, but we recompute it
                // here for the background thread to avoid moving it if not needed.
                let log_path = app_handle.path().home_dir()
                    .map(|h| h.join(".devo").join("sidecar.log"))
                    .unwrap_or_else(|_| std::path::PathBuf::from(".devo/sidecar.log"));

                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
                            let msg = String::from_utf8_lossy(&bytes);
                            let msg_trimmed = msg.trim();
                            if msg_trimmed.is_empty() {
                                continue;
                            }

                            // Write to the UI console for local debugging
                            eprintln!("[sidecar] {}", msg_trimmed);

                            // Append to sidecar.log so the LogsPage UI can pick it up
                            if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&log_path) {
                                let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S");
                                for line in msg_trimmed.lines() {
                                    let line = line.trim_end(); // only trim end to keep indentation
                                    if line.is_empty() {
                                        continue;
                                    }
                                    let has_timestamp = line.len() > 10 && line.chars().nth(4) == Some('-') && line.chars().nth(7) == Some('-');
                                    if has_timestamp {
                                        let _ = writeln!(file, "{}", line);
                                    } else if line.starts_with("INFO:") {
                                        let _ = writeln!(file, "{} INFO [console] {}", now, line);
                                    } else if line.starts_with("WARNING:") {
                                        let _ = writeln!(file, "{} WARN [console] {}", now, line);
                                    } else if line.starts_with("ERROR:") {
                                        let _ = writeln!(file, "{} ERROR [console] {}", now, line);
                                    } else {
                                        // Raw line (e.g. stacktrace or standard print), write as is
                                        // so the UI can group it with the previous log entry.
                                        let _ = writeln!(file, "{}", line);
                                    }
                                }
                            }
                        }
                        CommandEvent::Terminated(_) => {
                            eprintln!("[sidecar] Terminated");
                            break;
                        }
                        CommandEvent::Error(e) => {
                            eprintln!("[sidecar] Error: {}", e);
                            break;
                        }
                        _ => {}
                    }
                }

                // Explicitly kill if the loop breaks
                let _ = _keepalive_child.kill();
            });

            Ok(info)
        },
        Ok(Err(e)) => Err(e),
        Err(_) => Err("timed out waiting for DEVO_SIDECAR_READY (30s)".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_valid_ready_line() {
        let info = parse_ready_line("DEVO_SIDECAR_READY port=54321 token=abc123").unwrap();
        assert_eq!(info.port, 54321);
        assert_eq!(info.token, "abc123");
    }

    #[test]
    fn parse_ignores_unrelated_lines() {
        assert!(parse_ready_line("INFO:     Started server").is_none());
        assert!(parse_ready_line("").is_none());
    }

    #[test]
    fn parse_missing_token_returns_none() {
        assert!(parse_ready_line("DEVO_SIDECAR_READY port=8000").is_none());
    }

    #[test]
    fn parse_missing_port_returns_none() {
        assert!(parse_ready_line("DEVO_SIDECAR_READY token=abc").is_none());
    }
}
