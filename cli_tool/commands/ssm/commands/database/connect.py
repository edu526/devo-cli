"""Database connect command."""

import sys
import time
from typing import Optional

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMConfigManager
from cli_tool.commands.ssm.core.connection_runner import (
    ForwarderRegistry,
    _build_threads,
    _databases_needing_setup,
    _make_connection_table,
    _validate_tokens,
)
from cli_tool.commands.ssm.utils import HostsManager

console = Console()


def _is_windows_admin() -> bool:
    """Return True if the current Windows process is elevated.

    Non-Windows always returns True: on Linux/macOS the hosts file write is
    done via sudo, which prompts the user — no pre-check needed.
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _maybe_run_auto_setup(databases: dict, managed_hosts: set, no_auto_setup: bool) -> set:
    """Offer to run hosts setup for DBs missing config; return the (possibly refreshed) managed_hosts."""
    if no_auto_setup:
        return managed_hosts
    if not sys.stdin.isatty():
        return managed_hosts

    pending = _databases_needing_setup(databases, managed_hosts)
    if not pending:
        return managed_hosts

    if not _is_windows_admin():
        console.print(f"\n[yellow]⚠ {len(pending)} database(s) need hostname forwarding setup:[/yellow] {', '.join(pending)}")
        console.print(
            "[dim]Setup requires Administrator on Windows. Re-open PowerShell as Administrator "
            "and run `devo ssm connect` (or `devo ssm hosts setup`) again.[/dim]\n"
        )
        return managed_hosts

    sudo_note = "(requires Administrator)" if sys.platform == "win32" else "(requires sudo)"
    console.print(f"\n[yellow]⚠ {len(pending)} database(s) need hostname forwarding setup:[/yellow] {', '.join(pending)}")
    console.print("[dim]Setup will assign loopback IPs and add entries to /etc/hosts " + sudo_note + ".[/dim]")

    try:
        proceed = click.confirm("Run setup now?", default=True)
    except click.Abort:
        return managed_hosts

    if not proceed:
        return managed_hosts

    from cli_tool.commands.ssm.commands.hosts.setup import setup_databases

    succeeded, failed = setup_databases(pending)
    if succeeded:
        refreshed = SSMConfigManager().list_databases()
        for name in succeeded:
            if name in databases and name in refreshed:
                databases[name].update(refreshed[name])
        managed_hosts = {host for _, host in HostsManager().get_managed_entries()}
    if failed:
        hint = "re-open PowerShell as Administrator" if sys.platform == "win32" else "re-run with sudo"
        console.print(f"[red]✗ Setup failed for {len(failed)} database(s) ({', '.join(failed)}) — {hint} and retry.[/red]")
    console.print()
    return managed_hosts


def _print_no_connect_tip(port_conflicts: int, missing_hosts: int) -> None:
    console.print("[yellow]No databases to connect[/yellow]")
    if port_conflicts > 0:
        console.print("[dim]Stop the local service occupying port 5432, or use --no-hosts to connect via localhost.[/dim]")
    elif missing_hosts > 0:
        console.print("[dim]Run: devo ssm hosts setup[/dim]")


def _connect_databases(databases: dict, no_hosts: bool, no_auto_setup: bool = False) -> None:
    """Connect to one or more databases in parallel threads."""
    if not _validate_tokens(databases):
        return

    managed_hosts = {host for _, host in HostsManager().get_managed_entries()}
    if not no_hosts:
        managed_hosts = _maybe_run_auto_setup(databases, managed_hosts, no_auto_setup)

    console.print("[cyan]Starting connections...[/cyan]\n")

    table = _make_connection_table()
    registry = ForwarderRegistry()
    threads, port_conflicts, missing_hosts = _build_threads(databases, no_hosts, managed_hosts, table, registry)

    console.print(table)
    console.print()

    if not threads:
        _print_no_connect_tip(port_conflicts, missing_hosts)
        return

    console.print("[green]Connection(s) started![/green]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

    try:
        while any(thread.is_alive() for _, thread in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        try:
            console.print("\n[cyan]Stopping all connections...[/cyan]")
            registry.stop_event.set()
            registry.stop_all()
            for _, thread in threads:
                thread.join(timeout=2)
            console.print("[green]All connections closed[/green]")
        except KeyboardInterrupt:
            pass


def _show_database_selection(databases: dict) -> Optional[str]:
    """Show interactive database selection menu. Returns selected name or None."""
    db_list = list(databases.keys())
    console.print("[cyan]Select database to connect:[/cyan]\n")

    for i, db_name in enumerate(db_list, 1):
        db = databases[db_name]
        profile_text = db.get("profile", "default")
        console.print(f"  {i}. {db_name} ({db['host']}) [dim](profile: {profile_text})[/dim]")

    console.print(f"  {len(db_list) + 1}. Connect to all databases")
    console.print()

    try:
        choice = click.prompt("Enter number", type=int, default=1)
        if choice < 1 or choice > len(db_list) + 1:
            console.print("[red]Invalid selection[/red]")
            return None
        if choice == len(db_list) + 1:
            return "ALL"
        return db_list[choice - 1]
    except (KeyboardInterrupt, click.Abort):
        console.print("\n[yellow]Cancelled[/yellow]")
        return None


@click.command()
@click.argument("name", required=False)
@click.option("--no-hosts", is_flag=True, help="Disable hostname forwarding (use localhost)")
@click.option("--all", "connect_all", is_flag=True, help="Connect to all configured databases at once")
@click.option("--no-auto-setup", is_flag=True, help="Don't prompt to run hosts setup for unconfigured databases")
def connect_database(name, no_hosts, connect_all, no_auto_setup):
    """Connect to a configured database (uses hostname forwarding by default)"""
    config_manager = SSMConfigManager()
    databases = config_manager.list_databases()

    if not databases:
        console.print("[red]No databases configured[/red]")
        console.print("\nAdd a database with: devo ssm database add")
        return

    if connect_all:
        _connect_databases(databases, no_hosts, no_auto_setup)
        return

    if not name:
        selection = _show_database_selection(databases)
        if selection is None:
            return
        if selection == "ALL":
            _connect_databases(databases, no_hosts, no_auto_setup)
            return
        name = selection

    db_config = config_manager.get_database(name)

    if not db_config:
        console.print(f"[red]Database '{name}' not found in config[/red]")
        console.print("\nAvailable databases:")
        for db_name in databases.keys():
            console.print(f"  - {db_name}")
        return

    _connect_databases({name: db_config}, no_hosts, no_auto_setup)
