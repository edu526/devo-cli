"""Connection lifecycle management — bridges REST endpoints with ForwarderRegistry."""

import logging
import threading
from typing import Any, Optional

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.connection_runner import (
    ConnectionRecord,
    ForwarderRegistry,
    _find_free_port,
    _run_connection_loop,
)
from cli_tool.commands.ssm.utils import HostsManager
from cli_tool.sidecar.state import EventHub

logger = logging.getLogger(__name__)


def _resolve_local_port(db_config: dict, use_hostname_forwarding: bool) -> int:
    fallback = db_config["port"] if use_hostname_forwarding else 15432
    preferred = db_config.get("local_port", fallback)
    return _find_free_port(preferred)


def _hub_observer(hub: EventHub):
    def _emit(event: str, payload: dict) -> None:
        hub.publish(event, payload)

    return _emit


# Module-level state for in-flight SSO logins triggered by a *live* connection
# whose tokens expired mid-session, keyed by profile. Mirrors
# sidecar/routers/codeartifact.py's _ensure_single_sso_login: several DB
# connections commonly share one SSO profile, so if they all notice expired
# tokens around the same time we want one browser tab, not one per
# connection.
_sso_login_threads: dict[str, threading.Thread] = {}
_sso_login_lock = threading.Lock()


def _do_connection_sso_login(hub: EventHub, profile: str) -> None:
    from cli_tool.sidecar.services.sso_service import run_sso_login_sync

    try:
        run_sso_login_sync(hub, profile, source="connection")
    finally:
        with _sso_login_lock:
            _sso_login_threads.pop(profile, None)


def _ensure_single_connection_sso_login(hub: EventHub, profile: Optional[str], name: str) -> None:
    """Auto-launch `aws sso login` when a live connection's tokens expire,
    deduped per profile, so the user doesn't have to reconnect manually just
    to trigger the browser flow. The connection loop itself keeps polling
    and resumes on its own once _wait_for_valid_tokens sees valid tokens —
    this only saves the user the step of starting the refresh.
    """
    if not profile:
        return
    with _sso_login_lock:
        existing = _sso_login_threads.get(profile)
        if existing is not None and existing.is_alive():
            logger.info("SSO login for profile '%s' already in flight; connection '%s' will pick it up", profile, name)
            return
        thread = threading.Thread(
            target=_do_connection_sso_login,
            args=(hub, profile),
            daemon=True,
            name=f"sso-login-conn-{profile}",
        )
        _sso_login_threads[profile] = thread
        thread.start()


def start_connection(
    name: str,
    registry: ForwarderRegistry,
    hub: EventHub,
    no_hosts: bool = False,
) -> dict[str, Any]:
    """Start a single DB connection in a daemon thread.

    Returns a status dict with the local_port resolved.
    Raises ValueError if name is not in config or already connected.
    """
    existing = registry.get(name)
    if existing is not None:
        if existing.state not in ("stopped", "error", "expired_credentials"):
            raise ValueError(f"Connection '{name}' is already active (state: {existing.state})")
        # A record in "expired_credentials" may still have a live loop thread
        # blocked inside _wait_for_valid_tokens(), polling for token refresh.
        # registry.register() below would overwrite this dict entry with a
        # new record, making that thread's stop_event unreachable through
        # the registry — an orphaned thread that keeps its own tunnel alive
        # and can no longer be stopped from the API. Stop it explicitly
        # first so it unblocks and exits before we replace it.
        registry.stop_one(name)

    db_config = SSMConfigManager().get_database(name)
    if db_config is None:
        raise KeyError(f"Database '{name}' not configured")

    local_address = db_config.get("local_address", "127.0.0.1")
    use_hostname_forwarding = local_address != "127.0.0.1" and not no_hosts

    managed_hosts = {host for _, host in HostsManager().get_managed_entries()}
    if use_hostname_forwarding and db_config["host"] not in managed_hosts:
        raise ValueError(f"Host '{db_config['host']}' not in /etc/hosts — run hosts setup first")

    local_port = _resolve_local_port(db_config, use_hostname_forwarding)
    record = ConnectionRecord(name=name, local_port=local_port)

    from cli_tool.commands.ssm.core.session import SSMSession

    if SSMSession._is_token_expired(region=db_config["region"], profile=db_config.get("profile")):
        record.state = "expired_credentials"
        registry.register(name, record)
        return {
            "name": name,
            "local_port": local_port,
            "state": "expired_credentials",
            "sso_required": True,
            "profile": db_config.get("profile") or "default",
        }

    registry.register(name, record)

    # The global stop_event is set by stop_all_connections() and never
    # cleared; without this, any connection started after a "Stop All"
    # would see _should_stop() true and exit immediately.
    registry.stop_event.clear()

    if not registry._observers:
        registry.add_observer(_hub_observer(hub))

    thread = threading.Thread(
        target=_run_connection_loop,
        args=(
            name,
            db_config,
            local_port,
            use_hostname_forwarding,
            registry,
            record,
            lambda profile: _ensure_single_connection_sso_login(hub, profile, name),
        ),
        daemon=True,
        name=f"conn-{name}",
    )
    thread.start()
    return {"name": name, "local_port": local_port, "state": "starting"}


def stop_connection(name: str, registry: ForwarderRegistry) -> None:
    registry.stop_one(name)


def stop_all_connections(registry: ForwarderRegistry) -> None:
    registry.stop_event.set()
    registry.stop_all()
    for name, record in registry.list_records().items():
        registry.stop_one(name)


def list_connections(registry: ForwarderRegistry) -> list[dict[str, Any]]:
    out = []
    for name, rec in registry.list_records().items():
        out.append(
            {
                "name": name,
                "state": rec.state,
                "local_port": rec.local_port,
                "error": rec.error,
            }
        )
    return out


def start_all_connections(
    registry: ForwarderRegistry,
    hub: EventHub,
    no_hosts: bool = False,
) -> list[dict[str, Any]]:
    databases = SSMConfigManager().list_databases()
    results = []
    for name in databases:
        try:
            info = start_connection(name, registry, hub, no_hosts)
            logger.info("start_all: started '%s' on port %s", name, info.get("local_port"))
            results.append(info)
        except (ValueError, KeyError) as exc:
            msg = str(exc)
            if "already active" in msg:
                logger.info("start_all: '%s' is already active", name)
                results.append({"name": name, "state": "connected"})
            else:
                logger.error("start_all: could not start '%s': %s", name, exc)
                results.append({"name": name, "state": "error", "error": msg})
    return results
