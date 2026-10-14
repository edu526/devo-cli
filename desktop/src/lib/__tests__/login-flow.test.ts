import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({
  profilesApi: { refreshAll: vi.fn() },
}));
vi.mock("../notifications", () => ({ notifyLoginRequired: vi.fn(), notifyUser: vi.fn() }));

import { get } from "svelte/store";
import { profilesApi } from "../api";
import { notifyLoginRequired, notifyUser } from "../notifications";
import { loginActive, loginError, loginInProgress, loginNeeded, loginUrls } from "../stores";
import { ws } from "../ws";
import { _resetLoginFlow, autoOpenBrowser, ensureLogin, startLogin, startLoginWatcher } from "../login-flow";

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

      emit("sso.session.login_finished", { session: "corp", success: true });
      expect(get(loginActive).has("corp")).toBe(false);
    });

    it("an automatic one tells the user why a browser tab appeared, once per session", () => {
      emit("sso.session.login_started", { session: "corp", source: "connection", automatic: true });
      emit("sso.session.login_finished", { session: "corp", success: false });
      emit("sso.session.login_started", { session: "corp", source: "auto_renew", automatic: true });

      const started = vi.mocked(notifyUser).mock.calls.filter(([title]) => title === "AWS sign-in needed");
      expect(started).toHaveLength(1);
      expect(started[0]![1]).toContain("corp");
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

    it("a successful one clears the session at once", () => {
      loginNeeded.set({ corp: ["a"], personal: ["z", "y"] });

      emit("sso.session.login_finished", { session: "corp", success: true });

      expect(get(loginNeeded)).toEqual({ personal: ["z", "y"] });
    });

    it("then the profiles the sidecar renews after it", () => {
      loginNeeded.set({ personal: ["z", "y"] });

      emit("sso.session.profiles_renewed", { session: "corp", renewed: ["z"] });

      expect(get(loginNeeded)).toEqual({ personal: ["y"] });
    });
  });

  describe("a login the sidecar held back", () => {
    it("records the profiles per session and notifies", () => {
      emit("profile.needs_login", { names: ["a", "b"], by_session: { corp: ["a", "b"] } });

      expect(get(loginNeeded)).toEqual({ corp: ["a", "b"] });
      expect(notifyLoginRequired).toHaveBeenCalledWith(["a", "b"]);
    });

    it("adds the profiles of a session reported again instead of replacing them", () => {
      emit("profile.needs_login", { names: ["a"], by_session: { corp: ["a"] } });
      emit("profile.needs_login", { names: ["b", "a"], by_session: { corp: ["b", "a"] } });
      expect(get(loginNeeded)).toEqual({ corp: ["a", "b"] });
    });

    it("is forgotten when the sidecar reports the session works again", () => {
      loginNeeded.set({ corp: ["a"], personal: ["z"] });
      emit("profile.login_resolved", { sessions: ["corp"] });
      expect(get(loginNeeded)).toEqual({ personal: ["z"] });
    });
  });

  describe("ensureLogin", () => {
    const settle = () => new Promise((r) => setTimeout(r, 0));

    it("renews exactly the profiles asked for and says which got credentials", async () => {
      const done = ensureLogin(["db-dev", "db-prod", "db-dev"]);
      await settle();
      expect(refreshAll).toHaveBeenCalledWith(false, {
        allowBrowser: true,
        targets: { profiles: ["db-dev", "db-prod"], sessions: [] },
      });

      emit("profile.refreshed", { names: ["db-dev"], success: true });

      expect([...(await done)]).toEqual(["db-dev"]);
    });

    it("shares one request between callers asking for the same profiles", async () => {
      const first = ensureLogin(["db-dev"]);
      const second = ensureLogin(["db-dev"]);
      await settle();
      emit("profile.refreshed", { names: ["db-dev"], success: true });

      expect(await first).toBe(await second);
      expect(refreshAll).toHaveBeenCalledOnce();
    });

    it("asks again for what a refresh already running didn't cover", async () => {
      refreshAll
        .mockResolvedValueOnce({ status: "already_running", message: "" })
        .mockResolvedValueOnce({ status: "accepted", message: "" });
      const done = ensureLogin(["db-dev", "db-prod"]);
      await settle();
      emit("profile.refreshed", { names: ["db-dev"], success: true }); // the other run's result
      await settle();
      expect(refreshAll).toHaveBeenLastCalledWith(false, {
        allowBrowser: true,
        targets: { profiles: ["db-prod"], sessions: [] },
      });
      emit("profile.refreshed", { names: ["db-prod"], success: true });

      expect([...(await done)].sort()).toEqual(["db-dev", "db-prod"]);
    });

    it("fails when the request does", async () => {
      refreshAll.mockRejectedValue(new Error("down"));
      await expect(ensureLogin(["db-dev"])).rejects.toThrow("down");
    });
  });

  describe("the sign-in page of a login in progress", () => {
    it("is kept per session until the login ends", () => {
      emit("sso.login.url_ready", { session: "corp", profile: "a", url: "https://sign-in", code: "" });
      expect(get(loginUrls)).toEqual({ corp: { url: "https://sign-in", code: "" } });

      emit("sso.session.login_finished", { session: "corp", success: true });
      expect(get(loginUrls)).toEqual({});
    });
  });

  describe("a login Devo opened by itself that isn't completed", () => {
    it("is notified, so it isn't missed while Devo is hidden", () => {
      emit("sso.session.login_started", { session: "corp", source: "connection", automatic: true });
      vi.mocked(notifyUser).mockReset();
      emit("sso.session.login_finished", { session: "corp", success: false, renewed: [] });
      expect(notifyUser).toHaveBeenCalledWith("AWS sign-in not completed", expect.stringContaining("corp"));
    });

    it("but one the user started isn't", () => {
      emit("sso.session.login_started", { session: "corp", source: "profile", automatic: false });
      emit("sso.session.login_finished", { session: "corp", success: false, renewed: [] });
      expect(notifyUser).not.toHaveBeenCalled();
    });
  });

  describe("the auto open browser setting", () => {
    it("is on unless turned off", () => {
      expect(autoOpenBrowser({})).toBe(true);
      expect(autoOpenBrowser({ aws_login: { auto_open_browser: true } })).toBe(true);
      expect(autoOpenBrowser({ aws_login: { auto_open_browser: false } })).toBe(false);
    });
  });

  describe("the Log in button", () => {
    it("runs the refresh flow that renews silently and logs in only what needs it", async () => {
      expect(await startLogin()).toBe(true);
      expect(refreshAll).toHaveBeenCalledWith(false, {
        allowBrowser: true,
        targets: { profiles: [], sessions: [] },
      });
      expect(get(loginInProgress)).toBe(true);
    });

    it("asks for exactly what the banner shows, not whatever refresh-all finds stale", async () => {
      loginNeeded.set({ corp: ["a", "b"], legacy: [] });
      await startLogin();
      expect(refreshAll).toHaveBeenCalledWith(false, {
        allowBrowser: true,
        targets: { profiles: ["a", "b"], sessions: ["legacy"] },
      });
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
