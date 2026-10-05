import { describe, it, expect, beforeEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { canAutoRestart, markAutoRestart, restartApp } from "../restart";

const mockInvoke = vi.mocked(invoke);

describe("restart", () => {
  beforeEach(() => {
    mockInvoke.mockReset();
    localStorage.clear();
  });

  it("allows an automatic restart when none happened recently", () => {
    expect(canAutoRestart()).toBe(true);
  });

  it("blocks a second automatic restart within the loop-guard window", () => {
    markAutoRestart();
    expect(canAutoRestart()).toBe(false);
  });

  it("allows an automatic restart again once the window has passed", () => {
    localStorage.setItem("devo_last_auto_restart", String(Date.now() - 3 * 60 * 1000));
    expect(canAutoRestart()).toBe(true);
  });

  it("asks Tauri to restart, showing the window only when it is visible", async () => {
    mockInvoke.mockResolvedValueOnce(undefined);
    await restartApp();
    expect(mockInvoke).toHaveBeenCalledWith("restart_app", {
      showWindow: document.visibilityState === "visible",
    });
  });
});
