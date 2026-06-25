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
    let (mut rx, _child) = {
        #[cfg(debug_assertions)]
        {
            // Dev: the `scripts/build_sidecar_placeholder.sh` wrapper
            // sits at `binaries/devo-sidecar-<triple>`. Tauri resolves
            // it via the `externalBin` config and exec's the script.
            app.shell()
                .sidecar("devo-sidecar")
                .map_err(|e| format!("sidecar placeholder not found: {e}"))?
                .args(["--port", "0"])
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
        Ok(inner) => inner,
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
