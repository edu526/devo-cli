import { derived, writable } from "svelte/store";
import { connectionsApi } from "./api";
import { connectionsCache } from "./page-stores";
import { loginNeeded } from "./stores";
import { ws, type WsMessage } from "./ws";

/**
 * Problems the sidebar points at, whatever page is open: a failed tunnel,
 * a tunnel or SSO session waiting for a login. The pages only track this
 * while they are shown.
 */
export interface NavAlert {
  level: "error" | "warning";
  text: string;
}

/** Each tunnel's last known state. */
export const tunnelStates = writable<Record<string, string>>({});

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function databasesAlertFor(states: Record<string, string>): NavAlert | null {
  const all = Object.values(states);
  const failed = all.filter((s) => s === "error").length;
  if (failed > 0) return { level: "error", text: `${plural(failed, "tunnel", "tunnels")} failed` };
  const waiting = all.filter((s) => s === "expired_credentials").length;
  if (waiting > 0) return { level: "warning", text: `${plural(waiting, "tunnel needs", "tunnels need")} a login` };
  return null;
}

export function profilesAlertFor(needed: Record<string, string[]>): NavAlert | null {
  const sessions = Object.keys(needed).length;
  if (sessions === 0) return null;
  return { level: "warning", text: `AWS login required (${plural(sessions, "session", "sessions")})` };
}

export const databasesAlert = derived(tunnelStates, databasesAlertFor);
export const profilesAlert = derived(loginNeeded, profilesAlertFor);

async function reload(): Promise<void> {
  try {
    const list = await connectionsApi.list();
    tunnelStates.set(Object.fromEntries(list.map((c) => [c.name, c.state])));
  } catch {
    // The sidecar is unreachable; the next event brings the state back.
  }
}

/** Keep `tunnelStates` current from the sidecar's events. Returns a stop function. */
export function startNavStatus(): () => void {
  void reload();
  const setState = (msg: WsMessage) => {
    const name = msg.name as string | undefined;
    const state = msg.state as string | undefined;
    if (name && state) tunnelStates.update((s) => (s[name] === state ? s : { ...s, [name]: state }));
  };
  const offState = ws.on("connection.state_changed", setState);
  const offMetrics = ws.on("connection.metrics", setState);
  const offSync = ws.on("connections.sync", () => void reload());
  // The Databases page re-reads the full list now and then: take it too.
  const offCache = connectionsCache.subscribe((list) => {
    if (list) tunnelStates.set(Object.fromEntries(list.map((c) => [c.name, c.state])));
  });
  return () => {
    offState();
    offMetrics();
    offSync();
    offCache();
  };
}
