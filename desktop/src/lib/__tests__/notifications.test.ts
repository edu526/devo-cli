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

  it("does not send (or touch permissions) when notifications are disabled in config", async () => {
    // Reset once, then import page-stores and notifications from that same
    // fresh registry generation so both resolve to the same configCache
    // instance — a second resetModules() (e.g. inside freshNotifyUser())
    // would give notifications.ts its own, disconnected copy of the store.
    vi.resetModules();
    const { configCache } = await import("../page-stores");
    configCache.set({ notifications_enabled: false });
    const { notifyUser } = await import("../notifications");

    await expect(notifyUser("Title", "Body")).resolves.toBeUndefined();
    expect(mockIsPermissionGranted).not.toHaveBeenCalled();
    expect(mockRequestPermission).not.toHaveBeenCalled();
    expect(mockSendNotification).not.toHaveBeenCalled();
  });
});

describe("notifyLoginRequired", () => {
  async function fresh() {
    vi.resetModules();
    const mod = await import("../notifications");
    mod._resetLoginNotice();
    return mod.notifyLoginRequired;
  }
  const flush = () => new Promise((r) => setTimeout(r, 0));

  beforeEach(() => {
    mockIsPermissionGranted.mockReset().mockResolvedValue(true);
    mockRequestPermission.mockReset().mockResolvedValue("granted");
    mockSendNotification.mockReset();
  });

  it("does nothing for an empty list", async () => {
    const notify = await fresh();
    notify([]);
    await flush();
    expect(mockSendNotification).not.toHaveBeenCalled();
  });

  it("names the profiles that need a login", async () => {
    const notify = await fresh();
    notify(["dev", "prod"]);
    await flush();
    expect(mockSendNotification).toHaveBeenCalledOnce();
    const sent = mockSendNotification.mock.calls[0]![0] as { title: string; body: string };
    expect(sent.title).toBe("AWS login required");
    expect(sent.body).toContain("dev, prod");
  });

  it("summarises long lists", async () => {
    const notify = await fresh();
    notify(["a", "b", "c", "d", "e"]);
    await flush();
    expect((mockSendNotification.mock.calls[0]![0] as { body: string }).body).toContain("a, b, c and 2 more");
  });

  it("shows the same condition only once, whichever path reports it", async () => {
    const notify = await fresh();
    notify(["a", "b"]);
    notify(["b", "a"]); // same set, different order
    await flush();
    expect(mockSendNotification).toHaveBeenCalledOnce();
  });

  it("shows a different condition right away", async () => {
    const notify = await fresh();
    notify(["a"]);
    notify(["a", "z"]);
    await flush();
    expect(mockSendNotification).toHaveBeenCalledTimes(2);
  });

  it("shows the same condition again once the window has passed", async () => {
    vi.useFakeTimers();
    try {
      const notify = await fresh();
      notify(["a"]);
      await vi.advanceTimersByTimeAsync(3 * 60 * 1000);
      notify(["a"]);
      await vi.advanceTimersByTimeAsync(10);
      expect(mockSendNotification).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
