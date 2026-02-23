import os

import click
from rich.console import Console

from cli_tool.commands.code_reviewer import code_reviewer
from cli_tool.commands.codeartifact_login import codeartifact_login
from cli_tool.commands.commit_prompt import commit
from cli_tool.commands.completion import completion
from cli_tool.commands.config import config
from cli_tool.commands.eventbridge import eventbridge
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
    envvar="AWS_PROFILE",
    default=None,
    help="AWS profile to use (must come before command, e.g., 'devo --profile dev eventbridge')",
)
@click.version_option(__version__, "-v", "--version", prog_name="devo", message="%(version)s")
@click.pass_context
def cli(ctx, profile):
    """CLI for developers with AI-powered features."""
    import sys

    # Ensure context object exists
    ctx.ensure_object(dict)

    # If no profile specified, check if credentials exist
    if not profile:
        profile = os.environ.get("AWS_PROFILE")

    # Check if we need AWS credentials (skip for help, version, and completion commands)
    # Also skip if --help or -h is in the command line arguments
    # Skip for commands that don't need AWS: upgrade, config, completion
    skip_profile_check = (
        ctx.invoked_subcommand in ["completion", "upgrade", "config", None]
        or "--help" in sys.argv
        or "-h" in sys.argv
        or "--version" in sys.argv
        or "-v" in sys.argv
    )

    # For AWS commands, ensure profile is set (auto-select or prompt if needed)
    if not skip_profile_check and not profile:
        from cli_tool.utils.aws_profile import get_aws_profiles

        profiles = get_aws_profiles()

        if len(profiles) == 0:
            # No profiles found, let AWS CLI handle the error
            pass
        elif len(profiles) == 1:
            # Auto-select if only one profile exists
            profile = profiles[0]
            click.echo(click.style(f"✓ Using profile: {profile}", fg="green"))
            click.echo("")
        elif "default" in profiles:
            # If default exists, use it automatically
            profile = "default"
            click.echo(click.style(f"✓ Using profile: {profile}", fg="green"))
            click.echo("")
        else:
            # Multiple profiles without default - prompt user to select
            click.echo(click.style("Multiple AWS profiles found:", fg="blue"))
            for i, p in enumerate(profiles, 1):
                click.echo(f"  {i}. {p}")
            click.echo("")

            choice = click.prompt("Select a profile number", type=int, default=1)

            if 1 <= choice <= len(profiles):
                profile = profiles[choice - 1]
                click.echo(click.style(f"✓ Using profile: {profile}", fg="green"))
                click.echo("")
            else:
                click.echo(click.style("Invalid selection", fg="red"))
                sys.exit(1)

    # Store profile in context for all subcommands
    ctx.obj["profile"] = profile

    # Set AWS_PROFILE environment variable if profile is specified
    if profile:
        os.environ["AWS_PROFILE"] = profile


cli.add_command(commit)
cli.add_command(upgrade)
cli.add_command(codeartifact_login)
cli.add_command(completion)
cli.add_command(code_reviewer)
cli.add_command(config)
cli.add_command(eventbridge)


def main():
    try:
        cli(obj={})
    finally:
        # Show update notification after command execution
        from cli_tool.utils.version_check import show_update_notification

        show_update_notification()


if __name__ == "__main__":
    main()
