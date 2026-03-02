"""Hosts clear command."""

import click
from rich.console import Console

from cli_tool.commands.ssm.utils import HostsManager

console = Console()


@click.command()
@click.confirmation_option(prompt="Remove all Devo CLI entries from /etc/hosts?")
def hosts_clear():
    """Remove all Devo CLI managed entries from /etc/hosts"""
    hosts_manager = HostsManager()

    try:
        hosts_manager.clear_all()
        console.print("[green]All managed entries removed from /etc/hosts[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
