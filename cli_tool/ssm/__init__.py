"""AWS Systems Manager Session Manager integration"""

import click

from cli_tool.ssm.commands import (
    register_database_commands,
    register_forward_command,
    register_hosts_commands,
    register_instance_commands,
    register_shortcuts,
)

# Backward compatibility imports
from cli_tool.ssm.core import PortForwarder, SSMConfigManager, SSMSession
from cli_tool.ssm.utils import HostsManager

# Backward compatibility alias
SocatManager = PortForwarder


@click.group()
def ssm():
    """AWS Systems Manager Session Manager commands"""
    pass


# Register all subcommands
register_database_commands(ssm)
register_instance_commands(ssm)
register_forward_command(ssm)
register_hosts_commands(ssm)
register_shortcuts(ssm)

__all__ = ["ssm", "SSMConfigManager", "SSMSession", "HostsManager", "PortForwarder", "SocatManager"]
