/**
 * Auto-update client.
 *
 * Wraps the two Tauri commands exposed by `src-tauri/src/updater.rs`:
 *   - `fetch_update`  → polls the manifest, returns metadata if newer
 *   - `install_update` → downloads + installs, streams progress via Channel
 *
 * The plugin itself (tauri-plugin-updater) is also available as
 * `@tauri-apps/plugin-updater` and is used as a fallback when not running
 * inside a Tauri webview (i.e. browser dev mode).
 *
 * Exposes a `updateAvailable` store so other components (TitleBar,
 * UpdateBanner, future Onboarding) can react to a single source of
 * truth rather than each polling the manifest independently.
 */

import { writable, type Readable } from "svelte/store";
import { invoke, Channel } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";

export interface UpdateMetadata {
  version: string;
  currentVersion: string;
}

const _updateAvailableStore = writable<UpdateMetadata | null>(null);

/** Reactive store: non-null when an update is available. */
export const updateAvailable: Readable<UpdateMetadata | null> = {
  subscribe: _updateAvailableStore.subscribe,
};

export function setUpdateAvailable(meta: UpdateMetadata | null): void {
  _updateAvailableStore.set(meta);
}

export type DownloadEvent =
  | { event: "started"; data: { contentLength: number | null } }
  | { event: "progress"; data: { chunkLength: number } }
  | { event: "finished"; data: null };

export interface ProgressState {
  phase: "idle" | "downloading" | "finished" | "error";
  downloaded: number;
  total: number | null;
  error: string | null;
}

export type ProgressUpdater = ProgressState | ((prev: ProgressState) => ProgressState);

const INITIAL_PROGRESS: ProgressState = {
  phase: "idle",
  downloaded: 0,
  total: null,
  error: null,
};

export async function getAppVersion(): Promise<string | null> {
  try {
    return await getVersion();
  } catch {
    return null;
  }
}

export async function fetchUpdate(): Promise<UpdateMetadata | null> {
  try {
    const result = await invoke<UpdateMetadata | null>("fetch_update");
    setUpdateAvailable(result);
    return result;
  } catch {
    // No updater configured, no network, or plugin not registered in dev.
    setUpdateAvailable(null);
    return null;
  }
}

export async function installUpdate(
  onProgress: (state: ProgressUpdater) => void,
): Promise<boolean> {
  onProgress(INITIAL_PROGRESS);
  const channel = new Channel<DownloadEvent>();
  channel.onmessage = (msg) => {
    if (msg.event === "started") {
      onProgress({ phase: "downloading", downloaded: 0, total: msg.data.contentLength, error: null });
    } else if (msg.event === "progress") {
      onProgress((prev: ProgressState) => ({
        phase: "downloading",
        downloaded: prev.downloaded + msg.data.chunkLength,
        total: prev.total,
        error: null,
      }));
    } else if (msg.event === "finished") {
      onProgress((prev: ProgressState) => ({
        phase: "finished",
        downloaded: prev.downloaded,
        total: prev.total,
        error: null,
      }));
    }
  };

  try {
    await invoke("install_update", { onEvent: channel });
    return true;
  } catch (e) {
    onProgress({
      phase: "error",
      downloaded: 0,
      total: null,
      error: e instanceof Error ? e.message : String(e),
    });
    return false;
  }
}
