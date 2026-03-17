import os

import click

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

# Commands grouped by category for the help screen
_COMMAND_GROUPS = {
    "Git": ["commit", "code-reviewer"],
    "AWS": ["aws-login", "codeartifact-login", "dynamodb", "eventbridge", "ssm"],
    "Tools": ["autocomplete", "config", "upgrade"],
}

# Known aliases: actual command name → list of aliases
_ALIASES_MAP = {
    "codeartifact-login": ["ca-login"],
}


class BrandedGroup(click.Group):
    """Custom Click Group with Rich-powered help and command aliases."""

    def get_command(self, ctx, cmd_name):
        # Resolve aliases to actual command names
        reverse = {alias: real for real, aliases in _ALIASES_MAP.items() for alias in aliases}
        cmd_name = reverse.get(cmd_name, cmd_name)
        return super().get_command(ctx, cmd_name)

    def format_help(self, ctx, formatter):
        """Render help with ASCII banner + categorized commands."""
        from cli_tool.core.ui.brand import banner_as_ansi

        # Inject the banner into Click's formatter buffer
        formatter.write(banner_as_ansi(width=formatter.width))

        # Standard usage line and description
        self.format_usage(ctx, formatter)
        if self.help:
            formatter.write_paragraph()
            with formatter.indentation():
                formatter.write_text(self.help)

        # format_options internally calls format_commands (which we override below)
        self.format_options(ctx, formatter)

    def format_commands(self, ctx, formatter):
        """Write commands grouped by category (replaces flat Commands section)."""
        for group_name, cmd_names in _COMMAND_GROUPS.items():
            commands = []
            for name in cmd_names:
                cmd = self.get_command(ctx, name)
                if cmd is None:
                    continue
                display_name = name
                if name in _ALIASES_MAP:
                    aliases = ", ".join(_ALIASES_MAP[name])
                    display_name = f"{name} ({aliases})"
                commands.append((display_name, cmd.get_short_help_str(limit=formatter.width)))

            if commands:
                with formatter.section(group_name):
                    formatter.write_dl(commands)


# Backwards-compatible alias used by tests
AliasedGroup = BrandedGroup

try:
    from cli_tool._version import version as __version__
except ImportError:
    try:
        from setuptools_scm import get_version

        __version__ = get_version(root="..", relative_to=__file__)
    except Exception:
        __version__ = "unknown"


def _print_version(value, ctx):
    if not value or ctx.resilient_parsing:
        return
    import sys

    is_dev = ".dev" in __version__ or "+" in __version__
    base_version = __version__.split(".dev")[0].split("+")[0]

    if not sys.stdout.isatty():
        # Non-interactive (pipe/script) → plain string for scripting
        click.echo(f"{base_version}-dev" if is_dev else base_version)
    else:
        from cli_tool.core.ui.brand import render_version_header

        render_version_header()

    ctx.exit()


@click.group(cls=BrandedGroup)
@click.option(
    "--profile",
    default=None,
    help="AWS profile to use (must come before command, e.g., 'devo --profile dev eventbridge')",
)
@click.option(
    "-v",
    "--version",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    help="Show the version and exit.",
    callback=lambda ctx, _param, value: _print_version(value, ctx),
)
@click.pass_context
def cli(ctx, profile):
    """CLI for developers with AI-powered features."""
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile

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
