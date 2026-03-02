"""Hosts list command."""

import click
from rich.console import Console
from rich.table import Table

from cli_tool.commands.ssm.utils import HostsManager

console = Console()


@click.command()
def hosts_list():
    """List all /etc/hosts entries managed by Devo CLI"""
    hosts_manager = HostsManager()
    entries = hosts_manager.get_managed_entries()

    if not entries:
        console.print("[yellow]No managed entries in /etc/hosts[/yellow]")
        console.print("\nRun: devo ssm hosts setup")
        return

    table = Table(title="Managed /etc/hosts Entries")
    table.add_column("IP", style="cyan")
    table.add_column("Hostname", style="white")

    for ip, hostname in entries:
        table.add_row(ip, hostname)

    console.print(table)
