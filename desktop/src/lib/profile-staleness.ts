import type { ProfileRecord } from "./api";

/**
 * Same rule the sidecar uses to decide what a refresh should touch: expired,
 * unknown, or expiring within 10 minutes (`check_profile_needs_refresh`).
 */
const REFRESH_WITHIN_SECONDS = 10 * 60;

export function needsRefresh(profile: ProfileRecord): boolean {
  if (profile.status === "expired" || profile.status === "unknown") return true;
  return profile.seconds_remaining !== null && profile.seconds_remaining <= REFRESH_WITHIN_SECONDS;
}

export function anyNeedsRefresh(profiles: ProfileRecord[]): boolean {
  return profiles.some(needsRefresh);
}
