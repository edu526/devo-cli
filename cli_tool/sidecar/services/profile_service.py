"""Profile expiration monitoring — emits profile.expiring events via EventHub."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from cli_tool.commands.aws_login.core.config import list_aws_profiles
from cli_tool.commands.aws_login.core.credentials import get_profile_credentials_expiration
from cli_tool.sidecar.state import EventHub

_WARN_SECONDS = 5 * 60  # emit once when crossing below 5 minutes
_POLL_INTERVAL = 30  # seconds between polls


def get_profiles_info() -> list[dict[str, Any]]:
    """Return all SSO profiles with live expiration info."""
    from cli_tool.core.utils.config_manager import get_config_value

    default_name = get_config_value("aws_login.default_credentials_profile")

    out = []
    try:
        profiles = list_aws_profiles()
    except Exception:
        return out

    now = datetime.now(timezone.utc)
    for name, src in profiles:
        if src not in ("sso", "both"):
            continue
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
        out.append(
            {
                "name": name,
                "source": src,
                "expiration": expiration.isoformat() if expiration else None,
                "seconds_remaining": seconds_remaining,
                "status": status,
                "is_default": name == default_name,
            }
        )
    return out


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
