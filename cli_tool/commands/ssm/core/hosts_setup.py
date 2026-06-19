"""Pure host setup logic — assigns loopback IPs, allocates local ports, adds /etc/hosts entries.

No Rich, no Click. Returns structured, JSON-serializable results so both the CLI
command (prints) and the sidecar service (JSON + elevation detection) can consume
the same output without duplicating the port-allocation loop.
"""

from typing import Optional

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.connection_runner import _find_free_port
from cli_tool.commands.ssm.utils import HostsManager


def setup_databases(
    db_names: Optional[list[str]] = None,
    *,
    config_manager: Optional[SSMConfigManager] = None,
    hosts_manager: Optional[HostsManager] = None,
) -> tuple[list[dict], list[dict]]:
    """Assign loopback IPs, allocate free local ports and add /etc/hosts entries.

    If `db_names` is None, every configured database is processed. Otherwise only
    the named subset is touched.

    Returns (succeeded, failed) where each element is a JSON-serializable dict:
      - succeeded: {"name", "host", "ip", "local_port", "port_reassigned"}
      - failed:    {"name", "host", "error", "needs_elevation"}

    The loop always runs to completion (a failure on one db does not stop the
    rest), matching the original CLI behaviour. `needs_elevation` is True when
    the underlying error was a PermissionError, so the sidecar can surface an
    elevation command without re-running the loop.
    """
    cm = config_manager or SSMConfigManager()
    hm = hosts_manager or HostsManager()
    databases = cm.list_databases()

    if db_names is not None:
        databases = {n: c for n, c in databases.items() if n in db_names}

    succeeded: list[dict] = []
    failed: list[dict] = []
    used_local_ports: dict[int, str] = {}
    next_available_port = 15432  # high port for auto-assignment

    for name, db_config in databases.items():
        host = db_config["host"]

        # Compute (do not persist yet) the loopback IP
        needs_address = "local_address" not in db_config or db_config["local_address"] == "127.0.0.1"
        local_address = hm.get_next_loopback_ip() if needs_address else db_config["local_address"]

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
