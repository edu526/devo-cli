"""Database remove command."""

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMConfigManager

console = Console()


@click.command()
@click.argument("name")
def remove_database(name):
    """Remove a database configuration"""
    config_manager = SSMConfigManager()

    if config_manager.remove_database(name):
        console.print(f"[green]Database '{name}' removed[/green]")
    else:
        console.print(f"[red]Database '{name}' not found[/red]")
