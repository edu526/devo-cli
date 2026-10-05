"""Profile management endpoints /api/v1/profiles."""

import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from cli_tool.commands.aws_login.core.config import (
    add_sso_session_to_config,
    get_profile_config,
    remove_profile_section,
)
from cli_tool.commands.aws_login.core.credentials import (
    verify_credentials,
    write_default_credentials,
)
from cli_tool.sidecar.deps import get_app_state, require_bearer
from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.services.profile_service import (
    create_profile,
    get_profile_info,
    get_profiles_info,
    list_sso_sessions,
    list_sso_sessions_info,
    start_discover,
)
from cli_tool.sidecar.state import AppState, EventHub

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["profiles"], dependencies=[Depends(require_bearer)])


def _state(request: Request) -> AppState:
    return get_app_state(request)


@router.get("")
def list_profiles() -> list[dict[str, Any]]:
    return get_profiles_info()


@router.get("/sessions")
def list_sso_sessions_endpoint() -> list[dict[str, Any]]:
    """Return SSO sessions defined in ~/.aws/config.

    Drives the session dropdown in the desktop "Add Profile" wizard.
    Declared BEFORE the `/{name}` routes so it doesn't get shadowed.
    """
    return list_sso_sessions()


@router.get("/sessions/info")
def list_sso_sessions_info_endpoint() -> list[dict[str, Any]]:
    """Return one entry per unique SSO session with token status + profile count."""
    return list_sso_sessions_info()


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_sso_session_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """Append a new `[sso-session NAME]` block to ~/.aws/config.

    Body: {name, sso_start_url, sso_region}. Returns 409 on collision,
    422 on missing fields.
    """
    required = ("name", "sso_start_url", "sso_region")
    missing = [k for k in required if not body.get(k)]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required field(s): {', '.join(missing)}",
        )
    try:
        add_sso_session_to_config(
            name=body["name"],
            sso_start_url=body["sso_start_url"],
            sso_region=body["sso_region"],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {
        "name": body["name"],
        "sso_start_url": body["sso_start_url"],
        "sso_region": body["sso_region"],
    }


@router.post(":discover", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("6/minute")
def discover_profiles(body: dict[str, Any], request: Request, response: Response) -> dict[str, Any]:
    """Kick off the SSO discovery pipeline for a session.

    Body: {session: "<sso-session name>"}. Returns 202 immediately. The
    pipeline runs in the background and reports progress via WS events
    `sso.discover.starting` and `sso.discover.completed`.
    """
    session = body.get("session")
    if not session:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required field: session",
        )
    app_state = _state(request)
    start_discover(app_state.event_hub, session)
    return {
        "status": "accepted",
        "message": f"Discovery started for session '{session}' — watch WS for sso.discover.completed",
    }


@router.get("/{name}")
def get_profile(name: str) -> dict[str, Any]:
    info = get_profile_info(name)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Profile '{name}' not found")
    return info


@router.post("", status_code=status.HTTP_201_CREATED)
def create_profile_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """Append a new SSO profile to ~/.aws/config.

    Body: {name, sso_account_id, sso_role_name, region, output?, and ONE OF:
    sso_session (reference to an existing [sso-session] block) OR
    sso_start_url + sso_region (inline legacy format)}.

    Returns 201 on success, 409 on name collision / invalid input, 422 on
    missing required fields.
    """
    required = ("name", "sso_account_id", "sso_role_name", "region")
    missing = [k for k in required if not body.get(k)]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing required field(s): {', '.join(missing)}",
        )
    try:
        return create_profile(
            name=body["name"],
            sso_account_id=body["sso_account_id"],
            sso_role_name=body["sso_role_name"],
            region=body["region"],
            sso_session=body.get("sso_session"),
            sso_start_url=body.get("sso_start_url"),
            sso_region=body.get("sso_region"),
            output=body.get("output", "json"),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _do_refresh_all(hub: EventHub, force: bool = False, allow_browser: bool = True) -> None:
    """Synchronous body of the refresh_all background thread.

    When `force` is False (the default) only profiles that are expired
    or expiring are renewed — clicking "Refresh All" should refresh all
    profiles, so the desktop passes force=True by default.

    Without `force`, each stale profile is first renewed silently (no
    browser; works whenever the SSO session is still alive). Only the ones
    that can't be renewed that way go through the `aws sso login` browser
    flow. With `allow_browser=False` that last step is skipped and those
    profiles are reported in the `needs_login` field of `profile.refreshed`
    instead — used for unattended runs such as app launch. `force` always
    runs the full login: it is an explicit request to re-authenticate.

    Imports are kept inside the function so the heavy `aws_login` module
    tree is not loaded on sidecar startup.
    """
    try:
        from cli_tool.commands.aws_login.commands.refresh import (
            _classify_profiles,
            _group_profiles_by_session,
            _refresh_all_sessions,
            _silent_refresh_profiles,
        )
        from cli_tool.commands.aws_login.core.config import list_aws_profiles

        logger.info("Starting refresh_all (force=%s) — classifying profiles", force)
        profiles = list_aws_profiles()
        # Decide from the AWS CLI's credential cache: spawning `aws` once per
        # profile just to classify took ~2 s each, in series. Anything the
        # cache can't vouch for goes through the silent renewal below.
        to_refresh, valid = _classify_profiles(profiles, cached_only=True)
        if force:
            # Same semantics as `devo aws-login refresh --force`: move the
            # still-valid profiles onto the refresh list so the explicit
            # user action renews everything, not just the expiring ones.
            for prof, _src in valid:
                to_refresh.append((prof, "Forced refresh"))
            valid = []
        if not to_refresh:
            logger.info("refresh_all: all profiles valid, nothing to refresh")
            hub.publish("profile.refreshed", {"names": [], "success": True})
            return
        logger.info("refresh_all: refreshing %d profile(s)", len(to_refresh))
        hub.publish("profile.refreshing", {"name": f"{len(to_refresh)} profile(s)"})

        verified: list[str] = []
        if not force:
            verified, to_refresh = _silent_refresh_profiles(to_refresh)
            logger.info(
                "refresh_all: %d renewed silently, %d need a login",
                len(verified),
                len(to_refresh),
            )

        needs_login: list[str] = []
        if to_refresh and allow_browser:
            session_profiles = _group_profiles_by_session(to_refresh)
            _, _, browser_verified = _refresh_all_sessions(session_profiles)
            if force:
                browser_verified = _renew_role_credentials(browser_verified)
            verified = verified + browser_verified
        elif to_refresh:
            needs_login = [prof for prof, _reason in to_refresh]

        logger.info("refresh_all: verified %d profile(s)", len(verified))
        # Mirror CLI's refresh_all: if the configured default profile was
        # among the refreshed-and-verified profiles, rewrite [default]
        # credentials so anything that uses them (env, scripts, other
        # tooling) gets fresh STS credentials too.
        _sync_default_credentials_if_in(verified)
        event: dict[str, Any] = {"names": verified, "success": True}
        if needs_login:
            event["needs_login"] = needs_login
        hub.publish("profile.refreshed", event)
    except Exception as exc:
        logger.exception("refresh_all failed")
        hub.publish("profile.refreshed", {"names": [], "success": False, "error": str(exc)})


def _renew_role_credentials(profile_names: list[str]) -> list[str]:
    """After a successful forced login: drop the old cached role credentials
    and fetch new ones, so permission changes take effect now instead of when
    the old credentials expire. Returns the profiles that got new ones.

    Done after the login (not before) so a cancelled login doesn't throw away
    credentials that were still valid.
    """
    from cli_tool.commands.aws_login.commands.refresh import _verify_in_parallel
    from cli_tool.commands.aws_login.core.credentials import clear_cached_role_credentials

    for name in profile_names:
        clear_cached_role_credentials(name)
    return [name for name, ok in zip(profile_names, _verify_in_parallel(profile_names)) if ok]


# Held while a refresh-all runs. The banner's "Log in", the Refresh All button
# and the launch login all use this endpoint; a second request while one is in
# flight joins it (its result arrives on the same `profile.refreshed` event)
# instead of starting a parallel login.
_refresh_all_running = threading.Lock()


def _run_refresh_all(hub: EventHub, force: bool, allow_browser: bool, running: threading.Lock) -> None:
    """Thread body: run the refresh, then release the lock the request took."""
    try:
        _do_refresh_all(hub, force, allow_browser)
    finally:
        running.release()


def _sync_default_credentials_if_in(refreshed_profiles: list[str]) -> None:
    """Rewrite [default] in ~/.aws/credentials when the default profile was refreshed.

    Looks up `aws_login.default_credentials_profile` from the user config
    and, if present in `refreshed_profiles`, exports fresh STS credentials
    via `aws configure export-credentials` and writes them as [default].
    Best-effort: failures are logged and swallowed so the refresh path
    is never broken by a default-credentials rewrite issue.
    """
    try:
        from cli_tool.core.utils.config_manager import get_config_value

        default_profile = get_config_value("aws_login.default_credentials_profile")
    except Exception as exc:
        logger.warning("Could not read default_credentials_profile: %s", exc)
        return

    if not default_profile or default_profile not in refreshed_profiles:
        return

    try:
        result = write_default_credentials(default_profile)
        if result:
            logger.info("Updated [default] credentials from '%s'", default_profile)
        else:
            logger.warning("Could not update [default] credentials for '%s'", default_profile)
    except Exception as exc:
        logger.error("Failed to update [default] credentials for '%s': %s", default_profile, exc)


@router.post(":refresh_all", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("4/minute")
def refresh_all(
    request: Request,
    response: Response,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Kick off refresh in background. Progress arrives via WS profile.refreshed.

    Body (optional):
      - {"force": true} renews every profile, not only the ones that are
        expired or about to expire, through the full browser login. Mirrors
        `devo aws-login refresh --force`.
      - {"allow_browser": false} never opens a browser: stale profiles are
        renewed silently when possible and the rest are listed in
        `needs_login` on the `profile.refreshed` event. Default true.
    """
    app_state = _state(request)
    hub = app_state.event_hub
    force = bool((body or {}).get("force", False))
    allow_browser = bool((body or {}).get("allow_browser", True))

    running = _refresh_all_running
    if not running.acquire(blocking=False):
        return {
            "status": "already_running",
            "message": "A refresh is already in progress — watch WS for profile.refreshed",
        }
    try:
        t = threading.Thread(target=_run_refresh_all, args=(hub, force, allow_browser, running), daemon=True)
        t.start()
    except Exception:
        running.release()
        raise
    return {"status": "accepted", "message": "Refresh started — watch WS for profile.refreshed"}


def _do_refresh_one(hub: EventHub, name: str, force: bool = False) -> None:
    """Synchronous body of the per-profile refresh background thread.

    Tries a silent renewal first; the browser login below only runs when the
    profile's SSO session can't be renewed that way. With `force` it always
    logs in and then replaces this profile's cached role credentials.

    Uses `aws sso login --profile {name}` (same as `devo aws-login` login
    command), NOT `--sso-session`, so only this profile's credentials are
    fetched.  With `--sso-session` the SHARED session token is refreshed
    and every profile on that session benefits — that's `refresh_all`
    behaviour, not per-profile.

    The actual subprocess + verify_credentials calls are kept in this
    helper so the unit tests can patch them out without standing up
    the FastAPI request context.
    """
    from cli_tool.commands.aws_login.commands.refresh import _silent_refresh_profiles
    from cli_tool.commands.aws_login.core.config import get_profile_config
    from cli_tool.sidecar.services.sso_service import run_sso_login_sync

    hub.publish("profile.refreshing", {"name": name})

    profile_config = get_profile_config(name)
    if not profile_config:
        msg = f"Profile '{name}' not found"
        logger.error(msg)
        hub.publish("profile.refreshed", {"names": [], "success": False, "error": msg})
        return

    # Same rule as refresh-all: only open the browser when it is needed. If the
    # SSO session is alive the profile's credentials are renewed silently.
    renewed = [] if force else _silent_refresh_profiles([(name, "manual")])[0]
    if renewed:
        logger.info("Refreshed '%s' silently (no login needed)", name)
        hub.publish("profile.refreshed", {"names": [name], "success": True})
        _sync_default_credentials_if_in([name])
        return

    success = run_sso_login_sync(hub, name, source="profile")
    if success and force:
        success = bool(_renew_role_credentials([name]))
    if success:
        hub.publish("profile.refreshed", {"names": [name], "success": True})
        # If this profile is the configured default, rewrite [default]
        # credentials so they reflect the just-refreshed STS keys (the
        # CLI's login/refresh commands do the same).
        _sync_default_credentials_if_in([name])
    else:
        hub.publish("profile.refreshed", {"names": [], "success": False, "error": f"Refresh failed for {name}"})


@router.post("/{name}:refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_profile(name: str, request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Refresh SSO credentials for a single profile. Result arrives via WS profile.refreshed.

    Body (optional): {"force": true} always runs the browser login and then
    replaces the profile's cached role credentials (e.g. after a permission
    change). Without it the profile is renewed silently when possible.
    """
    app_state = _state(request)
    hub = app_state.event_hub
    force = bool((body or {}).get("force", False))

    threading.Thread(target=_do_refresh_one, args=(hub, name, force), daemon=True).start()
    return {"status": "accepted", "message": f"Refresh started for '{name}' — watch WS for profile.refreshed"}


@router.post("/{name}:refresh_sso_token")
def refresh_sso_token(name: str) -> dict[str, Any]:
    """Lightweight refresh: force boto3 to use the cached SSO refresh token.

    No browser flow — just calls STS to trigger a refresh. Fails if the SSO
    refresh token is also expired (caller should then run the full browser login).
    """
    from cli_tool.commands.aws_login.core.credentials import verify_credentials

    identity = verify_credentials(name)
    if not identity:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="SSO refresh token expired. Run full SSO login (browser flow).",
        )
    logger.info("SSO token refreshed for '%s'", name)
    return {"name": name, "account": identity.get("account"), "refreshed": True}


@router.post("/{name}:set_default")
def set_default_profile(name: str) -> dict[str, Any]:
    result = write_default_credentials(name)
    if result is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to export credentials")
    from cli_tool.core.utils.config_manager import set_config_value

    set_config_value("aws_login.default_credentials_profile", name)
    logger.info("Default credentials profile set to '%s'", name)
    return {"name": name, **result}


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(name: str) -> None:
    """Remove the [profile <name>] block from ~/.aws/config.

    Returns 204 on success, 404 if the profile doesn't exist. The
    [profile <name>] section in credentials is left untouched (the
    cached access keys become orphaned but harmless).
    """
    if not get_profile_config(name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{name}' not found",
        )
    remove_profile_section(name)
    logger.info("Removed profile '%s' from ~/.aws/config", name)


@router.get("/{name}/identity")
def get_identity(name: str) -> dict[str, Any]:
    identity = verify_credentials(name)
    if not identity:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credentials invalid or expired")
    return identity
