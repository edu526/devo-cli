/**
 * Theme store: 'dark' | 'light' | 'system'.
 *
 * `system` follows the OS `prefers-color-scheme` media query; the
 * resolved value is what `applyTheme` writes to the document root.
 * Persists to localStorage so the choice survives a restart.
 */

import { writable, type Writable } from "svelte/store";

export type Theme = "dark" | "light" | "system";

const STORAGE_KEY = "devo.theme";

function detectInitial(): Theme {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage?.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light" || stored === "system") return stored;
  return "dark";
}

export const theme: Writable<Theme> = writable<Theme>(detectInitial());

/** Subscribe in App.svelte so the document re-themes reactively. */
export function applyTheme(value: Theme): void {
  if (typeof document === "undefined") return;
  const resolved = resolveTheme(value);
  document.documentElement.setAttribute("data-theme", resolved);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // localStorage unavailable (private mode); the in-memory store
      // still keeps the choice for this session.
    }
  }
}

export function resolveTheme(value: Theme): "dark" | "light" {
  if (value !== "system") return value;
  if (typeof window === "undefined") return "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
