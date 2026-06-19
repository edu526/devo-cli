import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { fetchUpdate, installUpdate, type ProgressState } from "../update";

const mockInvoke = vi.mocked(invoke);

class FakeChannel {
  static instances: FakeChannel[] = [];
  onmessage: ((msg: unknown) => void) | null = null;

  constructor() {
    FakeChannel.instances.push(this);
  }

  emit(msg: unknown): void {
    this.onmessage?.(msg);
  }
}

describe("update", () => {
  beforeEach(() => {
    FakeChannel.instances = [];
    mockInvoke.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("fetchUpdate", () => {
    it("returns metadata when invoke yields one", async () => {
      mockInvoke.mockResolvedValueOnce({
        version: "1.2.3",
        currentVersion: "1.2.0",
      });

      const result = await fetchUpdate();

      expect(result).toEqual({ version: "1.2.3", currentVersion: "1.2.0" });
      expect(mockInvoke).toHaveBeenCalledWith("fetch_update");
    });

    it("returns null when invoke returns null (no update available)", async () => {
      mockInvoke.mockResolvedValueOnce(null);
      const result = await fetchUpdate();
      expect(result).toBeNull();
    });

    it("returns null on invoke error (no updater / offline / dev mode)", async () => {
      mockInvoke.mockRejectedValueOnce(new Error("plugin not registered"));
      const result = await fetchUpdate();
      expect(result).toBeNull();
    });
  });

  describe("installUpdate", () => {
    it("invokes install_update with a Channel and reports progress", async () => {
      mockInvoke.mockImplementation(async (cmd, args) => {
        if (cmd === "install_update") {
          const channel = (args as { onEvent: FakeChannel }).onEvent;
          channel.emit({ event: "started", data: { contentLength: 1024 } });
          channel.emit({ event: "progress", data: { chunkLength: 256 } });
          channel.emit({ event: "progress", data: { chunkLength: 768 } });
          channel.emit({ event: "finished", data: null });
        }
        return undefined;
      });

      const states: { downloaded: number; total: number | null; phase: string }[] = [];
      let last: ProgressState = {
        phase: "idle",
        downloaded: 0,
        total: null,
        error: null,
      };
      const ok = await installUpdate((s) => {
        // The progress callback receives either an object or an updater fn
        const next: ProgressState = typeof s === "function" ? s(last) : s;
        states.push({ downloaded: next.downloaded, total: next.total, phase: next.phase });
        last = next;
      });

      expect(ok).toBe(true);
      expect(states).toEqual([
        { downloaded: 0, total: null, phase: "idle" },
        { downloaded: 0, total: 1024, phase: "downloading" },
        { downloaded: 256, total: 1024, phase: "downloading" },
        { downloaded: 1024, total: 1024, phase: "downloading" },
        { downloaded: 1024, total: 1024, phase: "finished" },
      ]);
    });

    it("captures errors and reports them via the progress callback", async () => {
      mockInvoke.mockRejectedValueOnce(new Error("no pending update"));

      const states: { phase: string; error: string | null }[] = [];
      const ok = await installUpdate((s) => {
        const next: ProgressState = typeof s === "function" ? s({ phase: "idle", downloaded: 0, total: null, error: null }) : s;
        states.push({ phase: next.phase, error: next.error });
      });

      expect(ok).toBe(false);
      expect(states).toContainEqual({ phase: "error", error: "no pending update" });
    });
  });
});
