"""Hosts file management — wraps HostsManager, surfaces elevation requirement."""

from typing import Any, Optional

from cli_tool.commands.ssm.core.hosts_setup import setup_databases
from cli_tool.commands.ssm.utils import HostsManager


class NeedsElevation(Exception):
    """Raised when the operation requires elevated privileges."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__("Operation requires elevated privileges")


def _elevation_command(action: str) -> str:
    import platform

    if platform.system() == "Darwin":
        return f"osascript -e 'do shell script \"{action}\" with administrator privileges'"
    elif platform.system() == "Windows":
        return f'runas /user:Administrator "{action}"'
    return f"sudo {action}"


def list_hosts() -> list[dict[str, str]]:
    entries = HostsManager().get_managed_entries()
    return [{"ip": ip, "hostname": hostname} for ip, hostname in entries]


def add_host(ip: str, hostname: str) -> dict[str, Any]:
    try:
        mgr = HostsManager()
        mgr.add_entry(ip, hostname)
        return {"ip": ip, "hostname": hostname}
    except PermissionError:
        cmd = _elevation_command(f"devo ssm hosts add {ip} {hostname}")
        raise NeedsElevation(cmd)


def remove_host(hostname: str) -> None:
    try:
        HostsManager().remove_entry(hostname)
    except PermissionError:
        cmd = _elevation_command(f"devo ssm hosts remove {hostname}")
        raise NeedsElevation(cmd)


def setup_hosts(db_names: Optional[list[str]] = None) -> dict[str, Any]:
    """Run auto-setup for configured databases. Returns structured results.

    If any database failed because /etc/hosts could not be written, raises
    NeedsElevation with the command the user can run in their terminal —
    matching the behaviour of add_host / remove_host.
    """
    succeeded, failed = setup_databases(db_names)
    elevation_needed = next((f for f in failed if f.get("needs_elevation")), None)
    if elevation_needed:
        raise NeedsElevation(_elevation_command("devo ssm hosts setup"))
    return {"succeeded": succeeded, "failed": failed}
