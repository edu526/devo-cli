import type { ProfileRecord } from "./api";

/**
 * Whether the profile's credentials should be renewed now. The sidecar
 * decides (`needs_renewal`), with the same threshold its background renewal
 * and refresh-all use, so the UI never disagrees with them about what is stale.
 */
export function needsRefresh(profile: ProfileRecord): boolean {
  return profile.needs_renewal === true;
}

export function anyNeedsRefresh(profiles: ProfileRecord[]): boolean {
  return profiles.some(needsRefresh);
}
