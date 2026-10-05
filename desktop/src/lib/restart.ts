import { invoke } from "@tauri-apps/api/core";

// Guard against a restart loop: if the app already auto-restarted very
// recently and the session is *still* lost, something else is wrong, so stop
// restarting on its own and leave the manual button.
const AUTO_RESTART_KEY = "devo_last_auto_restart";
const AUTO_RESTART_MIN_GAP_MS = 2 * 60 * 1000;

export function canAutoRestart(): boolean {
  try {
    const last = Number(localStorage.getItem(AUTO_RESTART_KEY) ?? 0);
    return Date.now() - last > AUTO_RESTART_MIN_GAP_MS;
  } catch {
    return true;
  }
}

export function markAutoRestart(): void {
  try {
    localStorage.setItem(AUTO_RESTART_KEY, String(Date.now()));
  } catch {
    // storage unavailable — the loop guard degrades to "always allowed"
  }
}

/**
 * Relaunch Devo (kills the sidecar, starts a fresh process with a new
 * bootstrap token). If the window is hidden in the tray it stays hidden, so
 * an automatic recovery overnight doesn't pop a window up.
 */
export async function restartApp(): Promise<void> {
  await invoke("restart_app", { showWindow: document.visibilityState === "visible" });
}
