"""Show configuration path command."""

import click
from rich.console import Console

from cli_tool.utils.config_manager import get_config_path

console = Console()


@click.command()
def show_path():
    """Show configuration file path."""
    config_path = get_config_path()
    console.print(f"[cyan]{config_path}[/cyan]")
