"""Profile expiration monitoring — emits profile.expiring events via EventHub."""

import asyncio
import json
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from cli_tool.commands.aws_login.core.config import (
    get_existing_sso_sessions,
    list_aws_profiles,
)
from cli_tool.commands.aws_login.core.credentials import (
    get_profile_credentials_expiration,
    read_cached_credentials_expiration,
)
from cli_tool.sidecar.state import EventHub

logger = logging.getLogger(__name__)

_WARN_SECONDS = 5 * 60  # emit once when crossing below 5 minutes
_POLL_INTERVAL = 30  # seconds between polls
_FIRST_POLL_DELAY = 3  # first poll right after startup, so stale credentials are renewed at once
_RENEW_BEFORE_SECONDS = 15 * 60  # renew credentials that expire within this window
_RENEW_RETRY_COOLDOWN = 5 * 60  # don't retry a failed silent renewal sooner than this
_DEFAULT_SYNC_INTERVAL_SECONDS = 10 * 60  # resync [default] on this cadence
# ponytail: 8 workers caps concurrency for aws configure export-credentials subprocess calls
_MAX_WORKERS = 8


def _build_profile_info(name: str, src: str, default_name: str | None, now: datetime) -> dict[str, Any]:
    """Build the info dict for one profile. Shared by list and single-profile paths."""
    # Fast path: the AWS CLI's own credential cache (a file read). Only when
    # there is no cache entry do we fall back to spawning `aws`, which is ~2 s
    # per profile but can also create the credentials.
    expiration = read_cached_credentials_expiration(name) or get_profile_credentials_expiration(name)
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

    sso_token = _get_sso_token_info(name)
    sso_session = _get_sso_session_name(name)
    return {
        "name": name,
        "source": src,
        "expiration": expiration.isoformat() if expiration else None,
        "seconds_remaining": seconds_remaining,
        "status": status,
        "is_default": name == default_name,
        "sso_token": sso_token,
        "sso_session": sso_session,
    }


def _get_sso_session_name(profile_name: str) -> str | None:
    """Return the [sso-session] name referenced by this profile, if any."""
    from cli_tool.commands.aws_login.core.config import get_profile_config

    cfg = get_profile_config(profile_name)
    if not cfg:
        return None
    # The config has either `sso_session = NAME` (modern) or inline
    # `sso_start_url` (legacy). Both resolve to the same SSO session.
    return cfg.get("sso_session") or cfg.get("sso_start_url")


def _get_sso_token_info(profile_name: str) -> dict[str, Any] | None:
    """Read the underlying SSO access token expiration from ~/.aws/sso/cache/.

    The SSO access token (~1h TTL) is what boto3 uses internally to refresh
    the longer-lived AWS temporary credentials (~12h TTL). They expire
    independently — this lets the UI warn about SSO expiry separately.
    """
    from cli_tool.commands.aws_login.core.config import get_profile_config
    from cli_tool.commands.aws_login.core.credentials import get_sso_token_expiration

    cfg = get_profile_config(profile_name)
    if not cfg:
        return None
    sso_start_url = cfg.get("sso_start_url")
    if not sso_start_url:
        return None
    expires = get_sso_token_expiration(sso_start_url)
    if not expires:
        return {"status": "missing", "expiration": None, "seconds_remaining": None}

    now = datetime.now(timezone.utc)
    diff = (expires - now).total_seconds()
    if diff <= 0:
        status = "expired"
    elif diff <= _WARN_SECONDS:
        status = "expiring"
    else:
        status = "valid"

    return {
        "status": status,
        "expiration": expires.isoformat(),
        "seconds_remaining": max(0, int(diff)),
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


def list_sso_sessions_info() -> list[dict[str, Any]]:
    """Return one entry per unique SSO session referenced by SSO profiles.

    Each entry: {session, start_url, region, status, expiration, seconds_remaining,
    profile_count}. Profiles that share an [sso-session] (or legacy
    sso_start_url) are deduped so the UI can show a single SSO refresh button
    per session instead of one per profile.
    """
    from datetime import timezone as _tz

    from cli_tool.commands.aws_login.core.config import get_existing_sso_sessions, list_aws_profiles
    from cli_tool.commands.aws_login.core.credentials import get_sso_token_expiration

    try:
        profiles = list_aws_profiles()
    except Exception:
        profiles = []

    # Bucket profiles by session key (prefer [sso-session] name, fallback to start URL)
    by_session: dict[str, list[str]] = {}
    profile_session: dict[str, str] = {}
    for name, src in profiles:
        if src not in ("sso", "both"):
            continue
        session = _get_sso_session_name(name)
        if not session:
            continue
        by_session.setdefault(session, []).append(name)
        profile_session[name] = session

    # Pull region/start_url from the [sso-session] blocks if available
    try:
        sso_session_blocks = get_existing_sso_sessions()
    except Exception:
        sso_session_blocks = {}

    now = datetime.now(_tz.utc)
    sessions: list[dict[str, Any]] = []
    for session_key, profile_names in by_session.items():
        block = sso_session_blocks.get(session_key, {})
        start_url = block.get("sso_start_url", session_key)
        region = block.get("sso_region", "")
        expires = get_sso_token_expiration(start_url)
        if expires:
            diff = (expires - now).total_seconds()
            seconds_remaining = max(0, int(diff))
            if diff <= 0:
                status = "expired"
            elif diff <= _WARN_SECONDS:
                status = "expiring"
            else:
                status = "valid"
        else:
            seconds_remaining = None
            status = "missing"

        sessions.append(
            {
                "session": session_key,
                "start_url": start_url,
                "region": region,
                "status": status,
                "expiration": expires.isoformat() if expires else None,
                "seconds_remaining": seconds_remaining,
                "profile_count": len(profile_names),
                "profiles": profile_names,
            }
        )

    return sorted(sessions, key=lambda s: s["session"].lower())


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
            from cli_tool.sidecar.services import login_coordinator

            login_coordinator.login_and_wait(hub, sso_session=session_name, source="discover", known_expired=True, timeout=200)

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
    """Background asyncio task: keep credentials fresh and emit profile events.

    Each iteration runs in a worker thread: it can spend seconds on `aws`
    subprocesses, and run inline it would freeze the whole sidecar (every API
    request and WebSocket ping) for that long.
    """
    warned: set[str] = set()
    last_default_sync: dict[str, datetime] = {}
    renew_state: dict[str, Any] = {}
    await asyncio.sleep(_FIRST_POLL_DELAY)
    while True:
        try:
            last_default_sync = await asyncio.to_thread(_tick, hub, warned, last_default_sync, renew_state)
        except Exception:
            logger.exception("profile watch iteration failed")
        await asyncio.sleep(_POLL_INTERVAL)


def _session_key(profile: dict[str, Any]) -> str:
    return profile.get("sso_session") or profile["name"]


def _needs_renewal(profile: dict[str, Any]) -> bool:
    secs = profile.get("seconds_remaining")
    return profile.get("status") in ("expired", "unknown") or (secs is not None and secs <= _RENEW_BEFORE_SECONDS)


def _auto_renew(hub: EventHub, profiles: list[dict[str, Any]], state: dict[str, Any]) -> bool:
    """Silently renew credentials that expired or are about to, without a browser.

    This is what keeps the app hands-off: profiles are renewed in the
    background for as long as Devo is open. Listing no longer renews them as a
    side effect (it reads the AWS CLI cache), so it is done here explicitly.

    When a whole SSO session can't be renewed silently, the shared login
    handler opens the browser login for it (also with the window hidden). If
    the handler holds the login back — a recent automatic login for that
    session was not completed — a single `profile.needs_login` event is
    published instead, so the UI can offer a "Log in" button. Failing profiles
    are not retried silently for `_RENEW_RETRY_COOLDOWN` unless the session's
    SSO token becomes valid again (the user logged in), and sessions with a
    login in progress are skipped. Disable with `aws_login.auto_renew = false`.

    `state` is the caller's memory between calls. Returns True when at least
    one profile was renewed (the caller should re-read the profile info).
    """
    from cli_tool.core.utils.config_manager import get_config_value

    if get_config_value("aws_login.auto_renew", True) is False:
        return False

    from cli_tool.commands.aws_login.commands.refresh import _silent_refresh_profiles
    from cli_tool.sidecar.services import login_coordinator

    now = datetime.now(timezone.utc)
    retry_after: dict[str, datetime] = state.setdefault("retry_after", {})
    notified: set[str] = state.setdefault("notified", set())

    def blocked(p: dict[str, Any]) -> bool:
        if login_coordinator.is_running(_session_key(p)):
            return True  # a login is already getting this session back
        until = retry_after.get(p["name"])
        session_alive = (p.get("sso_token") or {}).get("status") == "valid"
        return until is not None and until > now and not session_alive

    recovered: set[str] = set()
    for p in profiles:
        if (p.get("sso_token") or {}).get("status") == "valid" and _session_key(p) in notified:
            recovered.add(_session_key(p))

    todo = [(p["name"], "stale") for p in profiles if _needs_renewal(p) and not blocked(p)]
    renewed: list[str] = []
    failing: list[tuple[str, str]] = []
    by_name = {p["name"]: p for p in profiles}
    if todo:
        renewed, failing = _silent_refresh_profiles(todo)

    renewed_sessions = {_session_key(by_name[n]) for n in renewed}
    for name in renewed:
        retry_after.pop(name, None)

    # Sessions we had reported as needing a login that work again (renewed, or
    # the user logged in): tell the UI so it can drop its "login required" notice.
    recovered |= renewed_sessions & notified
    if recovered:
        notified.difference_update(recovered)
        hub.publish("profile.login_resolved", {"sessions": sorted(recovered)})

    if not todo:
        return False

    dead_sessions: dict[str, list[str]] = {}
    for name, _reason in failing:
        retry_after[name] = now + timedelta(seconds=_RENEW_RETRY_COOLDOWN)
        key = _session_key(by_name[name])
        # A session where something did renew is alive: that failure is about
        # the profile itself, not something a login would fix.
        if key not in renewed_sessions:
            dead_sessions.setdefault(key, []).append(name)

    held_back: dict[str, list[str]] = {}
    for key, names in dead_sessions.items():
        status, _attempt = login_coordinator.request_login(hub, profile=names[0], source="auto_renew", automatic=True, known_expired=True)
        logger.info("auto-renew: session '%s' needs a login: %s", key, status)
        if status == login_coordinator.SUPPRESSED and key not in notified:
            held_back[key] = names
        notified.add(key)

    if held_back:
        hub.publish(
            "profile.needs_login",
            {
                "sessions": sorted(held_back),
                "names": [n for names in held_back.values() for n in names],
                "by_session": {session: names for session, names in sorted(held_back.items())},
            },
        )

    if renewed:
        logger.info("auto-renew: renewed %d profile(s)", len(renewed))
    return bool(renewed)


def _tick(
    hub: EventHub,
    warned: set[str],
    last_default_sync: dict[str, datetime] | None = None,
    renew_state: dict[str, Any] | None = None,
) -> dict[str, datetime]:
    """Single iteration of the watch loop. Exposed for unit tests.

    `last_default_sync` records when [default] was last resynced, per
    profile name — see the comment below for why a low-seconds signal
    alone can't drive that resync.
    """
    from cli_tool.commands.aws_login.core.credentials import write_default_credentials

    last_default_sync = dict(last_default_sync or {})

    try:
        profiles = get_profiles_info()
    except Exception:
        return last_default_sync

    try:
        if _auto_renew(hub, profiles, renew_state if renew_state is not None else {}):
            profiles = get_profiles_info()
    except Exception:
        logger.exception("auto-renew failed")

    # Group profiles by SSO session to emit one notification per session
    sso_sessions: dict[str, dict] = {}  # session_name -> {sso_secs, profile_names}
    now = datetime.now(timezone.utc)

    for p in profiles:
        name = p["name"]
        sts_secs = p.get("seconds_remaining")
        sso_info = p.get("sso_token") or {}
        sso_secs = sso_info.get("seconds_remaining")
        sso_session = p.get("sso_session") or name  # fallback to profile name for legacy

        # 1. Keep [default] credentials in ~/.aws/credentials resynced.
        # `sts_secs` comes from `export-credentials`, which makes botocore
        # silently refresh the role credentials well before they actually
        # expire — so polling the profile is itself what keeps `sts_secs`
        # looking healthy, and it almost never drops into the warning
        # window in practice. That silent refresh only updates botocore's
        # own cache, never the static copy already written to [default],
        # so waiting for a "dying" signal here leaves [default] to expire
        # ungoverned. Resync on a fixed cadence instead, while still
        # reacting immediately if `sts_secs` does report danger (e.g.
        # right after the sidecar was closed/asleep for a while).
        if p.get("is_default") and sso_secs is not None and sso_secs > _WARN_SECONDS:
            last_sync = last_default_sync.get(name)
            due = last_sync is None or (now - last_sync).total_seconds() >= _DEFAULT_SYNC_INTERVAL_SECONDS
            dying = sts_secs is not None and sts_secs <= _WARN_SECONDS
            if due or dying:
                logger.info("Syncing default credentials for '%s'", name)
                try:
                    write_default_credentials(name)
                    last_default_sync[name] = now
                except Exception as e:
                    logger.error("Default credentials sync failed: %s", e)

        # 2. Accumulate SSO session info (one entry per unique session)
        if sso_secs is None:
            continue
        if sso_session not in sso_sessions or sso_sessions[sso_session]["sso_secs"] > sso_secs:
            sso_sessions[sso_session] = {"sso_secs": sso_secs}

    # 3. Emit/clear notifications per SSO session
    for session_name, info in sso_sessions.items():
        sso_secs = info["sso_secs"]
        if sso_secs <= _WARN_SECONDS and session_name not in warned:
            warned.add(session_name)
            hub.publish(
                "profile.expiring",
                {
                    "name": session_name,
                    "seconds_remaining": sso_secs,
                    "type": "sso",
                },
            )
        elif sso_secs > _WARN_SECONDS and session_name in warned:
            warned.discard(session_name)

    return last_default_sync
