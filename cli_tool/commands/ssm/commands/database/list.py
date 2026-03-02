"""Database list command."""

import click
from rich.console import Console
from rich.table import Table

from cli_tool.commands.ssm.core import SSMConfigManager

console = Console()


@click.command()
def list_databases():
    """List configured databases"""
    config_manager = SSMConfigManager()
    databases = config_manager.list_databases()

    if not databases:
        console.print("[yellow]No databases configured[/yellow]")
        console.print("\nAdd a database with: devo ssm database add")
        return

    table = Table(title="Configured Databases")
    table.add_column("Name", style="cyan")
    table.add_column("Host", style="white")
    table.add_column("Port", style="green")
    table.add_column("Profile", style="yellow")

    for name, db in databases.items():
        table.add_row(name, db["host"], str(db["port"]), db.get("profile", "-"))

    console.print(table)
