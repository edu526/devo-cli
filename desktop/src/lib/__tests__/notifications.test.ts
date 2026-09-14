import { describe, it, expect, beforeEach, vi } from "vitest";
import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/plugin-notification";

const mockIsPermissionGranted = vi.mocked(isPermissionGranted);
const mockRequestPermission = vi.mocked(requestPermission);
const mockSendNotification = vi.mocked(sendNotification);

// notifyUser() caches permission state in a module-level variable so it isn't
// re-checked on every call. Each test needs a fresh module instance so that
// cache doesn't leak between assertions about how many times the permission
// APIs were called.
async function freshNotifyUser() {
  vi.resetModules();
  const mod = await import("../notifications");
  return mod.notifyUser;
}

describe("notifyUser", () => {
  beforeEach(() => {
    mockIsPermissionGranted.mockReset().mockResolvedValue(true);
    mockRequestPermission.mockReset().mockResolvedValue("granted");
    mockSendNotification.mockReset();
  });

  it("sends the notification when permission is already granted", async () => {
    const notifyUser = await freshNotifyUser();
    await notifyUser("Title", "Body");
    expect(mockRequestPermission).not.toHaveBeenCalled();
    expect(mockSendNotification).toHaveBeenCalledWith({ title: "Title", body: "Body" });
  });

  it("requests permission when not yet granted, then sends", async () => {
    mockIsPermissionGranted.mockResolvedValue(false);
    const notifyUser = await freshNotifyUser();
    await notifyUser("Title", "Body");
    expect(mockRequestPermission).toHaveBeenCalledOnce();
    expect(mockSendNotification).toHaveBeenCalledWith({ title: "Title", body: "Body" });
  });

  it("does not send when the user denies permission", async () => {
    mockIsPermissionGranted.mockResolvedValue(false);
    mockRequestPermission.mockResolvedValue("denied");
    const notifyUser = await freshNotifyUser();
    await notifyUser("Title", "Body");
    expect(mockSendNotification).not.toHaveBeenCalled();
  });

  it("caches a granted permission instead of re-checking on every call", async () => {
    const notifyUser = await freshNotifyUser();
    await notifyUser("A", "1");
    await notifyUser("B", "2");
    await notifyUser("C", "3");
    expect(mockIsPermissionGranted).toHaveBeenCalledOnce();
    expect(mockSendNotification).toHaveBeenCalledTimes(3);
  });

  it("caches a denied permission instead of re-prompting on every call", async () => {
    mockIsPermissionGranted.mockResolvedValue(false);
    mockRequestPermission.mockResolvedValue("denied");
    const notifyUser = await freshNotifyUser();
    await notifyUser("A", "1");
    await notifyUser("B", "2");
    expect(mockRequestPermission).toHaveBeenCalledOnce();
    expect(mockSendNotification).not.toHaveBeenCalled();
  });

  it("swallows errors from the notification APIs instead of throwing", async () => {
    mockIsPermissionGranted.mockRejectedValue(new Error("no webview"));
    const notifyUser = await freshNotifyUser();
    await expect(notifyUser("Title", "Body")).resolves.toBeUndefined();
    expect(mockSendNotification).not.toHaveBeenCalled();
  });
});
