"""SSM commands module."""

from cli_tool.commands.ssm.commands.database import register_database_commands
from cli_tool.commands.ssm.commands.forward import register_forward_command
from cli_tool.commands.ssm.commands.hosts import register_hosts_commands
from cli_tool.commands.ssm.commands.instance import register_instance_commands
from cli_tool.commands.ssm.commands.shortcuts import register_shortcuts

__all__ = [
    "register_database_commands",
    "register_instance_commands",
    "register_forward_command",
    "register_hosts_commands",
    "register_shortcuts",
]
