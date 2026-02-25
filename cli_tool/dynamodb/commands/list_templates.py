"""List export templates command."""

from cli_tool.dynamodb.utils import ExportConfigManager


def list_templates_command() -> None:
    """List all saved export templates."""
    config_manager = ExportConfigManager()
    config_manager.list_templates()
