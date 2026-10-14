import { describe, expect, it } from "vitest";
import type { ProfileRecord } from "../api";
import { anyNeedsRefresh, needsRefresh } from "../profile-staleness";

function p(needs_renewal: boolean | undefined): ProfileRecord {
  return { name: "x", source: "sso", expiration: null, seconds_remaining: 3600, status: "valid", is_default: false, needs_renewal };
}

describe("profile-staleness", () => {
  it("follows the sidecar's decision", () => {
    expect(needsRefresh(p(true))).toBe(true);
    expect(needsRefresh(p(false))).toBe(false);
  });

  it("assumes nothing when the sidecar didn't say", () => {
    expect(needsRefresh(p(undefined))).toBe(false);
  });

  it("anyNeedsRefresh", () => {
    expect(anyNeedsRefresh([])).toBe(false);
    expect(anyNeedsRefresh([p(false), p(false)])).toBe(false);
    expect(anyNeedsRefresh([p(false), p(true)])).toBe(true);
  });
});
