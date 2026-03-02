"""AWS SSO Login command implementation."""

import sys

import click
from rich.console import Console

from cli_tool.aws_login.commands import (
    configure_sso_profile,
    list_profiles,
    perform_login,
    refresh_all_profiles,
    set_default_profile,
)
from cli_tool.utils.aws import check_aws_cli

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def aws_login(ctx):
    """AWS SSO authentication and profile management.

    Login to AWS using SSO (default action):
      devo aws-login                # interactive profile selection

    Login to specific profile:
      devo aws-login login production

    Other commands:
      devo aws-login list           # list all profiles with status
      devo aws-login configure      # configure new profile
      devo aws-login refresh        # refresh expired credentials
      devo aws-login set-default    # set default profile
    """
    # Check if AWS CLI is installed
    if not check_aws_cli():
        sys.exit(1)

    # If a subcommand was invoked, let it handle the request
    if ctx.invoked_subcommand is not None:
        return

    # Otherwise, perform interactive login
    perform_login(None)


@aws_login.command("login")
@click.argument("profile", required=False)
def login_cmd(profile):
    """Login to AWS using SSO with a specific profile.

    Opens browser for SSO authentication and caches credentials.

    Examples:
      devo aws-login login production
      devo aws-login login  # interactive selection
    """
    perform_login(profile)


@aws_login.command("list")
def list_cmd():
    """List all AWS profiles with detailed status.

    Shows profiles from both ~/.aws/config and ~/.aws/credentials
    with their source (SSO, static, or both), credential status,
    expiration time, and time remaining.
    """
    list_profiles()


@aws_login.command("configure")
@click.argument("profile", required=False)
def configure_cmd(profile):
    """Configure a new SSO profile interactively.

    Guides you through setting up a new AWS SSO profile with
    account selection and role assignment.

    Examples:
      devo aws-login configure
      devo aws-login configure my-profile
    """
    profile_name = configure_sso_profile(profile)
    if not profile_name:
        sys.exit(1)

    console.print("\n[blue]Profile configured! Now logging in...[/blue]\n")
    perform_login(profile_name)


@aws_login.command("refresh")
def refresh_cmd():
    """Refresh expired or expiring credentials.

    Checks all profiles and refreshes those that are expired
    or expiring within 10 minutes. Groups profiles by SSO
    session to minimize login prompts.
    """
    refresh_all_profiles()


@aws_login.command("set-default")
@click.argument("profile", required=False)
def set_default_cmd(profile):
    """Set a profile as the default.

    Updates shell configuration to export AWS_PROFILE environment
    variable. On Linux/macOS, updates ~/.bashrc or ~/.zshrc.
    On Windows, sets user environment variable.

    Examples:
      devo aws-login set-default production
      devo aws-login set-default  # interactive selection
    """
    set_default_profile(profile)


if __name__ == "__main__":
    aws_login()
