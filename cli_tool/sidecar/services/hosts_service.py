"""Hosts file management — wraps HostsManager, surfaces elevation requirement."""

from typing import Any

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
