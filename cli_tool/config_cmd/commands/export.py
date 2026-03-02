"""Export configuration command."""

import json
from datetime import datetime

import click
from rich.console import Console

from cli_tool.utils.config_manager import export_config

console = Console()


@click.command()
@click.option("--section", "-s", multiple=True, help="Export specific sections (can be used multiple times)")
@click.option("--output", "-o", help="Output file path (default: devo-config-backup-YYYYMMDD-HHMMSS.json)")
@click.option("--stdout", is_flag=True, help="Print to stdout instead of saving to file")
def export_command(section, output, stdout):
    """Export configuration (full or partial).

    Examples:

      # Export to default timestamped file
      devo config export

      # Export to stdout
      devo config export --stdout

      # Export only SSM config to custom file
      devo config export -s ssm -o ssm-backup.json

      # Export SSM and DynamoDB to stdout
      devo config export -s ssm -s dynamodb --stdout
    """
    sections = list(section) if section else None

    # Determine output path
    if stdout:
        output_path = None
    elif not output:
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = f"devo-config-backup-{timestamp}.json"
    else:
        output_path = output

    try:
        exported = export_config(sections=sections, output_path=output_path)

        if output_path:
            console.print(f"[green]✓ Configuration exported to {output_path}[/green]")
        else:
            console.print(json.dumps(exported, indent=2))
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")
