"""Instance connection commands for SSM."""

from cli_tool.commands.ssm.commands.instance.add import add_instance
from cli_tool.commands.ssm.commands.instance.list import list_instances
from cli_tool.commands.ssm.commands.instance.remove import remove_instance
from cli_tool.commands.ssm.commands.instance.shell import connect_instance


def register_instance_commands(ssm_group):
    """Register instance-related commands to the SSM group."""

    @ssm_group.group("instance")
    def instance():
        """Manage EC2 instance connections"""
        pass

    # Register all instance commands
    instance.add_command(connect_instance, "shell")
    instance.add_command(list_instances, "list")
    instance.add_command(add_instance, "add")
    instance.add_command(remove_instance, "remove")
