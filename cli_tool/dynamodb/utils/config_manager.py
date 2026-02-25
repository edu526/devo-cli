"""Configuration manager for DynamoDB export templates."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.table import Table

console = Console()


class ExportConfigManager:
    """Manage export configuration templates."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / ".devo" / "dynamodb"
        self.config_dir = config_dir
        self.config_file = self.config_dir / "export_templates.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            self.config_file.write_text("{}")

    def save_template(self, name: str, config: Dict[str, Any]) -> None:
        """Save export configuration template."""
        templates = self.load_templates()
        templates[name] = config
        self.config_file.write_text(json.dumps(templates, indent=2))
        console.print(f"[green]✓ Template '{name}' saved[/green]")

    def load_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load all export templates."""
        if not self.config_file.exists():
            return {}
        return json.loads(self.config_file.read_text())

    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """Get specific template by name."""
        templates = self.load_templates()
        return templates.get(name)

    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        templates = self.load_templates()
        if name in templates:
            del templates[name]
            self.config_file.write_text(json.dumps(templates, indent=2))
            console.print(f"[green]✓ Template '{name}' deleted[/green]")
            return True
        console.print(f"[yellow]⚠ Template '{name}' not found[/yellow]")
        return False

    def list_templates(self) -> None:
        """List all saved templates."""
        templates = self.load_templates()

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
