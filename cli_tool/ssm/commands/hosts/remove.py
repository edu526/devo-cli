"""Hosts remove command."""

import click
from rich.console import Console

from cli_tool.ssm.core import SSMConfigManager
from cli_tool.ssm.utils import HostsManager

console = Console()


@click.command()
@click.argument("name")
def hosts_remove_single(name):
  """Remove a database hostname from /etc/hosts"""
  config_manager = SSMConfigManager()
  hosts_manager = HostsManager()

  db_config = config_manager.get_database(name)

  if not db_config:
    console.print(f"[red]Database '{name}' not found[/red]")
    return

  try:
    hosts_manager.remove_entry(db_config["host"])
    console.print(f"[green]Removed {db_config['host']} from /etc/hosts[/green]")
  except Exception as e:
    console.print(f"[red]Error: {e}[/red]")
