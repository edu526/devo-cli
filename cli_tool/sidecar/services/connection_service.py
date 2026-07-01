"""Connection lifecycle management — bridges REST endpoints with ForwarderRegistry."""

import logging
import threading
from typing import Any

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
    if registry.get(name) is not None:
        existing = registry.get(name)
        if existing.state not in ("stopped", "error", "expired_credentials"):
            raise ValueError(f"Connection '{name}' is already active (state: {existing.state})")

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

    if not registry._observers:
        registry.add_observer(_hub_observer(hub))

    thread = threading.Thread(
        target=_run_connection_loop,
        args=(name, db_config, local_port, use_hostname_forwarding, registry, record),
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
            logger.error("start_all: could not start '%s': %s", name, exc)
            results.append({"name": name, "state": "error", "error": str(exc)})
    return results
