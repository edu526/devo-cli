"""Shortcuts for most used SSM commands."""

import click


def _find_subcommand(group, group_name: str, cmd_name: str):
    """Find a subcommand within a named group."""
    sub_group = group.commands.get(group_name)
    if sub_group:
        return sub_group.commands.get(cmd_name)
    return None


def register_shortcuts(ssm_group):
    """Register shortcut commands for most used operations."""

    @ssm_group.command("connect", hidden=False)
    @click.argument("name", required=False)
    @click.option("--no-hosts", is_flag=True, help="Disable hostname forwarding (use localhost)")
    @click.pass_context
    def connect_shortcut(ctx, name, no_hosts):
        """Shortcut for 'devo ssm database connect'"""
        connect_cmd = _find_subcommand(ssm_group, "database", "connect")
        if connect_cmd:
            ctx.invoke(connect_cmd, name=name, no_hosts=no_hosts)

    @ssm_group.command("shell", hidden=False)
    @click.argument("name")
    @click.pass_context
    def shell_shortcut(ctx, name):
        """Shortcut for 'devo ssm instance shell'"""
        shell_cmd = _find_subcommand(ssm_group, "instance", "shell")
        if shell_cmd:
            ctx.invoke(shell_cmd, name=name)
