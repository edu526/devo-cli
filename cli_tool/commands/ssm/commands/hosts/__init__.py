"""/etc/hosts management commands for SSM."""

from cli_tool.commands.ssm.commands.hosts.add import hosts_add_single
from cli_tool.commands.ssm.commands.hosts.clear import hosts_clear
from cli_tool.commands.ssm.commands.hosts.list import hosts_list
from cli_tool.commands.ssm.commands.hosts.remove import hosts_remove_single
from cli_tool.commands.ssm.commands.hosts.setup import hosts_setup


def register_hosts_commands(ssm_group):
    """Register /etc/hosts management commands to the SSM group."""

    @ssm_group.group("hosts")
    def hosts():
        """Manage /etc/hosts entries for hostname forwarding"""
        pass

    # Register all hosts commands
    hosts.add_command(hosts_setup, "setup")
    hosts.add_command(hosts_list, "list")
    hosts.add_command(hosts_clear, "clear")
    hosts.add_command(hosts_add_single, "add")
    hosts.add_command(hosts_remove_single, "remove")
