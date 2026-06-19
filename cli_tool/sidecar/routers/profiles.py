"""Profile management endpoints /api/v1/profiles."""

import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from cli_tool.commands.aws_login.core.credentials import (
    verify_credentials,
    write_default_credentials,
)
from cli_tool.sidecar.deps import get_app_state, require_bearer
from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.services.profile_service import get_profile_info, get_profiles_info
from cli_tool.sidecar.state import AppState, EventHub

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["profiles"], dependencies=[Depends(require_bearer)])


def _state(request: Request) -> AppState:
    return get_app_state(request)


@router.get("")
def list_profiles() -> list[dict[str, Any]]:
    return get_profiles_info()


@router.get("/{name}")
def get_profile(name: str) -> dict[str, Any]:
    info = get_profile_info(name)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Profile '{name}' not found")
    return info


def _do_refresh_all(hub: EventHub) -> None:
    """Synchronous body of the refresh_all background thread.

    Imports are kept inside the function so the heavy `aws_login` module
    tree is not loaded on sidecar startup.
    """
    try:
        from cli_tool.commands.aws_login.commands.refresh import (
            _classify_profiles,
            _group_profiles_by_session,
            _refresh_all_sessions,
        )
        from cli_tool.commands.aws_login.core.config import list_aws_profiles

        logger.info("Starting refresh_all — classifying profiles")
        profiles = list_aws_profiles()
        to_refresh, _ = _classify_profiles(profiles)
        if not to_refresh:
            logger.info("refresh_all: all profiles valid, nothing to refresh")
            hub.publish("profile.refreshed", {"names": [], "success": True})
            return
        logger.info("refresh_all: refreshing %d profile(s)", len(to_refresh))
        session_profiles = _group_profiles_by_session(to_refresh)
        _, _, verified = _refresh_all_sessions(session_profiles)
        logger.info("refresh_all: verified %d profile(s)", len(verified))
        hub.publish("profile.refreshed", {"names": verified, "success": True})
    except Exception as exc:
        logger.exception("refresh_all failed")
        hub.publish("profile.refreshed", {"names": [], "success": False, "error": str(exc)})


@router.post(":refresh_all", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("1/minute")
def refresh_all(request: Request, response: Response) -> dict[str, Any]:
    """Kick off refresh in background. Progress arrives via WS profile.refreshed."""
    app_state = _state(request)
    hub = app_state.event_hub

    t = threading.Thread(target=_do_refresh_all, args=(hub,), daemon=True)
    t.start()
    return {"status": "accepted", "message": "Refresh started — watch WS for profile.refreshed"}


def _do_refresh_one(hub: EventHub, name: str) -> None:
    """Synchronous body of the per-profile refresh background thread.

    Uses `aws sso login --profile {name}` (same as `devo aws-login` login
    command), NOT `--sso-session`, so only this profile's credentials are
    fetched.  With `--sso-session` the SHARED session token is refreshed
    and every profile on that session benefits — that's `refresh_all`
    behaviour, not per-profile.

    The actual subprocess + verify_credentials calls are kept in this
    helper so the unit tests can patch them out without standing up
    the FastAPI request context.
    """
    import subprocess

    from cli_tool.commands.aws_login.core.config import get_profile_config
    from cli_tool.commands.aws_login.core.credentials import verify_credentials

    logger.info("Starting SSO refresh for profile '%s'", name)
    hub.publish("profile.refreshing", {"name": name})

    try:
        profile_config = get_profile_config(name)
        if not profile_config:
            msg = f"Profile '{name}' not found"
            logger.error(msg)
            hub.publish("profile.refreshed", {"names": [], "success": False, "error": msg})
            return

        login_cmd = ["aws", "sso", "login", "--profile", name]
        logger.info("Running: %s", " ".join(login_cmd))
        result = subprocess.run(login_cmd, timeout=120)
        if result.returncode != 0:
            msg = f"SSO login failed for '{name}' (exit {result.returncode})"
            logger.error(msg)
            hub.publish("profile.refreshed", {"names": [], "success": False, "error": msg})
            return

        if verify_credentials(name):
            logger.info("Refresh successful for '%s'", name)
            hub.publish("profile.refreshed", {"names": [name], "success": True})
        else:
            msg = f"Credential verification failed for '{name}'"
            logger.error(msg)
            hub.publish("profile.refreshed", {"names": [], "success": False, "error": msg})
    except subprocess.TimeoutExpired:
        msg = "SSO login timed out after 120 seconds"
        logger.error(msg)
        hub.publish("profile.refreshed", {"names": [], "success": False, "error": msg})
    except Exception as exc:
        logger.exception("Unexpected error refreshing profile '%s'", name)
        hub.publish("profile.refreshed", {"names": [], "success": False, "error": str(exc)})


@router.post("/{name}:refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_profile(name: str, request: Request) -> dict[str, Any]:
    """Refresh SSO credentials for a single profile. Result arrives via WS profile.refreshed."""
    app_state = _state(request)
    hub = app_state.event_hub

    threading.Thread(target=_do_refresh_one, args=(hub, name), daemon=True).start()
    return {"status": "accepted", "message": f"Refresh started for '{name}' — watch WS for profile.refreshed"}


@router.post("/{name}:set_default")
def set_default_profile(name: str) -> dict[str, Any]:
    result = write_default_credentials(name)
    if result is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to export credentials")
    from cli_tool.core.utils.config_manager import set_config_value

    set_config_value("aws_login.default_credentials_profile", name)
    logger.info("Default credentials profile set to '%s'", name)
    return {"name": name, **result}


@router.get("/{name}/identity")
def get_identity(name: str) -> dict[str, Any]:
    identity = verify_credentials(name)
    if not identity:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credentials invalid or expired")
    return identity
