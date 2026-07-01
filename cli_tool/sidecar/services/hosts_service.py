"""Hosts file management — wraps HostsManager, surfaces elevation requirement."""

import platform
import sys
from typing import Any, Optional

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.hosts_setup import setup_databases
from cli_tool.commands.ssm.utils import HostsManager
from cli_tool.core.utils.config_manager import get_config_dir


class NeedsElevation(Exception):
    """Raised when the operation requires elevated privileges.

    `action` and `params` are structured hints for the desktop frontend so it
    can trigger a UAC prompt via Tauri instead of asking the user to run a
    command in their terminal. `command` stays for backward compatibility and
    for non-desktop consumers.
    """

    def __init__(
        self,
        command: str,
        action: str = "",
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        self.command = command
        self.action = action
        self.params = params or {}
        super().__init__("Operation requires elevated privileges")


def _elevation_command(action: str) -> str:
    if platform.system() == "Darwin":
        return f"osascript -e 'do shell script \"{action}\" with administrator privileges'"
    elif platform.system() == "Windows":
        return f'runas /user:Administrator "{action}"'
    return f"pkexec {action}"


def list_hosts() -> list[dict[str, str]]:
    entries = HostsManager().get_managed_entries()
    return [{"ip": ip, "hostname": hostname} for ip, hostname in entries]


def _db_name_for_host(hostname: str) -> Optional[str]:
    """Map a /etc/hosts hostname back to its devo db name, if any.

    `devo ssm hosts {add,remove}` resolve their <name> arg against
    ~/.devo/config.json — passing the raw hostname makes devo silently
    no-op (exit 0, nothing changed). For elevation we want to pass the
    db name so the elevated command actually mutates the file.
    """
    try:
        dbs = SSMConfigManager().list_databases()
    except Exception:
        return None
    for name, cfg in dbs.items():
        if cfg.get("host") == hostname:
            return name
    return None


def add_host(ip: str, hostname: str) -> dict[str, Any]:
    try:
        mgr = HostsManager()
        mgr.add_entry(ip, hostname)
        return {"ip": ip, "hostname": hostname}
    except PermissionError:
        # Manual /etc/hosts entries have no db name in config; the CLI
        # `devo ssm hosts add` cannot reach them. Fall back to writing
        # the hosts file directly via `devo ssm hosts add-manual`.
        db_name = _db_name_for_host(hostname)
        python_bin = sys.executable
        config_dir = get_config_dir()
        use_env = platform.system() != "Windows"
        cmd = _elevation_command(f"env DEVO_CONFIG_DIR={config_dir} {python_bin} -m cli_tool.cli ssm hosts add-manual {ip} {hostname}")
        raise NeedsElevation(
            cmd,
            action="hosts-add",
            params={
                "ip": ip,
                "hostname": hostname,
                "db_name": db_name or "",
                "python_bin": python_bin,
                "config_dir": str(config_dir),
                "use_env": use_env,
            },
        )


def remove_host(hostname: str) -> None:
    try:
        HostsManager().remove_entry(hostname)
    except PermissionError:
        db_name = _db_name_for_host(hostname)
        python_bin = sys.executable
        config_dir = get_config_dir()
        use_env = platform.system() != "Windows"
        if db_name:
            cmd = _elevation_command(f"env DEVO_CONFIG_DIR={config_dir} {python_bin} -m cli_tool.cli ssm hosts remove {db_name}")
        else:
            cmd = _elevation_command(f"env DEVO_CONFIG_DIR={config_dir} {python_bin} -m cli_tool.cli ssm hosts remove-manual {hostname}")
        raise NeedsElevation(
            cmd,
            action="hosts-remove",
            params={"hostname": hostname, "db_name": db_name or "", "python_bin": python_bin, "config_dir": str(config_dir), "use_env": use_env},
        )


def setup_hosts(db_names: Optional[list[str]] = None) -> dict[str, Any]:
    """Run auto-setup for configured databases. Returns structured results.

    If any database failed because /etc/hosts could not be written, raises
    NeedsElevation with the command the user can run in their terminal —
    matching the behaviour of add_host / remove_host.
    """
    succeeded, failed = setup_databases(db_names)
    elevation_needed = next((f for f in failed if f.get("needs_elevation")), None)
    if elevation_needed:
        python_bin = sys.executable
        config_dir = get_config_dir()
        params = {"db_names": db_names} if db_names else {}
        params["python_bin"] = python_bin
        params["config_dir"] = str(config_dir)
        params["use_env"] = platform.system() != "Windows"
        raise NeedsElevation(
            _elevation_command(f"env DEVO_CONFIG_DIR={config_dir} {python_bin} -m cli_tool.cli ssm hosts setup"),
            action="hosts-setup",
            params=params,
        )
    return {"succeeded": succeeded, "failed": failed}
