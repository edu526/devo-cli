import type { ProfileRecord } from "./api";
import { formatTimeLeft } from "./sso-sessions";

const STATUS_LABELS: Record<ProfileRecord["status"], string> = {
  valid: "Valid",
  expiring: "Expiring",
  expired: "Expired",
  // No cached credentials: nothing signed this profile in yet (or since a cleanup)
  unknown: "Not signed in",
};

export function profileStatusLabel(status: ProfileRecord["status"]): string {
  return STATUS_LABELS[status] ?? status;
}

/** "3 h 20 min left", "30 min ago" (expired), or "" when there is nothing to tell. */
export function profileTimeText(profile: ProfileRecord, now = Date.now()): string {
  if (profile.status === "valid" || profile.status === "expiring") {
    return profile.seconds_remaining === null ? "" : `${formatTimeLeft(profile.seconds_remaining)} left`;
  }
  if (profile.status === "expired" && profile.expiration) {
    const ago = Math.round((now - new Date(profile.expiration).getTime()) / 1000);
    return Number.isFinite(ago) && ago >= 0 ? `${formatTimeLeft(ago)} ago` : "";
  }
  return "";
}

/** "Developer · 111122223333", or whichever of the two is known. */
export function profileTarget(profile: ProfileRecord): string {
  return [profile.role_name, profile.account_id].filter(Boolean).join(" · ");
}
