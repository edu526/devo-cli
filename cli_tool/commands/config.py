"""Configuration command wrapper.

This is a thin wrapper that imports from the main config_cmd module.
All logic is in cli_tool/config_cmd/.
"""

from cli_tool.config_cmd import register_config_commands

# For backward compatibility
config_command = register_config_commands()

__all__ = ["config_command"]
