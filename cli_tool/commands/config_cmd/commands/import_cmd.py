"""Import configuration command."""

import click
from rich.console import Console

from cli_tool.core.utils.config_manager import import_config

console = Console()


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--section", "-s", multiple=True, help="Import specific sections only")
@click.option("--replace", is_flag=True, help="Replace sections instead of merging")
def import_command(input_file, section, replace):
    """Import configuration from file.

    Examples:

      # Import full config (merge with existing)
      devo config import backup.json

      # Import only SSM section
      devo config import backup.json -s ssm

      # Replace SSM section completely
      devo config import backup.json -s ssm --replace
    """
    sections = list(section) if section else None
    merge = not replace

    try:
        import_config(input_file, sections=sections, merge=merge)

        action = "merged" if merge else "replaced"
        if sections:
            console.print(f"[green]✓ Sections {', '.join(sections)} {action} from {input_file}[/green]")
        else:
            console.print(f"[green]✓ Configuration {action} from {input_file}[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")
