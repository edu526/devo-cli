"""Show configuration command."""

import json

import click
from rich.console import Console
from rich.syntax import Syntax

from cli_tool.utils.config_manager import list_config_sections, load_config

console = Console()


@click.command()
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
