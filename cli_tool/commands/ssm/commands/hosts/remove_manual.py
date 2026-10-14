"""Manual /etc/hosts remove — bypasses devo db config, operates on raw host.

Used by the desktop app's UAC helper for entries that have no matching
db name in ~/.devo/config.json (orphan hosts, manual additions).
"""

import logging

import click
from rich.console import Console

from cli_tool.commands.ssm.utils import HostsFileLocked, HostsManager

console = Console()
logger = logging.getLogger(__name__)


@click.command()
@click.argument("hostname")
def hosts_remove_manual(hostname: str) -> None:
    """Remove a raw hostname entry from /etc/hosts (no config required)."""
    try:
        HostsManager().remove_entry(hostname)
        console.print(f"[green]Removed {hostname} from /etc/hosts[/green]")
        logger.info("Removed %s from the hosts file", hostname)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("Could not remove %s from the hosts file: %s", hostname, e)
        raise click.exceptions.Exit(code=e.exit_code if isinstance(e, HostsFileLocked) else 1) from e
