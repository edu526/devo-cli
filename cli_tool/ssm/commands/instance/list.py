"""Instance list command."""

import click
from rich.console import Console
from rich.table import Table

from cli_tool.ssm.core import SSMConfigManager

console = Console()


@click.command()
def list_instances():
  """List configured instances"""
  config_manager = SSMConfigManager()
  instances = config_manager.list_instances()

  if not instances:
    console.print("[yellow]No instances configured[/yellow]")
    console.print("\nAdd an instance with: devo ssm instance add")
    return

  table = Table(title="Configured Instances")
  table.add_column("Name", style="cyan")
  table.add_column("Instance ID", style="white")
  table.add_column("Region", style="green")
  table.add_column("Profile", style="yellow")

  for name, inst in instances.items():
    table.add_row(name, inst["instance_id"], inst["region"], inst.get("profile", "-"))

  console.print(table)
