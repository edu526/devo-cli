"""Reset configuration command."""

import click
from rich.console import Console

from cli_tool.core.utils.config_manager import get_default_config, reset_config, set_config_value

console = Console()


@click.command()
@click.option("--section", "-s", help="Reset only specific section")
@click.confirmation_option(prompt="Are you sure you want to reset configuration?")
def reset_command(section):
    """Reset configuration to defaults.

    WARNING: This will delete your current configuration!
    """
    if section:
        # Reset specific section
        default_value = get_default_config().get(section)

        if default_value is None:
            console.print(f"[red]✗ Unknown section: {section}[/red]")
            return

        set_config_value(section, default_value)
        console.print(f"[green]✓ Section '{section}' reset to defaults[/green]")
    else:
        # Reset full config
        reset_config()
        console.print("[green]✓ Configuration reset to defaults[/green]")
