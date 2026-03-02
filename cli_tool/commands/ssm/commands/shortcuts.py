"""Shortcuts for most used SSM commands."""

import click


def register_shortcuts(ssm_group):
    """Register shortcut commands for most used operations."""

    @ssm_group.command("connect", hidden=False)
    @click.argument("name", required=False)
    @click.option("--no-hosts", is_flag=True, help="Disable hostname forwarding (use localhost)")
    @click.pass_context
    def connect_shortcut(ctx, name, no_hosts):
        """Shortcut for 'devo ssm database connect'"""
        # Get the database group and invoke connect
        database_group = None
        for cmd_name, cmd in ssm_group.commands.items():
            if cmd_name == "database":
                database_group = cmd
                break

        if database_group:
            connect_cmd = database_group.commands.get("connect")
            if connect_cmd:
                ctx.invoke(connect_cmd, name=name, no_hosts=no_hosts)

    @ssm_group.command("shell", hidden=False)
    @click.argument("name")
    @click.pass_context
    def shell_shortcut(ctx, name):
        """Shortcut for 'devo ssm instance shell'"""
        # Get the instance group and invoke shell
        instance_group = None
        for cmd_name, cmd in ssm_group.commands.items():
            if cmd_name == "instance":
                instance_group = cmd
                break

        if instance_group:
            shell_cmd = instance_group.commands.get("shell")
            if shell_cmd:
                ctx.invoke(shell_cmd, name=name)
