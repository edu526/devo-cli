import { writable, get } from "svelte/store";

export type ErrorSource = "api" | "ws" | "window" | "unhandledrejection" | "tauri";

export interface ErrorEntry {
  id: number;
  ts: number;
  source: ErrorSource;
  message: string;
  detail?: string;
}

const MAX_ENTRIES = 200;

export const errorLog = writable<ErrorEntry[]>([]);

let _nextId = 1;

export function logError(source: ErrorSource, message: string, detail?: string): void {
  const entry: ErrorEntry = { id: _nextId++, ts: Date.now(), source, message, detail };
  errorLog.update((entries) => {
    const next = entries.length >= MAX_ENTRIES ? entries.slice(entries.length - MAX_ENTRIES + 1) : entries.slice();
    next.push(entry);
    return next;
  });
}

export function clearErrorLog(): void {
  errorLog.set([]);
}

export function getErrorLogSnapshot(): ErrorEntry[] {
  return get(errorLog).slice();
}
