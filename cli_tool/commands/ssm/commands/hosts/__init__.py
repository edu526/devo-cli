"""/etc/hosts management commands for SSM."""

import logging

import click

from cli_tool.commands.ssm.commands.hosts.add import hosts_add_single
from cli_tool.commands.ssm.commands.hosts.add_manual import hosts_add_manual
from cli_tool.commands.ssm.commands.hosts.clear import hosts_clear
from cli_tool.commands.ssm.commands.hosts.list import hosts_list
from cli_tool.commands.ssm.commands.hosts.remove import hosts_remove_single
from cli_tool.commands.ssm.commands.hosts.remove_manual import hosts_remove_manual
from cli_tool.commands.ssm.commands.hosts.setup import hosts_setup

# The commands log their outcome for `--log-file`; without one, the console
# output is enough (and the CLI configures no logging to print it twice).
_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())


def register_hosts_commands(ssm_group):
    """Register /etc/hosts management commands to the SSM group."""

    @ssm_group.group("hosts")
    @click.option("--log-file", type=click.Path(dir_okay=False), hidden=True, help="Also log the outcome to this file")
    def hosts(log_file):
        """Manage /etc/hosts entries for hostname forwarding"""
        # The desktop runs these commands elevated, in a hidden window: it
        # passes its sidecar.log so a failure's reason shows up in Logs.
        if log_file:
            handler = logging.FileHandler(log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)

    # Register all hosts commands
    hosts.add_command(hosts_setup, "setup")
    hosts.add_command(hosts_list, "list")
    hosts.add_command(hosts_clear, "clear")
    hosts.add_command(hosts_add_single, "add")
    hosts.add_command(hosts_remove_single, "remove")
    # ponytail: bypass-config variants used by the desktop UAC helper
    hosts.add_command(hosts_add_manual, "add-manual")
    hosts.add_command(hosts_remove_manual, "remove-manual")
