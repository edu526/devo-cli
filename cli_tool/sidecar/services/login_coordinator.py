"""The one place where the sidecar starts an AWS SSO browser login.

Everything that may need a login goes through here: SSM tunnels whose
credentials expired, the background renewal, Refresh / Refresh All, the
"Log in" banner, CodeArtifact and the account-discovery wizard. That gives:

- one login per SSO session at a time: a request for a session that is
  already logging in joins that attempt instead of opening another tab
  (profiles of the same session share one SSO token)
- every requester still sees the `sso.login.*` events it always listened
  to, re-published with its own `profile`/`source`, so the existing UI
  flows keep working unchanged
- the browser only opens when it is really needed: before running
  `aws sso login` (which always opens it) the attempt first tries to renew
  silently, unless the caller just found the session dead itself
- a backoff for *automatic* requests (expired tunnels, background renewal):
  when an automatic login is not completed (tab ignored, cancelled, timed
  out) the next automatic one for that session waits 15 min, then 30, up to
  2 h — so nobody comes back to a pile of login tabs. Explicit requests
  (the user clicked something) are never held back.
- `sso.session.login_started` / `sso.session.login_finished` events that the
  UI uses for a single banner and a single notification per session
- after a successful login, the other profiles of that session are renewed
  silently right away, so tunnels reconnect and stale states clear at once.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from cli_tool.sidecar.state import EventHub

logger = logging.getLogger(__name__)

_AUTO_FIRST_BACKOFF = 15 * 60
_AUTO_MAX_BACKOFF = 2 * 60 * 60

# Possible results of request_login()
STARTED = "started"
JOINED = "joined"
SUPPRESSED = "suppressed"


@dataclass
class _Attempt:
    key: str
    requesters: set = field(default_factory=set)  # {(profile_or_session, source)}
    done: threading.Event = field(default_factory=threading.Event)
    success: Optional[bool] = None
    last_events: dict = field(default_factory=dict)  # event name -> last payload


_lock = threading.Lock()
_running: dict[str, _Attempt] = {}
# session key -> (monotonic time the next automatic attempt is allowed, current delay)
_auto_backoff: dict[str, tuple[float, float]] = {}


def session_key_for(profile: Optional[str] = None, sso_session: Optional[str] = None) -> str:
    """SSO session a login belongs to: the `[sso-session]` name, else the
    legacy start URL, else the profile name itself."""
    if sso_session:
        return sso_session
    from cli_tool.commands.aws_login.core.config import get_profile_config

    cfg = (get_profile_config(profile) or {}) if profile else {}
    return cfg.get("sso_session") or cfg.get("sso_start_url") or profile or ""


def is_running(key: str) -> bool:
    with _lock:
        return key in _running


class _FanoutHub:
    """Hub handed to run_sso_login_sync for one attempt. `sso.login.*` events
    are re-published once per requester with that requester's profile/source,
    and remembered so a late joiner can be caught up."""

    def __init__(self, hub: EventHub, attempt: _Attempt):
        self._hub = hub
        self._attempt = attempt

    def publish(self, event: str, payload: dict[str, Any]) -> None:
        if not event.startswith("sso.login."):
            self._hub.publish(event, payload)
            return
        with _lock:
            self._attempt.last_events[event] = payload
            requesters = list(self._attempt.requesters)
        for who, source in requesters:
            self._hub.publish(event, {**payload, "profile": who, "source": source})


def _auto_allowed(key: str) -> bool:
    entry = _auto_backoff.get(key)
    return entry is None or time.monotonic() >= entry[0]


def _record_result(key: str, success: bool, automatic: bool) -> None:
    if success:
        _auto_backoff.pop(key, None)
    elif automatic:
        previous = _auto_backoff.get(key, (0.0, 0.0))[1]
        delay = min(_AUTO_MAX_BACKOFF, previous * 2 if previous else _AUTO_FIRST_BACKOFF)
        _auto_backoff[key] = (time.monotonic() + delay, delay)


def request_login(
    hub: EventHub,
    *,
    source: str,
    automatic: bool,
    profile: Optional[str] = None,
    sso_session: Optional[str] = None,
    known_expired: bool = False,
) -> tuple[str, Optional[_Attempt]]:
    """Ask for a login for the SSO session of `profile` (or the named
    `sso_session`). Never blocks. Returns (STARTED | JOINED | SUPPRESSED, attempt).

    The attempt opens the browser only if the session can't be renewed
    silently; pass `known_expired=True` when the caller has just checked that.
    """
    who = profile or sso_session
    if not who:
        raise ValueError("request_login needs a profile or an sso_session")
    key = session_key_for(profile, sso_session)

    with _lock:
        attempt = _running.get(key)
        if attempt is not None:
            attempt.requesters.add((who, source))
            catch_up = dict(attempt.last_events)
            status = JOINED
        else:
            if automatic and not _auto_allowed(key):
                logger.info("Automatic login for '%s' held back (recent attempt not completed)", key)
                return SUPPRESSED, None
            attempt = _Attempt(key=key, requesters={(who, source)})
            _running[key] = attempt
            catch_up = {}
            status = STARTED

    if status == JOINED:
        logger.info("Login for session '%s' already in progress; %s/%s joins it", key, source, who)
        for event in ("sso.login.started", "sso.login.url_ready"):
            if event in catch_up:
                hub.publish(event, {**catch_up[event], "profile": who, "source": source})
        return status, attempt

    threading.Thread(
        target=_run_attempt,
        args=(hub, attempt, profile, sso_session, source, automatic, known_expired),
        daemon=True,
        name=f"sso-login-{key}",
    ).start()
    return status, attempt


def login_and_wait(
    hub: EventHub,
    *,
    source: str,
    profile: Optional[str] = None,
    sso_session: Optional[str] = None,
    known_expired: bool = False,
    timeout: Optional[float] = 300,
) -> bool:
    """Explicit (user-initiated) login that blocks until the attempt ends.
    Joins a login already in progress for the same session."""
    _status, attempt = request_login(
        hub,
        source=source,
        automatic=False,
        profile=profile,
        sso_session=sso_session,
        known_expired=known_expired,
    )
    if attempt is None:
        return False
    attempt.done.wait(timeout)
    return bool(attempt.success)


def _run_attempt(
    hub: EventHub,
    attempt: _Attempt,
    profile: Optional[str],
    sso_session: Optional[str],
    source: str,
    automatic: bool,
    known_expired: bool = False,
) -> None:
    from cli_tool.sidecar.services import sso_service

    key = attempt.key
    fanout = _FanoutHub(hub, attempt)
    success = False
    renewed: list[str] = []
    try:
        if not known_expired and _renewable_without_browser(profile, sso_session):
            # The session is still alive: no browser needed. Report success on
            # the same event the requesters wait for, so their flows go on.
            logger.info("Session '%s' renewed without a browser login", key)
            success = True
            fanout.publish(
                "sso.login.completed",
                {"profile": profile or sso_session, "source": source, "success": True, "browser": False},
            )
        else:
            hub.publish(
                "sso.session.login_started",
                {"session": key, "source": source, "automatic": automatic},
            )
            success = sso_service.run_sso_login_sync(
                fanout,
                profile or sso_session,
                source=source,
                sso_session=None if profile else sso_session,
            )
        if success:
            renewed = _renew_session_profiles(key)
    except Exception:
        logger.exception("SSO login for session '%s' failed", key)
    finally:
        with _lock:
            sources = {s for _w, s in attempt.requesters}
            # An explicit requester joining an automatic attempt makes it count
            # as explicit: a failure must not hold back the user's next click.
            _record_result(key, success, automatic and all(s in ("connection", "auto_renew") for s in sources))
            attempt.success = success
            _running.pop(key, None)
        attempt.done.set()
        hub.publish(
            "sso.session.login_finished",
            {"session": key, "success": success, "renewed": renewed},
        )


def _renewable_without_browser(profile: Optional[str], sso_session: Optional[str]) -> bool:
    """True if the session works without a new browser login: the profile's
    credentials can be (re)obtained silently, or — for a session-only login —
    its cached SSO token is still valid."""
    try:
        if profile:
            from cli_tool.commands.aws_login.commands.refresh import _silent_refresh_profiles

            renewed, _failing = _silent_refresh_profiles([(profile, "pre-login")])
            return bool(renewed)

        from cli_tool.commands.aws_login.core.config import get_existing_sso_sessions
        from cli_tool.commands.aws_login.core.credentials import get_sso_cache_token

        start_url = (get_existing_sso_sessions().get(sso_session) or {}).get("sso_start_url")
        return bool(start_url and get_sso_cache_token(start_url))
    except Exception:
        logger.exception("Could not check whether '%s' needs a login", profile or sso_session)
        return False


def _renew_session_profiles(key: str) -> list[str]:
    """After a login, renew every SSO profile of that session silently (the
    new SSO token makes it a quick STS call each). Best effort."""
    try:
        from cli_tool.commands.aws_login.commands.refresh import _silent_refresh_profiles
        from cli_tool.commands.aws_login.core.config import list_aws_profiles

        names = [n for n, src in list_aws_profiles() if src in ("sso", "both") and session_key_for(n) == key]
        if not names:
            return []
        renewed, _failing = _silent_refresh_profiles([(n, "login") for n in names])
        return renewed
    except Exception:
        logger.exception("Renewing the profiles of session '%s' after login failed", key)
        return []


def _reset_for_tests() -> None:
    with _lock:
        _running.clear()
        _auto_backoff.clear()
