import { describe, it, expect, beforeEach, vi } from "vitest";
import { isEnabled, enable, disable } from "@tauri-apps/plugin-autostart";
import { isAutostartEnabled, setAutostartEnabled } from "../autostart";

const mockIsEnabled = vi.mocked(isEnabled);
const mockEnable = vi.mocked(enable);
const mockDisable = vi.mocked(disable);

describe("autostart", () => {
  beforeEach(() => {
    mockIsEnabled.mockReset();
    mockEnable.mockReset();
    mockDisable.mockReset();
  });

  describe("isAutostartEnabled", () => {
    it("returns the plugin's reported state", async () => {
      mockIsEnabled.mockResolvedValueOnce(true);
      expect(await isAutostartEnabled()).toBe(true);
    });

    it("returns false when the plugin call fails (dev mode / unsupported platform)", async () => {
      mockIsEnabled.mockRejectedValueOnce(new Error("plugin not registered"));
      expect(await isAutostartEnabled()).toBe(false);
    });
  });

  describe("setAutostartEnabled", () => {
    it("calls enable() when turning on", async () => {
      await setAutostartEnabled(true);
      expect(mockEnable).toHaveBeenCalledOnce();
      expect(mockDisable).not.toHaveBeenCalled();
    });

    it("calls disable() when turning off", async () => {
      await setAutostartEnabled(false);
      expect(mockDisable).toHaveBeenCalledOnce();
      expect(mockEnable).not.toHaveBeenCalled();
    });

    it("propagates errors from the plugin", async () => {
      mockEnable.mockRejectedValueOnce(new Error("permission denied"));
      await expect(setAutostartEnabled(true)).rejects.toThrow("permission denied");
    });
  });
});
