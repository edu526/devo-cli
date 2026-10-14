import { describe, it, expect } from "vitest";
import type { ProfileRecord } from "../api";
import { profileStatusLabel, profileTarget, profileTimeText } from "../profile-display";

const NOW = Date.parse("2026-10-14T12:00:00Z");

const profile = (overrides: Partial<ProfileRecord>): ProfileRecord => ({
  name: "dev",
  source: "sso",
  expiration: null,
  seconds_remaining: null,
  status: "valid",
  is_default: false,
  ...overrides,
});

describe("profileStatusLabel", () => {
  it("says what an unknown status means", () => {
    expect(profileStatusLabel("unknown")).toBe("Not signed in");
    expect(profileStatusLabel("expiring")).toBe("Expiring");
  });
});

describe("profileTimeText", () => {
  it("tells how long valid credentials have left", () => {
    expect(profileTimeText(profile({ status: "valid", seconds_remaining: 12000 }), NOW)).toBe("3 h 20 min left");
    expect(profileTimeText(profile({ status: "expiring", seconds_remaining: 540 }), NOW)).toBe("9 min left");
  });

  it("tells how long ago expired credentials ran out", () => {
    const p = profile({ status: "expired", seconds_remaining: 0, expiration: "2026-10-14T11:30:00Z" });
    expect(profileTimeText(p, NOW)).toBe("30 min ago");
  });

  it("has nothing to tell without credentials or times", () => {
    expect(profileTimeText(profile({ status: "unknown" }), NOW)).toBe("");
    expect(profileTimeText(profile({ status: "expired", expiration: null }), NOW)).toBe("");
  });
});

describe("profileTarget", () => {
  it("names the role and account the profile signs in to", () => {
    expect(profileTarget(profile({ role_name: "Developer", account_id: "111122223333" }))).toBe(
      "Developer · 111122223333",
    );
    expect(profileTarget(profile({ account_id: "111122223333" }))).toBe("111122223333");
    expect(profileTarget(profile({}))).toBe("");
  });
});
