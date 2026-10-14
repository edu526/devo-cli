"""Hosts setup command."""

import logging
from typing import Optional

import click
from rich.console import Console

from cli_tool.commands.ssm.core import hostname_forwarding
from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.hosts_setup import setup_databases as _run_setup
from cli_tool.commands.ssm.utils import HostsFileLocked

console = Console()
logger = logging.getLogger(__name__)


def setup_databases(db_names: Optional[list[str]] = None) -> tuple[list[str], list[str]]:
    """Run setup and print per-db results. Returns (succeeded_names, failed_names).

    Thin CLI wrapper around the pure core in `cli_tool.commands.ssm.core.hosts_setup`.
    Kept for backward-compat with callers/tests that expect name-only lists.
    """
    succeeded, failed = _setup_and_print(db_names)
    return [e["name"] for e in succeeded], [e["name"] for e in failed]


def _setup_and_print(db_names: Optional[list[str]]) -> tuple[list[dict], list[dict]]:
    succeeded, failed = _run_setup(db_names)

    for entry in succeeded:
        port_note = ""
        if entry["port_reassigned"]:
            port_note = f" (local port conflict, assigned {entry['local_port']})"
        console.print(f"[green]✓[/green] {entry['name']}: {entry['host']} -> {entry['ip']}:{entry['local_port']}{port_note}")
    for entry in failed:
        console.print(f"[red]✗[/red] {entry['name']}: {entry['error']}")
        logger.error("Could not add %s (%s) to the hosts file: %s", entry["name"], entry["host"], entry["error"])
    if succeeded:
        logger.info("Added to the hosts file: %s", ", ".join(e["name"] for e in succeeded))

    return succeeded, failed


@click.command()
@click.argument("db_names", nargs=-1)
def hosts_setup(db_names):
    """Setup /etc/hosts entries for configured databases (all, or only DB_NAMES)"""
    config_manager = SSMConfigManager()
    databases = config_manager.list_databases()

    if not databases:
        console.print("[yellow]No databases configured[/yellow]")
        return

    console.print("[cyan]Setting up /etc/hosts entries...[/cyan]\n")
    ssm_config = config_manager.load()
    requested = [n for n in databases if not db_names or n in db_names]
    paused = [n for n in requested if not hostname_forwarding.is_enabled(ssm_config, databases[n])]
    if paused:
        console.print(f"[yellow]Skipped, hostname forwarding is paused (Devo Desktop): {', '.join(paused)}[/yellow]\n")

    succeeded, failed = _setup_and_print(list(db_names) or None)
    # Denied even as administrator: the error above says why; "run as
    # Administrator" would send the user the wrong way.
    locked = any(f.get("locked") for f in failed)

    if failed and not succeeded:
        console.print("\n[red]Setup failed![/red]")
        if not locked:
            console.print("[yellow]All entries failed. Please run your terminal as Administrator.[/yellow]")
    elif failed:
        console.print("\n[yellow]Setup partially complete[/yellow]")
        console.print(f"[dim]{len(succeeded)} succeeded, {len(failed)} failed[/dim]")
    else:
        console.print("\n[green]Setup complete![/green]")
        console.print("\n[dim]Your microservices can now use the real hostnames in their configuration.[/dim]")
    if failed:
        # The desktop runs this elevated and reads the exit code to know it worked.
        raise click.exceptions.Exit(code=HostsFileLocked.exit_code if locked else 1)
