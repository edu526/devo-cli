"""EventBridge command wrapper.

This is a thin wrapper that imports from the main eventbridge module.
All logic is in cli_tool/eventbridge/.
"""

from cli_tool.eventbridge import register_eventbridge_commands

# For backward compatibility
eventbridge = register_eventbridge_commands()

__all__ = ["eventbridge"]
