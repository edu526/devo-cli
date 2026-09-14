/**
 * Launch-at-login client.
 *
 * Thin wrapper around `@tauri-apps/plugin-autostart`, which registers/removes
 * the OS-level autostart entry (Registry Run key on Windows, LaunchAgent on
 * macOS, .desktop file on Linux). There is no app-level persistence — the OS
 * entry itself is the source of truth, so `isAutostartEnabled` always reflects
 * what's actually registered.
 *
 * Defaulted to enabled for new installs from `App.svelte`'s first-run
 * (onboarding) gate; after that, only the OS entry matters, so a user who
 * disables it from Settings stays disabled.
 */

import { isEnabled, enable, disable } from "@tauri-apps/plugin-autostart";

export async function isAutostartEnabled(): Promise<boolean> {
  try {
    return await isEnabled();
  } catch {
    // No autostart plugin registered, or not running inside Tauri (browser dev mode).
    return false;
  }
}

export async function setAutostartEnabled(next: boolean): Promise<void> {
  if (next) {
    await enable();
  } else {
    await disable();
  }
}
