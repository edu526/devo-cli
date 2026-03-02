"""Instance add command."""

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMConfigManager

console = Console()


@click.command()
@click.option("--name", required=True, help="Instance configuration name")
@click.option("--instance-id", required=True, help="EC2 instance ID")
@click.option("--region", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile")
def add_instance(name, instance_id, region, profile):
    """Add an instance configuration"""
    config_manager = SSMConfigManager()

    config_manager.add_instance(name=name, instance_id=instance_id, region=region, profile=profile)

    console.print(f"[green]Instance '{name}' added successfully[/green]")
    console.print(f"\nConnect with: devo ssm shell {name}")
