"""Configuration CLI commands."""

import click

from cli_tool.commands.config_cmd.commands.export import export_command
from cli_tool.commands.config_cmd.commands.import_cmd import import_command
from cli_tool.commands.config_cmd.commands.migrate import migrate_command
from cli_tool.commands.config_cmd.commands.path import show_path
from cli_tool.commands.config_cmd.commands.reset import reset_command
from cli_tool.commands.config_cmd.commands.sections import list_sections
from cli_tool.commands.config_cmd.commands.set import set_command
from cli_tool.commands.config_cmd.commands.show import show_config


def register_config_commands():
    """Register configuration commands."""

    @click.group(name="config")
    def config_group():
        """Manage Devo CLI configuration."""
        pass

    # Register all subcommands
    config_group.add_command(show_config, "show")
    config_group.add_command(show_path, "path")
    config_group.add_command(list_sections, "sections")
    config_group.add_command(export_command, "export")
    config_group.add_command(import_command, "import")
    config_group.add_command(migrate_command, "migrate")
    config_group.add_command(reset_command, "reset")
    config_group.add_command(set_command, "set")

    return config_group
