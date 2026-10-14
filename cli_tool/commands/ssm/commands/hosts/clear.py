"""Hosts clear command."""

import logging

import click
from rich.console import Console

from cli_tool.commands.ssm.utils import HostsFileLocked, HostsManager

console = Console()
logger = logging.getLogger(__name__)


@click.command()
@click.confirmation_option(prompt="Remove all Devo CLI entries from /etc/hosts?")
def hosts_clear():
    """Remove all Devo CLI managed entries from /etc/hosts"""
    hosts_manager = HostsManager()

    try:
        hosts_manager.clear_all()
        console.print("[green]All managed entries removed from /etc/hosts[/green]")
        logger.info("Removed every Devo entry from the hosts file")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("Could not remove the Devo entries from the hosts file: %s", e)
        # The desktop runs this elevated and reads the exit code to know it worked.
        raise click.exceptions.Exit(code=e.exit_code if isinstance(e, HostsFileLocked) else 1) from e
