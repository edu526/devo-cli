import { get } from "svelte/store";
import { profilesApi } from "./api";
import { notifyLoginRequired, notifyUser } from "./notifications";
import { loginActive, loginError, loginInProgress, loginNeeded } from "./stores";
import { ws, type WsMessage } from "./ws";

/**
 * UI side of the sidecar's single login handler. The sidecar decides when a
 * browser login is needed and opens it itself (also while Devo is hidden in
 * the tray); this module only reflects that state:
 *
 * - `loginActive`: SSO sessions whose browser login is open right now
 *   (`sso.session.login_started` / `login_finished`)
 * - `loginNeeded`: sessions that need a login the sidecar did not start on its
 *   own (an automatic one was recently ignored), or whose login failed. The
 *   banner offers a "Log in" button for them.
 */

// Stop showing "waiting for the browser" if the sidecar never reports back.
const LOGIN_TIMEOUT_MS = 5 * 60 * 1000;
// The refresh endpoint allows a few calls per minute; wait that out on a 429.
const RATE_LIMIT_RETRY_MS = 65 * 1000;
// One "finish signing in" notification per session per this window.
const STARTED_NOTICE_WINDOW_MS = 5 * 60 * 1000;

let loginTimeout: ReturnType<typeof setTimeout> | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
const lastStartedNotice = new Map<string, number>();

function finishLogin(): void {
  if (loginTimeout !== null) clearTimeout(loginTimeout);
  loginTimeout = null;
  loginInProgress.set(false);
}

/**
 * "Log in" button: run the sidecar's refresh-all flow, which renews silently
 * what it can and opens the browser (through the same handler) for the rest.
 * Returns false if one is already running or the request failed.
 */
export async function startLogin(): Promise<boolean> {
  if (get(loginInProgress)) return false;
  if (retryTimer !== null) clearTimeout(retryTimer);
  retryTimer = null;
  loginInProgress.set(true);
  loginError.set(null);
  loginTimeout = setTimeout(finishLogin, LOGIN_TIMEOUT_MS);
  try {
    await profilesApi.refreshAll(false, { allowBrowser: true });
    return true;
  } catch (e) {
    finishLogin();
    if ((e as { status?: number }).status === 429) {
      loginError.set("Devo refreshed moments ago. Retrying in a minute…");
      retryTimer = setTimeout(() => {
        retryTimer = null;
        void startLogin();
      }, RATE_LIMIT_RETRY_MS);
    } else {
      loginError.set(e instanceof Error ? e.message : String(e));
    }
    return false;
  }
}

function setActive(session: string, active: boolean): void {
  loginActive.update((current) => {
    const next = new Set(current);
    if (active) next.add(session);
    else next.delete(session);
    return next;
  });
}

function forgetSessions(sessions: string[]): void {
  loginNeeded.update((current) => {
    const next = { ...current };
    sessions.forEach((s) => delete next[s]);
    return next;
  });
}

function forgetProfiles(renewed: string[]): void {
  if (renewed.length === 0) return;
  const done = new Set(renewed);
  loginNeeded.update((current) => {
    const next: Record<string, string[]> = {};
    for (const [session, names] of Object.entries(current)) {
      const left = names.filter((n) => !done.has(n));
      // keep sessions known only by name (no profile list) until resolved
      if (left.length > 0 || names.length === 0) next[session] = left;
    }
    return next;
  });
}

function noticeLoginStarted(session: string): void {
  const now = Date.now();
  const last = lastStartedNotice.get(session);
  if (last !== undefined && now - last < STARTED_NOTICE_WINDOW_MS) return;
  lastStartedNotice.set(session, now);
  void notifyUser(
    "AWS sign-in needed",
    `Devo opened your browser to sign in to "${session}". Finish there to keep your connections working.`,
  );
}

/** Keep the login state in sync with the sidecar. Returns a stop function. */
export function startLoginWatcher(): () => void {
  const offStarted = ws.on("sso.session.login_started", (msg: WsMessage) => {
    const session = msg.session as string;
    setActive(session, true);
    // The user didn't click anything for automatic logins: tell them why a
    // browser tab just appeared.
    if (msg.automatic) noticeLoginStarted(session);
  });

  const offFinished = ws.on("sso.session.login_finished", (msg: WsMessage) => {
    const session = msg.session as string;
    setActive(session, false);
    if (msg.success) {
      forgetSessions([session]);
      forgetProfiles((msg.renewed as string[] | undefined) ?? []);
    } else {
      // Still needs a login; offer the button.
      loginNeeded.update((current) => ({ ...current, [session]: current[session] ?? [] }));
    }
  });

  const offNeeded = ws.on("profile.needs_login", (msg: WsMessage) => {
    const bySession = (msg.by_session as Record<string, string[]> | undefined) ?? {};
    loginNeeded.update((current) => ({ ...current, ...bySession }));
    notifyLoginRequired((msg.names as string[] | undefined) ?? []);
  });

  const offResolved = ws.on("profile.login_resolved", (msg: WsMessage) => {
    forgetSessions((msg.sessions as string[] | undefined) ?? []);
  });

  const offRefreshed = ws.on("profile.refreshed", (msg: WsMessage) => {
    finishLogin();
    forgetProfiles((msg.names as string[] | undefined) ?? []);
  });

  return () => {
    offStarted();
    offFinished();
    offNeeded();
    offResolved();
    offRefreshed();
  };
}

/** Test hook: forget all state. */
export function _resetLoginFlow(): void {
  if (retryTimer !== null) clearTimeout(retryTimer);
  retryTimer = null;
  lastStartedNotice.clear();
  finishLogin();
  loginNeeded.set({});
  loginActive.set(new Set());
  loginError.set(null);
}
