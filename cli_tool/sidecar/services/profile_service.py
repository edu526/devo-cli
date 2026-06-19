"""Profile expiration monitoring — emits profile.expiring events via EventHub."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from cli_tool.commands.aws_login.core.config import list_aws_profiles
from cli_tool.commands.aws_login.core.credentials import get_profile_credentials_expiration
from cli_tool.sidecar.state import EventHub

_WARN_SECONDS = 5 * 60  # emit once when crossing below 5 minutes
_POLL_INTERVAL = 30  # seconds between polls
# ponytail: 8 workers caps concurrency for aws configure export-credentials subprocess calls
_MAX_WORKERS = 8


def _build_profile_info(name: str, src: str, default_name: str | None, now: datetime) -> dict[str, Any]:
    """Build the info dict for one profile. Shared by list and single-profile paths."""
    expiration = get_profile_credentials_expiration(name)
    seconds_remaining = None
    status = "unknown"
    if expiration:
        diff = (expiration - now).total_seconds()
        seconds_remaining = max(0, int(diff))
        if diff <= 0:
            status = "expired"
        elif diff <= _WARN_SECONDS:
            status = "expiring"
        else:
            status = "valid"
    return {
        "name": name,
        "source": src,
        "expiration": expiration.isoformat() if expiration else None,
        "seconds_remaining": seconds_remaining,
        "status": status,
        "is_default": name == default_name,
    }


def get_profiles_info() -> list[dict[str, Any]]:
    """Return all SSO profiles with live expiration info."""
    from cli_tool.core.utils.config_manager import get_config_value

    default_name = get_config_value("aws_login.default_credentials_profile")

    try:
        profiles = list_aws_profiles()
    except Exception:
        return []

    sso_profiles = [(name, src) for name, src in profiles if src in ("sso", "both")]
    now = datetime.now(timezone.utc)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        return list(ex.map(lambda ns: _build_profile_info(ns[0], ns[1], default_name, now), sso_profiles))


def get_profile_info(name: str) -> dict[str, Any] | None:
    """Return a single SSO profile with live expiration info, or None if not found."""
    from cli_tool.core.utils.config_manager import get_config_value

    default_name = get_config_value("aws_login.default_credentials_profile")
    try:
        profiles = list_aws_profiles()
    except Exception:
        return None

    for prof_name, src in profiles:
        if prof_name == name and src in ("sso", "both"):
            return _build_profile_info(name, src, default_name, datetime.now(timezone.utc))
    return None


def create_profile(
    name: str,
    sso_start_url: str,
    sso_region: str,
    sso_account_id: str,
    sso_role_name: str,
    region: str,
    output: str = "json",
) -> dict[str, Any]:
    """Append a new SSO profile to ~/.aws/config and return its info record.

    Raises ValueError on validation failure or name collision; the router
    translates that into a 409.
    """
    from cli_tool.commands.aws_login.core.config import add_profile_to_config

    add_profile_to_config(
        profile_name=name,
        sso_start_url=sso_start_url,
        sso_region=sso_region,
        sso_account_id=sso_account_id,
        sso_role_name=sso_role_name,
        region=region,
        output=output,
    )
    info = get_profile_info(name)
    if info is not None:
        return info
    # Defensive fallback: the new profile may not appear in `list_aws_profiles`
    # yet if the FS layer hasn't re-read, so build a minimal record by hand.
    return {
        "name": name,
        "source": "sso",
        "expiration": None,
        "seconds_remaining": None,
        "status": "unknown",
        "is_default": False,
    }


async def watch_profiles(hub: EventHub) -> None:
    """Background asyncio task: poll expirations and emit profile.expiring events."""
    warned: set[str] = set()
    while True:
        await asyncio.sleep(_POLL_INTERVAL)
        _tick(hub, warned)


def _tick(hub: EventHub, warned: set[str]) -> None:
    """Single iteration of the watch loop. Exposed for unit tests."""
    try:
        profiles = get_profiles_info()
    except Exception:
        return
    for p in profiles:
        name = p["name"]
        secs = p.get("seconds_remaining")
        if secs is None:
            continue
        if secs <= _WARN_SECONDS and name not in warned:
            warned.add(name)
            hub.publish(
                "profile.expiring",
                {
                    "name": name,
                    "seconds_remaining": secs,
                },
            )
        elif secs > _WARN_SECONDS and name in warned:
            warned.discard(name)
