"""Database add command."""

import click
from rich.console import Console

from cli_tool.ssm.core import SSMConfigManager

console = Console()


@click.command()
@click.option("--name", required=True, help="Database configuration name")
@click.option("--bastion", required=True, help="Bastion instance ID")
@click.option("--host", required=True, help="Database host/endpoint")
@click.option("--port", required=True, type=int, help="Database port")
@click.option("--local-port", type=int, help="Local port (default: same as remote)")
@click.option("--region", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile")
def add_database(name, bastion, host, port, local_port, region, profile):
  """Add a database configuration"""
  config_manager = SSMConfigManager()

  config_manager.add_database(name=name, bastion=bastion, host=host, port=port, region=region, profile=profile, local_port=local_port)

  console.print(f"[green]Database '{name}' added successfully[/green]")
  console.print(f"\nConnect with: devo ssm connect {name}")
