import { get } from "svelte/store";
import { profilesApi } from "./api";
import { notifyLoginRequired, notifyUser } from "./notifications";
import { loginActive, loginError, loginInProgress, loginNeeded, loginUrls } from "./stores";
import { ws, type WsMessage } from "./ws";

/**
 * UI side of the sidecar's single login handler, and the one way the UI asks
 * for AWS credentials (`ensureLogin`). The sidecar opens the browser itself
 * only when something needs it right away (Devo opening with the session
 * expired, a tunnel whose credentials expired); the background renewal only
 * reports sessions it couldn't renew. This module reflects that:
 *
 * - `loginActive`: SSO sessions whose browser login is open right now
 *   (`sso.session.login_started` / `login_finished`), with their sign-in
 *   page in `loginUrls` so the banner can open it again
 * - `loginNeeded`: sessions the background renewal couldn't renew, or
 *   that an expired tunnel needs while the browser may not open by itself
 *   (`profile.needs_login`), or whose login failed. The banner offers a
 *   "Log in" button for them.
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
 * "Log in" button: run the sidecar's refresh-all flow on what the banner
 * shows, which renews silently what it can and opens the browser (through
 * the same handler) for the rest. Returns false if one is already running or
 * the request failed.
 *
 * It renews exactly what the banner shows: the user asked for those, whatever
 * time their credentials have left.
 */
export async function startLogin(): Promise<boolean> {
  if (get(loginInProgress)) return false;
  if (retryTimer !== null) clearTimeout(retryTimer);
  retryTimer = null;
  loginInProgress.set(true);
  loginError.set(null);
  loginTimeout = setTimeout(finishLogin, LOGIN_TIMEOUT_MS);
  try {
    await profilesApi.refreshAll(false, { allowBrowser: true, targets: loginTargets() });
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

/** The banner's profiles, plus the sessions it only knows by name. */
function loginTargets(): { profiles: string[]; sessions: string[] } {
  const needed = get(loginNeeded);
  return {
    profiles: Object.values(needed).flat(),
    sessions: Object.entries(needed)
      .filter(([, names]) => names.length === 0)
      .map(([session]) => session),
  };
}

const ensuring = new Map<string, Promise<Set<string>>>();

/**
 * The one way a page asks for credentials it needs (a tunnel to start, a
 * registry to log in to): renews `profiles`, silently where their SSO session
 * still works and through the browser login where it doesn't (one login per
 * session, however many ask), and resolves with the profiles that got
 * credentials. The banner shows the login while it runs. Calls for the same
 * profiles share one request. Rejects if the request itself fails.
 */
export function ensureLogin(profiles: string[]): Promise<Set<string>> {
  const wanted = [...new Set(profiles)].sort();
  const key = wanted.join("\n");
  const running = ensuring.get(key);
  if (running) return running;
  const request = renew(wanted).finally(() => ensuring.delete(key));
  ensuring.set(key, request);
  return request;
}

async function renew(wanted: string[]): Promise<Set<string>> {
  const renewed = new Set<string>();
  // A refresh already running answers on the same event: wait for it, then
  // ask once more for what it didn't cover.
  for (let round = 0; round < 2; round++) {
    const pending = wanted.filter((p) => !renewed.has(p));
    if (pending.length === 0) break;
    const finished = nextRefreshed();
    let status: string;
    try {
      ({ status } = await profilesApi.refreshAll(false, {
        allowBrowser: true,
        targets: { profiles: pending, sessions: [] },
      }));
    } catch (e) {
      finished.cancel();
      throw e;
    }
    const msg = await finished.result;
    for (const name of (msg?.names as string[] | undefined) ?? []) renewed.add(name);
    if (status !== "already_running") break;
  }
  return renewed;
}

/** The next `profile.refreshed`, or null if none comes within the login timeout. */
function nextRefreshed(): { result: Promise<WsMessage | null>; cancel: () => void } {
  let off: () => void = () => {};
  let timer: ReturnType<typeof setTimeout> | undefined;
  const result = new Promise<WsMessage | null>((resolve) => {
    off = ws.on("profile.refreshed", (msg: WsMessage) => {
      off();
      clearTimeout(timer);
      resolve(msg);
    });
    timer = setTimeout(() => {
      off();
      resolve(null);
    }, LOGIN_TIMEOUT_MS);
  });
  return {
    result,
    cancel: () => {
      off();
      clearTimeout(timer);
    },
  };
}

/**
 * The "Open the browser to sign in automatically" setting
 * (`aws_login.auto_open_browser`, on unless set to false). The sidecar acts
 * on it (at launch, and for expired tunnels); the UI only shows it.
 */
export function autoOpenBrowser(config: Record<string, unknown>): boolean {
  return (config.aws_login as Record<string, unknown> | undefined)?.auto_open_browser !== false;
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

  // The sign-in page of a login that is open, by session: the browser may
  // have opened it behind other windows, or not at all.
  const offUrl = ws.on("sso.login.url_ready", (msg: WsMessage) => {
    const session = msg.session as string | undefined;
    const url = msg.url as string | undefined;
    if (session && url) loginUrls.update((current) => ({ ...current, [session]: url }));
  });

  const offFinished = ws.on("sso.session.login_finished", (msg: WsMessage) => {
    const session = msg.session as string;
    setActive(session, false);
    loginUrls.update((current) => {
      const next = { ...current };
      delete next[session];
      return next;
    });
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
    // Added to what's there: tunnels of one session can expire one by one.
    loginNeeded.update((current) => {
      const next = { ...current };
      for (const [session, names] of Object.entries(bySession)) {
        next[session] = [...new Set([...(current[session] ?? []), ...names])];
      }
      return next;
    });
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
    offUrl();
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
  loginUrls.set({});
  loginError.set(null);
  ensuring.clear();
}
