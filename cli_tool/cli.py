import os

import click
from rich.console import Console

from cli_tool.commands.autocomplete import autocomplete
from cli_tool.commands.aws_login import aws_login
from cli_tool.commands.code_reviewer.commands.analyze import code_reviewer
from cli_tool.commands.codeartifact import codeartifact_login
from cli_tool.commands.commit import commit
from cli_tool.commands.config_cmd import register_config_commands
from cli_tool.commands.dynamodb import dynamodb
from cli_tool.commands.eventbridge import register_eventbridge_commands
from cli_tool.commands.ssm import ssm
from cli_tool.commands.upgrade import upgrade

console = Console()


def profile_option(f):
    """Decorator to add --profile option to commands."""
    return click.option(
        "--profile",
        envvar="AWS_PROFILE",
        default=None,
        help="AWS profile to use for authentication",
    )(f)


class AliasedGroup(click.Group):
    """Custom Click Group that supports command aliases."""

    def get_command(self, ctx, cmd_name):
        # Define aliases mapping
        aliases = {
            "ca-login": "codeartifact-login",
        }
        # Resolve alias to actual command name
        cmd_name = aliases.get(cmd_name, cmd_name)
        return super().get_command(ctx, cmd_name)

    def format_commands(self, ctx, formatter):
        """Show aliases in help text."""
        # Define aliases mapping (reverse lookup)
        aliases_map = {
            "codeartifact-login": ["ca-login"],
        }

        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None:
                continue

            # Build command name with aliases
            cmd_name = subcommand
            if subcommand in aliases_map:
                aliases = ",".join(aliases_map[subcommand])
                cmd_name = f"{subcommand} ({aliases})"

            help_text = cmd.get_short_help_str(limit=formatter.width)
            commands.append((cmd_name, help_text))

        if commands:
            with formatter.section("Commands"):
                formatter.write_dl(commands)


try:
    from cli_tool._version import version as __version__
except ImportError:
    # Fallback for development
    try:
        from setuptools_scm import get_version

        __version__ = get_version(root="..", relative_to=__file__)
    except Exception:
        __version__ = "unknown"


@click.group(cls=AliasedGroup)
@click.option(
    "--profile",
    default=None,
    help="AWS profile to use (must come before command, e.g., 'devo --profile dev eventbridge')",
)
@click.version_option(__version__, "-v", "--version", prog_name="devo", message="%(version)s")
@click.pass_context
def cli(ctx, profile):
    """CLI for developers with AI-powered features."""
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Store profile in context for commands that need it
    # Note: We don't automatically use AWS_PROFILE here - let commands decide
    ctx.obj["profile"] = profile

    # Set AWS_PROFILE environment variable if profile is specified via --profile
    if profile:
        os.environ["AWS_PROFILE"] = profile


cli.add_command(commit)
cli.add_command(upgrade)
cli.add_command(aws_login)
cli.add_command(codeartifact_login)
cli.add_command(autocomplete)
cli.add_command(code_reviewer)
cli.add_command(register_config_commands())
cli.add_command(dynamodb)
cli.add_command(register_eventbridge_commands())
cli.add_command(ssm)


def _collect_command_names(group: click.Group) -> set:
    """Recursively collect all valid command names from a Click group."""
    names = set()
    for name, cmd in group.commands.items():
        names.add(name)
        if isinstance(cmd, click.Group):
            names.update(_collect_command_names(cmd))
    return names


def _parse_command_name(argv: list) -> str | None:
    """Extract the full command path from argv, ignoring flags and argument values."""
    known = _collect_command_names(cli)
    tokens = [a for a in argv if not a.startswith("-") and a in known]
    return " ".join(tokens) if tokens else None


def main():
    from cli_tool.core.utils.telemetry import capture_command, capture_error, show_first_run_notice
    from cli_tool.core.utils.version_check import show_update_notification

    show_first_run_notice()

    import sys

    cmd_name = _parse_command_name(sys.argv[1:])

    telemetry_thread = None
    try:
        cli(obj={})
        telemetry_thread = capture_command(cmd_name, success=True)
    except SystemExit as e:
        telemetry_thread = capture_command(cmd_name, success=(e.code == 0))
        raise
    except Exception as e:
        telemetry_thread = capture_error(cmd_name, e)
        raise
    finally:
        if telemetry_thread:
            telemetry_thread.join(timeout=2)
        show_update_notification()


if __name__ == "__main__":
    main()
