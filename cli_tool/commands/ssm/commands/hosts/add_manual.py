"""Manual /etc/hosts add — bypasses devo db config, operates on raw ip+host.

Used by the desktop app's UAC helper when an entry was added directly via
the UI (no matching db name in ~/.devo/config.json). The regular
`devo ssm hosts add <name>` only works for configured dbs.
"""

import click
from rich.console import Console

from cli_tool.commands.ssm.utils import HostsManager

console = Console()


@click.command()
@click.argument("ip")
@click.argument("hostname")
def hosts_add_manual(ip: str, hostname: str) -> None:
    """Add a raw ip+hostname entry to /etc/hosts (no config required)."""
    try:
        HostsManager().add_entry(ip, hostname)
        console.print(f"[green]Added {hostname} -> {ip}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.exceptions.Exit(code=1) from e
