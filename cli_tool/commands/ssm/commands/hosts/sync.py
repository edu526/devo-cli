"""Hosts sync command."""

import logging

import click
from rich.console import Console

from cli_tool.commands.ssm.core.hosts_setup import sync_databases
from cli_tool.commands.ssm.utils import HostsFileLocked

console = Console()
logger = logging.getLogger(__name__)


@click.command()
def hosts_sync():
    """Make /etc/hosts match the databases: add missing entries, remove stale ones.

    Stale entries are hostnames in Devo's block that no database forwards
    anymore (deleted, with another host now, or paused). Databases sharing a
    loopback IP and port get their own IP; clients keep the same hostname.
    """
    succeeded, failed, removed, moved = sync_databases()

    for entry in succeeded:
        console.print(f"[green]✓[/green] {entry['name']}: {entry['host']} -> {entry['ip']}:{entry['local_port']}")
    for move in moved:
        console.print(f"[green]✓[/green] {move['name']}: own IP {move['to']} (shared {move['from']} with {move['shared_with']})")
        logger.info("%s moved from %s to %s (shared it with %s)", move["name"], move["from"], move["to"], move["shared_with"])
    for host in removed:
        console.print(f"[green]✓[/green] removed stale {host}")
    for entry in failed:
        console.print(f"[red]✗[/red] {entry['name'] or entry['host']}: {entry['error']}")
        logger.error("Could not sync %s in the hosts file: %s", entry["name"] or entry["host"], entry["error"])
    if succeeded or removed:
        logger.info("Hosts file synced: %d set up, %d stale removed", len(succeeded), len(removed))

    if not failed:
        console.print("\n[green]Hosts file in sync[/green]")
        return
    # The desktop runs this elevated and reads the exit code to know it worked.
    locked = any(f.get("locked") for f in failed)
    raise click.exceptions.Exit(code=HostsFileLocked.exit_code if locked else 1)
