import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/plugin-notification";

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
  try {
    if (await ensurePermission()) {
      sendNotification({ title, body });
    }
  } catch (err) {
    console.error("Failed to send desktop notification:", err);
  }
}
