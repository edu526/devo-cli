"""Configuration management commands."""

import json

import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from cli_tool.utils.config_manager import (
    export_config,
    get_config_path,
    import_config,
    list_config_sections,
    load_config,
    migrate_legacy_configs,
    reset_config,
    set_config_value,
)

console = Console()


@click.group(name="config")
def config_command():
    """Manage Devo CLI configuration."""
    pass


@config_command.command(name="show")
@click.option("--section", "-s", help="Show only specific section (e.g., ssm, dynamodb)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def show_config(section, as_json):
    """Show current configuration."""
    config = load_config()

    if section:
        if section not in config:
            console.print(f"[red]✗ Section '{section}' not found[/red]")
            console.print(f"Available sections: {', '.join(list_config_sections())}")
            return
        config = {section: config[section]}

    if as_json:
        console.print(json.dumps(config, indent=2))
    else:
        syntax = Syntax(json.dumps(config, indent=2), "json", theme="monokai", line_numbers=True)
        console.print(syntax)


@config_command.command(name="path")
def show_path():
    """Show configuration file path."""
    config_path = get_config_path()
    console.print(f"[cyan]{config_path}[/cyan]")


@config_command.command(name="sections")
def list_sections():
    """List all configuration sections."""
    sections = list_config_sections()

    table = Table(title="Configuration Sections")
    table.add_column("Section", style="cyan")
    table.add_column("Description", style="dim")

    descriptions = {
        "bedrock": "AWS Bedrock AI model settings",
        "github": "GitHub repository configuration",
        "codeartifact": "AWS CodeArtifact settings",
        "version_check": "Version check preferences",
        "ssm": "SSM connection configurations",
        "dynamodb": "DynamoDB export templates",
    }

    for section in sections:
        desc = descriptions.get(section, "")
        table.add_row(section, desc)

    console.print(table)


@config_command.command(name="export")
@click.option("--section", "-s", multiple=True, help="Export specific sections (can be used multiple times)")
@click.option("--output", "-o", help="Output file path (default: stdout)")
def export_command(section, output):
    """Export configuration (full or partial).

    Examples:

      # Export full config to stdout
      devo config export

      # Export only SSM config
      devo config export -s ssm

      # Export SSM and DynamoDB to file
      devo config export -s ssm -s dynamodb -o backup.json
    """
    sections = list(section) if section else None

    try:
        exported = export_config(sections=sections, output_path=output)

        if output:
            console.print(f"[green]✓ Configuration exported to {output}[/green]")
        else:
            console.print(json.dumps(exported, indent=2))
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")


@config_command.command(name="import")
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


@config_command.command(name="migrate")
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


@config_command.command(name="reset")
@click.option("--section", "-s", help="Reset only specific section")
@click.confirmation_option(prompt="Are you sure you want to reset configuration?")
def reset_command(section):
    """Reset configuration to defaults.

    WARNING: This will delete your current configuration!
    """
    if section:
        # Reset specific section
        from cli_tool.utils.config_manager import get_default_config

        default_value = get_default_config().get(section)

        if default_value is None:
            console.print(f"[red]✗ Unknown section: {section}[/red]")
            return

        set_config_value(section, default_value)
        console.print(f"[green]✓ Section '{section}' reset to defaults[/green]")
    else:
        # Reset full config
        reset_config()
        console.print("[green]✓ Configuration reset to defaults[/green]")


@config_command.command(name="set")
@click.argument("key")
@click.argument("value")
def set_command(key, value):
    """Set a configuration value.

    Examples:

      # Set Bedrock model ID
      devo config set bedrock.model_id "new-model-id"

      # Enable version check
      devo config set version_check.enabled true
    """
    # Try to parse value as JSON (for booleans, numbers, objects)
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        # Keep as string if not valid JSON
        parsed_value = value

    try:
        set_config_value(key, parsed_value)
        console.print(f"[green]✓ Set {key} = {parsed_value}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to set value: {e}[/red]")
