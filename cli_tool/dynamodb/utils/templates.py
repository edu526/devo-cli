"""DynamoDB export templates management."""

from typing import Any, Dict

from rich.console import Console
from rich.table import Table

from cli_tool.utils.config_manager import (
    delete_dynamodb_template,
    get_dynamodb_template,
    get_dynamodb_templates,
    save_dynamodb_template,
)

console = Console()


class ExportConfigManager:
    """Manage export configuration templates (wrapper for backward compatibility)."""

    def save_template(self, name: str, config: Dict[str, Any]) -> None:
        """Save export configuration template."""
        save_dynamodb_template(name, config)
        console.print(f"[green]✓ Template '{name}' saved[/green]")

    def load_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load all export templates."""
        return get_dynamodb_templates()

    def get_template(self, name: str) -> Dict[str, Any]:
        """Get specific template by name."""
        return get_dynamodb_template(name)

    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        if delete_dynamodb_template(name):
            console.print(f"[green]✓ Template '{name}' deleted[/green]")
            return True
        console.print(f"[yellow]⚠ Template '{name}' not found[/yellow]")
        return False

    def list_templates(self) -> None:
        """List all saved templates."""
        templates = get_dynamodb_templates()

        if not templates:
            console.print("[yellow]No templates saved[/yellow]")
            return

        table = Table(title="Export Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Table", style="green")
        table.add_column("Format", style="yellow")
        table.add_column("Options", style="magenta")

        for name, config in templates.items():
            options = []
            if config.get("mode"):
                options.append(f"mode:{config['mode']}")
            if config.get("compress"):
                options.append(f"compress:{config['compress']}")
            if config.get("limit"):
                options.append(f"limit:{config['limit']}")

            table.add_row(
                name,
                config.get("table_name", "N/A"),
                config.get("format", "csv"),
                ", ".join(options) if options else "-",
            )

        console.print(table)


def create_template_from_args(**kwargs) -> Dict[str, Any]:
    """Create template dict from command arguments."""
    template = {}

    # Only include non-None values
    for key, value in kwargs.items():
        if value is not None and key not in ["ctx", "list_tables", "preview", "info", "dry_run", "yes"]:
            template[key] = value

    return template
