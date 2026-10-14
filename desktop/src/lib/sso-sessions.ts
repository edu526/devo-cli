import type { ProfileRecord, SsoTokenInfo } from "./api";
import { needsRefresh } from "./profile-staleness";

/**
 * An SSO session as the Profiles page shows it. While its token is valid,
 * Devo renews the profiles' credentials in the background; once it expires,
 * only a browser login can — some organizations end it minutes after each
 * login, so it is worth showing.
 */
export interface SessionSummary {
  name: string;
  status: SsoTokenInfo["status"];
  secondsRemaining: number | null;
  profiles: string[];
  /** Profiles of the session that need new credentials now. */
  stale: string[];
}

/** The SSO sessions of `profiles`, from the token info each profile carries. */
export function sessionsFromProfiles(profiles: ProfileRecord[]): SessionSummary[] {
  const byName = new Map<string, SessionSummary>();
  for (const p of profiles) {
    if (!p.sso_session) continue;
    let session = byName.get(p.sso_session);
    if (!session) {
      session = {
        name: p.sso_session,
        status: p.sso_token?.status ?? "missing",
        secondsRemaining: p.sso_token?.seconds_remaining ?? null,
        profiles: [],
        stale: [],
      };
      byName.set(p.sso_session, session);
    }
    session.profiles.push(p.name);
    if (needsRefresh(p)) session.stale.push(p.name);
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export function sessionActive(session: SessionSummary): boolean {
  return session.status === "valid" || session.status === "expiring";
}

/** "12 min", "1 h 20 min", "less than a minute". */
export function formatTimeLeft(seconds: number | null): string {
  if (seconds === null) return "";
  if (seconds < 60) return "less than a minute";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}
