"""Hosts file management — wraps HostsManager, surfaces elevation requirement."""

import platform
import sys
from typing import Any, Optional

from cli_tool.commands.ssm.core import hostname_forwarding
from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.hosts_setup import setup_databases, stale_hostnames, sync_databases
from cli_tool.commands.ssm.utils import HostsManager
from cli_tool.commands.ssm.utils.hosts_manager import describe_hosts_lock
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


def _hosts_command_elevation(hosts_args: list[str], action: str, **params: Any) -> NeedsElevation:
    """NeedsElevation for running `devo ssm hosts <hosts_args>` elevated.

    The desktop sends Tauri only `action` and its values (`params`): the shell
    builds the command line itself (hosts_command.rs), from the executable
    this sidecar announced at boot. `cli_args` and `command` are what it runs,
    for the log and for the terminal.
    """
    cli_args = ["ssm", "hosts", *hosts_args]
    return NeedsElevation(
        _elevation_command(f"env DEVO_CONFIG_DIR={get_config_dir()} {sys.executable} -m cli_tool.cli {' '.join(cli_args)}"),
        action=action,
        params={**params, "cli_args": cli_args},
    )


def setup_hosts(db_names: Optional[list[str]] = None) -> dict[str, Any]:
    """Run auto-setup for configured databases. Returns structured results.

    If any database failed because /etc/hosts could not be written, raises
    NeedsElevation with the command the user can run in their terminal —
    matching the behaviour of add_host / remove_host.
    """
    succeeded, failed = setup_databases(db_names)
    if any(f.get("needs_elevation") for f in failed):
        extra = {"db_names": db_names} if db_names else {}
        raise _hosts_command_elevation(["setup", *(db_names or [])], "hosts-setup", **extra)
    return {"succeeded": succeeded, "failed": failed}


def hosts_status() -> dict[str, Any]:
    """Read-only view of hostname forwarding; never writes anything (the page
    used to "check" by running setup, which wrote the hosts file).

    `enabled` is the setting for all databases. Per database: `enabled` (its
    hostname is forwarded, by that setting or its own exception) and `mapped`
    (the hosts file points its hostname at its loopback IP). `missing` lists
    the enabled ones not mapped, `stale` the hostnames in Devo's block that no
    forwarded database uses (sync_hosts fixes both).
    """
    ssm_config = SSMConfigManager().load()
    entries = HostsManager().get_managed_entries()
    managed = {host: ip for ip, host in entries}
    databases = {}
    for name, cfg in (ssm_config.get("databases") or {}).items():
        local_address = cfg.get("local_address", "127.0.0.1")
        databases[name] = {
            "enabled": hostname_forwarding.is_enabled(ssm_config, cfg),
            "mapped": local_address != "127.0.0.1" and managed.get(cfg.get("host")) == local_address,
        }
    return {
        "enabled": hostname_forwarding.global_enabled(ssm_config),
        "databases": databases,
        "missing": sorted(n for n, d in databases.items() if d["enabled"] and not d["mapped"]),
        "stale": stale_hostnames(ssm_config, entries),
    }


def sync_hosts() -> dict[str, Any]:
    """Make the hosts file match the databases (`devo ssm hosts sync`): map the
    missing ones, remove the stale entries. Returns hosts_status(); raises
    NeedsElevation when the file needs it."""
    _succeeded, failed, _removed, _moved = sync_databases()
    if any(f.get("needs_elevation") for f in failed):
        raise _hosts_command_elevation(["sync"], "hosts-sync")
    return hosts_status()


def hosts_lock_reason() -> dict[str, str]:
    """Why the hosts file can't be written even as administrator, for the user.

    The desktop asks after an elevated `devo ssm hosts` command exits with
    HostsFileLocked.exit_code: it only sees that code, not the command's output.
    """
    return {"message": describe_hosts_lock()}


def _map_hostnames(db_names: list[str]) -> None:
    """Add the hosts entries of `db_names`; NeedsElevation if it can't write."""
    if db_names:
        setup_hosts(db_names)


def set_forwarding(enabled: bool) -> dict[str, Any]:
    """Turn hostname forwarding on/off for every database; returns hosts_status().

    Off removes every Devo entry from the hosts file (`devo ssm hosts clear`);
    on maps them all. Either way the per-database exceptions go ("all" means
    all). Raises NeedsElevation when the hosts file needs it: once the
    elevated command ran, calling this again finds the file done and just
    records the setting.

    Turning on, the setting is recorded first (the elevated `hosts setup`
    reads it): if the admin prompt is cancelled the databases show up as
    missing and "Sync Hosts" finishes the job. Turning off, it is recorded
    once the entries are gone.
    """
    cm = SSMConfigManager()
    if enabled:
        cm.set_hostname_forwarding(True)
        _map_hostnames(list(cm.list_databases()))
    else:
        try:
            HostsManager().clear_all()
        except PermissionError:
            raise _hosts_command_elevation(["clear", "--yes"], "hosts-clear")
        cm.set_hostname_forwarding(False)
    return hosts_status()


def set_database_forwarding(name: str, enabled: bool) -> dict[str, Any]:
    """Turn hostname forwarding on/off for one database; returns hosts_status().

    Works whatever the all-databases setting is (it becomes an exception to
    it), e.g. forwarding just one while the rest stay paused. Raises KeyError
    for an unknown database and NeedsElevation like set_forwarding.
    """
    cm = SSMConfigManager()
    ssm_config = cm.load()
    databases = ssm_config.get("databases") or {}
    db = databases.get(name)
    if db is None:
        raise KeyError(f"Database '{name}' not configured")

    if enabled:
        cm.set_hostname_forwarding(True, name)
        _map_hostnames([name])
    else:
        host = db["host"]
        # Another database still forwarded through the same hostname keeps the entry.
        shared = any(n != name and c.get("host") == host and hostname_forwarding.is_enabled(ssm_config, c) for n, c in databases.items())
        if not shared:
            try:
                HostsManager().remove_entry(host)
            except PermissionError:
                raise _hosts_command_elevation(["remove-manual", host], "hosts-remove", hostname=host)
        cm.set_hostname_forwarding(False, name)
    return hosts_status()
