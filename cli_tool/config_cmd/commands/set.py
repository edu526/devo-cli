"""Set configuration value command."""

import json

import click
from rich.console import Console

from cli_tool.utils.config_manager import set_config_value

console = Console()


@click.command()
@click.argument("key")
@click.argument("value")
def set_command(key, value):
    """Set a configuration value.

    Examples:

      # Set Bedrock model ID
      devo config set bedrock.model_id "new-model-id"

      # Enable version check
      devo config set version_check.enabled true
    """
    # Try to parse value as JSON (for booleans, numbers, objects)
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        # Keep as string if not valid JSON
        parsed_value = value

    try:
        set_config_value(key, parsed_value)
        console.print(f"[green]✓ Set {key} = {parsed_value}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to set value: {e}[/red]")
