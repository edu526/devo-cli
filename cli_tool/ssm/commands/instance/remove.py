"""Instance remove command."""

import click
from rich.console import Console

from cli_tool.ssm.core import SSMConfigManager

console = Console()


@click.command()
@click.argument("name")
def remove_instance(name):
  """Remove an instance configuration"""
  config_manager = SSMConfigManager()

  if config_manager.remove_instance(name):
    console.print(f"[green]Instance '{name}' removed[/green]")
  else:
    console.print(f"[red]Instance '{name}' not found[/red]")
