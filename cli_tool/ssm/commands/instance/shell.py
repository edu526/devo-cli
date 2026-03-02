"""Instance shell command."""

import click
from rich.console import Console

from cli_tool.ssm.core import SSMConfigManager, SSMSession

console = Console()


@click.command()
@click.argument("name")
def connect_instance(name):
  """Connect to a configured instance via interactive shell"""
  config_manager = SSMConfigManager()
  instance_config = config_manager.get_instance(name)

  if not instance_config:
    console.print(f"[red]Instance '{name}' not found in config[/red]")
    console.print("\nAvailable instances:")
    for inst_name in config_manager.list_instances().keys():
      console.print(f"  - {inst_name}")
    return

  console.print(f"[cyan]Connecting to {name} ({instance_config['instance_id']})...[/cyan]")
  console.print("[yellow]Type 'exit' to close the session[/yellow]\n")

  try:
    SSMSession.start_session(instance_id=instance_config["instance_id"], region=instance_config["region"], profile=instance_config.get("profile"))
  except KeyboardInterrupt:
    console.print("\n[green]Session closed[/green]")
