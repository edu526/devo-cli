"""List configuration sections command."""

import click
from rich.console import Console
from rich.table import Table

from cli_tool.config_cmd.core.descriptions import SECTION_DESCRIPTIONS
from cli_tool.utils.config_manager import list_config_sections

console = Console()


@click.command()
def list_sections():
    """List all configuration sections."""
    sections = list_config_sections()

    table = Table(title="Configuration Sections")
    table.add_column("Section", style="cyan")
    table.add_column("Description", style="dim")

    for section in sections:
        desc = SECTION_DESCRIPTIONS.get(section, "")
        table.add_row(section, desc)

    console.print(table)
