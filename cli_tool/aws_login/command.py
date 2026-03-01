"""AWS SSO Login command implementation."""

import sys

import click
from rich.console import Console

from cli_tool.aws_login.list import list_profiles
from cli_tool.aws_login.login import perform_login
from cli_tool.aws_login.refresh import refresh_all_profiles
from cli_tool.aws_login.set_default import set_default_profile
from cli_tool.aws_login.setup import configure_sso_profile
from cli_tool.aws_login.status import show_status
from cli_tool.utils.aws import check_aws_cli

console = Console()


@click.command()
@click.option(
    "--profile",
    "-p",
    help="AWS profile name to login",
)
@click.option(
    "--list",
    "-l",
    "list_profiles_flag",
    is_flag=True,
    help="List available AWS profiles",
)
@click.option(
    "--configure",
    "-c",
    is_flag=True,
    help="Configure a new SSO profile interactively",
)
@click.option(
    "--refresh-all",
    "-r",
    is_flag=True,
    help="Refresh all profiles that are expired or expiring soon (within 10 minutes)",
)
@click.option(
    "--status",
    "-s",
    is_flag=True,
    help="Show detailed expiration status for all profiles",
)
@click.option(
    "--set-default",
    "-d",
    is_flag=True,
    help="Set a profile as the default (updates shell configuration)",
)
def aws_login(profile, list_profiles_flag, configure, refresh_all, status, set_default):
    """Login to AWS using SSO and cache credentials.

    Automates the AWS SSO login process by:
    - Opening browser for SSO authentication
    - Caching credentials automatically
    - Showing credential expiration time

    Examples:
      devo aws-login --profile production
      devo aws-login -p dev
      devo aws-login --list
      devo aws-login --configure
      devo aws-login --configure --profile my-profile
      devo aws-login --refresh-all
      devo aws-login --status
      devo aws-login --set-default --profile production
    """
    # Check if AWS CLI is installed
    if not check_aws_cli():
        sys.exit(1)

    # Set default profile
    if set_default:
        set_default_profile(profile)
        sys.exit(0)

    # Show detailed status
    if status:
        show_status()
        sys.exit(0)

    # Refresh all profiles that need it
    if refresh_all:
        refresh_all_profiles()
        sys.exit(0)

    # Configure new profile
    if configure:
        profile_name = configure_sso_profile(profile)
        if not profile_name:
            sys.exit(1)

        console.print("[blue]Profile configured! Now logging in...[/blue]\n")
        profile = profile_name
        # Continue to login flow

    # List profiles
    if list_profiles_flag:
        list_profiles()
        sys.exit(0)

    # Login flow
    perform_login(profile)


if __name__ == "__main__":
    aws_login()
