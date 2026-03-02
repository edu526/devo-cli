"""Code Reviewer commands."""

import click

from cli_tool.code_reviewer.commands.analyze import analyze


def register_code_reviewer_commands(parent_group):
    """Register code reviewer commands."""

    @parent_group.command("code-reviewer")
    @click.pass_context
    def code_reviewer(ctx):
        """🚀 Code Reviewer - AI-Powered Code Analysis"""
        pass

    # Register analyze as the main command
    code_reviewer.add_command(analyze, "analyze")

    # Make analyze the default command when no subcommand is provided
    code_reviewer.callback = analyze.callback
    code_reviewer.params = analyze.params
