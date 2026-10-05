import { describe, expect, it } from "vitest";
import type { ProfileRecord } from "../api";
import { anyNeedsRefresh, needsRefresh } from "../profile-staleness";

function p(status: ProfileRecord["status"], secs: number | null): ProfileRecord {
  return { name: "x", source: "sso", expiration: null, seconds_remaining: secs, status, is_default: false };
}

describe("profile-staleness", () => {
  it("expired and unknown profiles need a refresh", () => {
    expect(needsRefresh(p("expired", 0))).toBe(true);
    expect(needsRefresh(p("unknown", null))).toBe(true);
  });

  it("uses the sidecar's 10-minute window", () => {
    expect(needsRefresh(p("valid", 9 * 60))).toBe(true);
    expect(needsRefresh(p("valid", 10 * 60))).toBe(true);
    expect(needsRefresh(p("valid", 11 * 60))).toBe(false);
  });

  it("a long-valid profile does not", () => {
    expect(needsRefresh(p("valid", 3 * 3600))).toBe(false);
  });

  it("anyNeedsRefresh", () => {
    expect(anyNeedsRefresh([])).toBe(false);
    expect(anyNeedsRefresh([p("valid", 3600), p("valid", 7200)])).toBe(false);
    expect(anyNeedsRefresh([p("valid", 3600), p("expired", 0)])).toBe(true);
  });
});
