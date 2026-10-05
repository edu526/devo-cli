import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/plugin-notification";
import { get } from "svelte/store";
import { configCache } from "./page-stores";

// Cached across the whole session so every notifyUser() call doesn't re-ask
// the OS for permission — a plain repeated isPermissionGranted()/
// requestPermission() round trip per call added nondeterministic latency to
// when notifications actually appeared, and repeatedly calling
// requestPermission() after the user has already denied it would re-prompt
// them. "denied" is intentionally sticky for the session: if the user grants
// it later via OS settings, a restart picks that up, same as most apps.
let permissionState: "granted" | "denied" | "unknown" = "unknown";

async function ensurePermission(): Promise<boolean> {
  if (permissionState === "granted") return true;
  if (permissionState === "denied") return false;
  try {
    let granted = await isPermissionGranted();
    if (!granted) {
      const permission = await requestPermission();
      granted = permission === "granted";
    }
    permissionState = granted ? "granted" : "denied";
    return granted;
  } catch (err) {
    console.error("Failed to check/request notification permission:", err);
    return false;
  }
}

/** Show an OS-level desktop notification, if permission is (or becomes) granted. */
export async function notifyUser(title: string, body: string): Promise<void> {
  // Explicit opt-out only: an absent/undefined key (or no cached config yet)
  // defaults to enabled, matching the config's own enabled-by-default treatment.
  if (get(configCache)?.notifications_enabled === false) return;
  try {
    if (await ensurePermission()) {
      sendNotification({ title, body });
    }
  } catch (err) {
    console.error("Failed to send desktop notification:", err);
  }
}

// The same "login required" condition is reported by two paths (the sidecar's
// background renewal and the launch-time refresh) and can repeat; show it once.
const LOGIN_NOTIFY_WINDOW_MS = 2 * 60 * 1000;
let lastLoginNotice: { key: string; at: number } | null = null;

/** Tell the user, once per condition, that AWS profiles need a browser login. */
export function notifyLoginRequired(names: string[]): void {
  if (names.length === 0) return;
  const key = [...names].sort().join("|");
  const now = Date.now();
  if (lastLoginNotice && lastLoginNotice.key === key && now - lastLoginNotice.at < LOGIN_NOTIFY_WINDOW_MS) return;
  lastLoginNotice = { key, at: now };

  const shown = names.slice(0, 3).join(", ");
  const extra = names.length > 3 ? ` and ${names.length - 3} more` : "";
  void notifyUser(
    "AWS login required",
    `${shown}${extra} can't be renewed automatically. Open Devo and click Refresh to log in.`,
  );
}

/** Test hook: forget the last notice so tests start clean. */
export function _resetLoginNotice(): void {
  lastLoginNotice = null;
}
