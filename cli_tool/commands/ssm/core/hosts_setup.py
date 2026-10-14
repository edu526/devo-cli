"""Pure host setup logic — assigns loopback IPs, allocates local ports, adds /etc/hosts entries.

No Rich, no Click. Returns structured, JSON-serializable results so both the CLI
command (prints) and the sidecar service (JSON + elevation detection) can consume
the same output without duplicating the port-allocation loop.
"""

from typing import Optional

from cli_tool.commands.ssm.core import hostname_forwarding
from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.connection_runner import _find_free_port
from cli_tool.commands.ssm.utils import HostsFileLocked, HostsManager


def setup_databases(
    db_names: Optional[list[str]] = None,
    *,
    config_manager: Optional[SSMConfigManager] = None,
    hosts_manager: Optional[HostsManager] = None,
) -> tuple[list[dict], list[dict]]:
    """Assign loopback IPs, allocate free local ports and add /etc/hosts entries.

    If `db_names` is None, every configured database is processed. Otherwise only
    the named subset is touched. Databases whose hostname forwarding is paused
    are always skipped (see hostname_forwarding).

    Returns (succeeded, failed) where each element is a JSON-serializable dict:
      - succeeded: {"name", "host", "ip", "local_port", "port_reassigned"}
      - failed:    {"name", "host", "error", "needs_elevation", "locked"}

    The loop always runs to completion (a failure on one db does not stop the
    rest), matching the original CLI behaviour. `needs_elevation` is True when
    the underlying error was a PermissionError, so the sidecar can surface an
    elevation command without re-running the loop.
    """
    cm = config_manager or SSMConfigManager()
    hm = hosts_manager or HostsManager()
    ssm_config = cm.load()
    databases = cm.list_databases()
    # IPs other databases keep in the config, also the paused ones (no hosts entry)
    taken_ips = {c.get("local_address") for c in databases.values()} - {None, "127.0.0.1"}

    if db_names is not None:
        databases = {n: c for n, c in databases.items() if n in db_names}
    databases = {n: c for n, c in databases.items() if hostname_forwarding.is_enabled(ssm_config, c)}

    succeeded: list[dict] = []
    failed: list[dict] = []
    used_local_ports: dict[int, str] = {}
    next_available_port = 15432  # high port for auto-assignment

    for name, db_config in databases.items():
        host = db_config["host"]

        # Compute (do not persist yet) the loopback IP
        needs_address = "local_address" not in db_config or db_config["local_address"] == "127.0.0.1"
        local_address = hm.get_next_loopback_ip(taken_ips) if needs_address else db_config["local_address"]
        taken_ips.add(local_address)

        # Compute (do not persist yet) the local port
        original_local_port = db_config.get("local_port", db_config["port"])
        preferred_port = original_local_port
        while preferred_port in used_local_ports:
            preferred_port = next_available_port
            next_available_port += 1
        local_port = _find_free_port(preferred_port)
        next_available_port = max(next_available_port, local_port + 1)
        needs_port_save = local_port != original_local_port
        used_local_ports[local_port] = name

        # Side-effecting write FIRST. If it fails the config stays clean.
        try:
            hm.add_entry(local_address, host)
        except Exception as e:
            failed.append(
                {
                    "name": name,
                    "host": host,
                    "error": str(e),
                    "needs_elevation": isinstance(e, PermissionError),
                    # denied even as administrator (antivirus, read-only file…)
                    "locked": isinstance(e, HostsFileLocked),
                }
            )
            continue

        # Persist new values only after the hosts entry was successfully written
        if needs_address or needs_port_save:
            config = cm.load()
            if needs_address:
                config["databases"][name]["local_address"] = local_address
            if needs_port_save:
                config["databases"][name]["local_port"] = local_port
            cm.save(config)

        succeeded.append(
            {
                "name": name,
                "host": host,
                "ip": local_address,
                "local_port": local_port,
                "port_reassigned": needs_port_save,
            }
        )

    return succeeded, failed


def stale_hostnames(ssm_config: dict, managed_entries: list[tuple[str, str]]) -> list[str]:
    """Hostnames in Devo's block of the hosts file that no forwarded database
    uses: databases deleted, with another host now, or paused. They keep
    sending that name to a 127.0.0.X nothing listens on."""
    wanted = {c.get("host") for c in (ssm_config.get("databases") or {}).values() if hostname_forwarding.is_enabled(ssm_config, c)}
    return sorted({host for _ip, host in managed_entries if host not in wanted})


def sync_databases(
    *,
    config_manager: Optional[SSMConfigManager] = None,
    hosts_manager: Optional[HostsManager] = None,
) -> tuple[list[dict], list[dict], list[str]]:
    """Make the hosts file match the databases: set up the forwarded ones
    (setup_databases) and remove the stale entries (stale_hostnames).

    Returns (succeeded, failed, removed): `failed` also holds the stale
    entries that couldn't be removed, as {"name": None, "host", "error",
    "needs_elevation", "locked"}.
    """
    cm = config_manager or SSMConfigManager()
    hm = hosts_manager or HostsManager()
    succeeded, failed = setup_databases(config_manager=cm, hosts_manager=hm)

    removed: list[str] = []
    for host in stale_hostnames(cm.load(), hm.get_managed_entries()):
        try:
            hm.remove_entry(host)
            removed.append(host)
        except Exception as e:
            failed.append(
                {
                    "name": None,
                    "host": host,
                    "error": str(e),
                    "needs_elevation": isinstance(e, PermissionError),
                    "locked": isinstance(e, HostsFileLocked),
                }
            )
    return succeeded, failed, removed
