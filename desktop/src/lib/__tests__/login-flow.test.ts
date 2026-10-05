import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({
  profilesApi: { refreshAll: vi.fn() },
}));
vi.mock("../notifications", () => ({ notifyLoginRequired: vi.fn(), notifyUser: vi.fn() }));

import { get } from "svelte/store";
import { profilesApi } from "../api";
import { notifyLoginRequired, notifyUser } from "../notifications";
import { loginActive, loginError, loginInProgress, loginNeeded } from "../stores";
import { ws } from "../ws";
import { _resetLoginFlow, startLogin, startLoginWatcher } from "../login-flow";

const refreshAll = vi.mocked(profilesApi.refreshAll);

function emit(event: string, payload: Record<string, unknown> = {}) {
  (ws as unknown as { _emit(e: string, m: unknown): void })._emit(event, { event, ...payload });
}

describe("login-flow", () => {
  let stop: () => void;

  beforeEach(() => {
    refreshAll.mockReset().mockResolvedValue({ status: "accepted", message: "" });
    vi.mocked(notifyLoginRequired).mockReset();
    vi.mocked(notifyUser).mockReset();
    _resetLoginFlow();
    stop = startLoginWatcher();
  });

  afterEach(() => {
    stop();
    vi.useRealTimers();
  });

  describe("a login the sidecar opened", () => {
    it("is shown as in progress until it finishes", () => {
      emit("sso.session.login_started", { session: "corp", source: "connection", automatic: true });
      expect(get(loginActive).has("corp")).toBe(true);

      emit("sso.session.login_finished", { session: "corp", success: true, renewed: [] });
      expect(get(loginActive).has("corp")).toBe(false);
    });

    it("an automatic one tells the user why a browser tab appeared, once per session", () => {
      emit("sso.session.login_started", { session: "corp", source: "connection", automatic: true });
      emit("sso.session.login_finished", { session: "corp", success: false });
      emit("sso.session.login_started", { session: "corp", source: "auto_renew", automatic: true });

      expect(notifyUser).toHaveBeenCalledOnce();
      expect(vi.mocked(notifyUser).mock.calls[0]![1]).toContain("corp");
    });

    it("a user-initiated one does not notify (they just clicked)", () => {
      emit("sso.session.login_started", { session: "corp", source: "profile", automatic: false });
      expect(notifyUser).not.toHaveBeenCalled();
    });

    it("a failed one leaves the session waiting for the Log in button", () => {
      emit("sso.session.login_started", { session: "corp", source: "connection", automatic: true });
      emit("sso.session.login_finished", { session: "corp", success: false });

      expect(get(loginNeeded)).toEqual({ corp: [] });
    });

    it("a successful one clears the session and its renewed profiles", () => {
      loginNeeded.set({ corp: ["a"], personal: ["z", "y"] });

      emit("sso.session.login_finished", { session: "corp", success: true, renewed: ["z"] });

      expect(get(loginNeeded)).toEqual({ personal: ["y"] });
    });
  });

  describe("a login the sidecar held back", () => {
    it("records the profiles per session and notifies", () => {
      emit("profile.needs_login", { names: ["a", "b"], by_session: { corp: ["a", "b"] } });

      expect(get(loginNeeded)).toEqual({ corp: ["a", "b"] });
      expect(notifyLoginRequired).toHaveBeenCalledWith(["a", "b"]);
    });

    it("is forgotten when the sidecar reports the session works again", () => {
      loginNeeded.set({ corp: ["a"], personal: ["z"] });
      emit("profile.login_resolved", { sessions: ["corp"] });
      expect(get(loginNeeded)).toEqual({ personal: ["z"] });
    });
  });

  describe("the Log in button", () => {
    it("runs the refresh flow that renews silently and logs in only what needs it", async () => {
      expect(await startLogin()).toBe(true);
      expect(refreshAll).toHaveBeenCalledWith(false, { allowBrowser: true });
      expect(get(loginInProgress)).toBe(true);
    });

    it("never runs twice at once", async () => {
      await startLogin();
      expect(await startLogin()).toBe(false);
      expect(refreshAll).toHaveBeenCalledOnce();
    });

    it("is done when the refresh reports back, which also drops the renewed profiles", async () => {
      loginNeeded.set({ corp: ["a", "b"] });
      await startLogin();

      emit("profile.refreshed", { names: ["a"], success: true });

      expect(get(loginInProgress)).toBe(false);
      expect(get(loginNeeded)).toEqual({ corp: ["b"] });
    });

    it("keeps sessions known only by name until resolved", () => {
      loginNeeded.set({ corp: [] });
      emit("profile.refreshed", { names: ["x"], success: true });
      expect(get(loginNeeded)).toEqual({ corp: [] });
    });

    it("stops waiting if the sidecar never answers", async () => {
      vi.useFakeTimers();
      await startLogin();
      await vi.advanceTimersByTimeAsync(5 * 60 * 1000 + 10);
      expect(get(loginInProgress)).toBe(false);
    });

    it("on a rate limit, explains it and retries once the limit resets", async () => {
      vi.useFakeTimers();
      refreshAll.mockRejectedValueOnce(Object.assign(new Error("429"), { status: 429 }));

      expect(await startLogin()).toBe(false);
      expect(get(loginError)).toMatch(/Retrying in a minute/);

      await vi.advanceTimersByTimeAsync(65 * 1000);

      expect(refreshAll).toHaveBeenCalledTimes(2);
      expect(get(loginError)).toBeNull();
    });

    it("a click during the wait replaces the scheduled retry", async () => {
      vi.useFakeTimers();
      refreshAll.mockRejectedValueOnce(Object.assign(new Error("429"), { status: 429 }));
      await startLogin();
      await vi.advanceTimersByTimeAsync(10 * 1000);

      await startLogin();
      emit("profile.refreshed", { names: [], success: true });
      await vi.advanceTimersByTimeAsync(60 * 1000);

      expect(refreshAll).toHaveBeenCalledTimes(2);
    });

    it("reports other errors and lets the user try again", async () => {
      refreshAll.mockRejectedValueOnce(new Error("boom"));
      expect(await startLogin()).toBe(false);
      expect(get(loginError)).toBe("boom");
      expect(get(loginInProgress)).toBe(false);
    });
  });

  it("stops reacting once the watcher is stopped", () => {
    stop();
    emit("profile.needs_login", { names: ["a"], by_session: { corp: ["a"] } });
    emit("sso.session.login_started", { session: "corp", automatic: true });
    expect(get(loginNeeded)).toEqual({});
    expect(get(loginActive).size).toBe(0);
    stop = startLoginWatcher();
  });
});
