"""Migrate legacy configuration command."""

import click
from rich.console import Console

from cli_tool.utils.config_manager import migrate_legacy_configs

console = Console()


@click.command()
@click.option("--no-backup", is_flag=True, help="Don't backup legacy files")
def migrate_command(no_backup):
    """Migrate legacy config files to consolidated format.

    This command consolidates:
    - ~/.devo/ssm-config.json
    - ~/.devo/dynamodb/export_templates.json

    Into a single ~/.devo/config.json file.
    """
    console.print("[cyan]Migrating legacy configuration files...[/cyan]\n")

    status = migrate_legacy_configs(backup=not no_backup)

    if status["already_migrated"]:
        return

    if status["ssm"] or status["dynamodb"]:
        console.print("\n[green]✓ Migration completed successfully[/green]")
    else:
        console.print("\n[yellow]No legacy config files found to migrate[/yellow]")
