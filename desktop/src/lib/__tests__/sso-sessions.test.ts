import { describe, it, expect } from "vitest";
import type { ProfileRecord } from "../api";
import { formatTimeLeft, sessionActive, sessionsFromProfiles } from "../sso-sessions";

const profile = (overrides: Partial<ProfileRecord>): ProfileRecord => ({
  name: "p",
  source: "sso",
  expiration: null,
  seconds_remaining: 7200,
  status: "valid",
  is_default: false,
  sso_session: "corp",
  sso_token: { status: "valid", expiration: null, seconds_remaining: 720 },
  ...overrides,
});

describe("sessionsFromProfiles", () => {
  it("groups profiles by SSO session with the session's token state", () => {
    const sessions = sessionsFromProfiles([
      profile({ name: "dev" }),
      profile({ name: "prod", status: "expired", seconds_remaining: 0, needs_renewal: true }),
      profile({ name: "other", sso_session: "acme", sso_token: { status: "expired", expiration: null, seconds_remaining: 0 } }),
    ]);

    expect(sessions).toEqual([
      { name: "acme", status: "expired", secondsRemaining: 0, profiles: ["other"], stale: [] },
      { name: "corp", status: "valid", secondsRemaining: 720, profiles: ["dev", "prod"], stale: ["prod"] },
    ]);
  });

  it("leaves out profiles without a session", () => {
    expect(sessionsFromProfiles([profile({ sso_session: null })])).toEqual([]);
  });

  it("treats a missing token as no session", () => {
    expect(sessionsFromProfiles([profile({ sso_token: null })])[0]?.status).toBe("missing");
  });
});

describe("sessionActive", () => {
  it("is active while the token is valid or expiring", () => {
    const [session] = sessionsFromProfiles([profile({})]);
    expect(sessionActive(session!)).toBe(true);
    expect(sessionActive({ ...session!, status: "expired" })).toBe(false);
  });
});

describe("formatTimeLeft", () => {
  it("reads naturally", () => {
    expect(formatTimeLeft(30)).toBe("less than a minute");
    expect(formatTimeLeft(720)).toBe("12 min");
    expect(formatTimeLeft(3600)).toBe("1 h");
    expect(formatTimeLeft(4800)).toBe("1 h 20 min");
    expect(formatTimeLeft(null)).toBe("");
  });
});
