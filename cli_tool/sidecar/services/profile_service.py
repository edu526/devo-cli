"""Profile expiration monitoring — emits profile.expiring events via EventHub."""

import asyncio
import json
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from cli_tool.commands.aws_login.core.config import (
    get_existing_sso_sessions,
    list_aws_profiles,
)
from cli_tool.commands.aws_login.core.credentials import get_profile_credentials_expiration
from cli_tool.sidecar.state import EventHub

logger = logging.getLogger(__name__)

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
    sso_account_id: str,
    sso_role_name: str,
    region: str,
    sso_session: str | None = None,
    sso_start_url: str | None = None,
    sso_region: str | None = None,
    output: str = "json",
) -> dict[str, Any]:
    """Append a new SSO profile to ~/.aws/config and return its info record.

    Two modes (see add_profile_to_config). Raises ValueError on validation
    failure or name collision; the router translates that into a 409.
    """
    from cli_tool.commands.aws_login.core.config import add_profile_to_config

    add_profile_to_config(
        profile_name=name,
        sso_account_id=sso_account_id,
        sso_role_name=sso_role_name,
        region=region,
        output=output,
        sso_session=sso_session,
        sso_start_url=sso_start_url,
        sso_region=sso_region,
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


def list_sso_sessions() -> list[dict[str, Any]]:
    """Return SSO sessions defined in ~/.aws/config.

    Each entry: {name, sso_start_url, sso_region}. Used by the desktop
    "Add Profile" wizard to populate its session dropdown.
    """
    sessions = get_existing_sso_sessions()
    return sorted(
        (
            {
                "name": name,
                "sso_start_url": cfg.get("sso_start_url", ""),
                "sso_region": cfg.get("sso_region", ""),
            }
            for name, cfg in sessions.items()
        ),
        key=lambda s: s["name"].lower(),
    )


def _run_aws_sso_login(session_name: str) -> None:
    """Run `aws sso login --sso-session <name>`. Blocks until the user
    finishes the browser flow (or it times out)."""
    subprocess.run(
        ["aws", "sso", "login", "--sso-session", session_name],
        timeout=180,
        check=False,
    )


def _list_accounts(access_token: str, sso_region: str) -> list[dict[str, Any]]:
    """Run `aws sso list-accounts` and return the accountList."""
    result = subprocess.run(
        [
            "aws",
            "sso",
            "list-accounts",
            "--access-token",
            access_token,
            "--region",
            sso_region or "us-east-1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"list-accounts failed: {result.stderr.strip()}")
    return json.loads(result.stdout).get("accountList", [])


def _list_roles(access_token: str, account_id: str, sso_region: str) -> list[dict[str, Any]]:
    """Run `aws sso list-account-roles` for one account and return roleList."""
    result = subprocess.run(
        [
            "aws",
            "sso",
            "list-account-roles",
            "--access-token",
            access_token,
            "--account-id",
            account_id,
            "--region",
            sso_region or "us-east-1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"list-account-roles failed: {result.stderr.strip()}")
    return json.loads(result.stdout).get("roleList", [])


def _do_discover(hub: EventHub, session_name: str) -> None:
    """Background pipeline: sso login → list accounts → list roles per account.

    Publishes one of two WS events:
      * sso.discover.starting   — fires immediately, signals the browser
                                   SSO flow has begun
      * sso.discover.completed  — fires with {session, success, ...payload}
    """
    from cli_tool.commands.aws_login.core.credentials import get_sso_cache_token

    hub.publish("sso.discover.starting", {"session": session_name})

    try:
        sessions = get_existing_sso_sessions()
        cfg = sessions.get(session_name)
        if not cfg:
            raise ValueError(f"sso-session {session_name!r} not found")
        sso_start_url = cfg.get("sso_start_url", "")
        sso_region = cfg.get("sso_region", "")

        # Skip the explicit login if a valid token is already cached —
        # `aws sso login` is a no-op in that case anyway, but skipping
        # avoids spawning a subprocess and the visual "starting" flicker.
        if not get_sso_cache_token(sso_start_url):
            _run_aws_sso_login(session_name)

        access_token = get_sso_cache_token(sso_start_url)
        if not access_token:
            raise RuntimeError("SSO login did not produce a cached access token")

        accounts = _list_accounts(access_token, sso_region)
        # Fetch roles in parallel — each call is sub-second but the user
        # shouldn't wait N*30s sequentially for N accounts.
        accounts_with_roles: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_list_roles, access_token, a["accountId"], sso_region): a for a in accounts if "accountId" in a}
            for fut in futures:
                acct = futures[fut]
                try:
                    roles = fut.result()
                except Exception as exc:
                    logger.warning("list-roles for %s failed: %s", acct.get("accountId"), exc)
                    roles = []
                accounts_with_roles.append(
                    {
                        "accountId": acct.get("accountId", ""),
                        "accountName": acct.get("accountName", ""),
                        "emailAddress": acct.get("emailAddress", ""),
                        "roles": [{"roleName": r.get("roleName", "")} for r in roles],
                    }
                )

        hub.publish(
            "sso.discover.completed",
            {
                "session": session_name,
                "success": True,
                "accounts": accounts_with_roles,
            },
        )
    except Exception as exc:
        logger.exception("sso.discover failed for session %s", session_name)
        hub.publish(
            "sso.discover.completed",
            {
                "session": session_name,
                "success": False,
                "error": str(exc),
            },
        )


def start_discover(hub: EventHub, session_name: str) -> None:
    """Spawn the background discovery pipeline for a session."""
    t = threading.Thread(target=_do_discover, args=(hub, session_name), daemon=True)
    t.start()


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
