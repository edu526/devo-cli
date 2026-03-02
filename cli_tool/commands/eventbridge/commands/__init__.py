"""EventBridge CLI commands."""

import click

from cli_tool.commands.eventbridge.commands.list import list_rules


def register_eventbridge_commands():
    """Register EventBridge commands."""

    @click.command("eventbridge")
    @click.option(
        "--env",
        "-e",
        help="Filter by environment (e.g., dev, staging, prod)",
        required=False,
    )
    @click.option("--region", "-r", default="us-east-1", help="AWS region (default: us-east-1)")
    @click.option(
        "--status",
        "-s",
        type=click.Choice(["ENABLED", "DISABLED", "ALL"], case_sensitive=False),
        default="ALL",
        help="Filter by rule status",
    )
    @click.option(
        "--output",
        "-o",
        type=click.Choice(["table", "json"], case_sensitive=False),
        default="table",
        help="Output format (default: table)",
    )
    @click.pass_context
    def eventbridge_cmd(ctx, env, region, status, output):
        """Check EventBridge scheduled rules status by environment."""
        list_rules(ctx, env, region, status, output)

    return eventbridge_cmd
