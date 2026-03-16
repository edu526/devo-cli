"""AWS SSO Login command implementation."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from cli_tool.commands.aws_login.commands import (
    configure_sso_profile,
    list_profiles,
    perform_login,
    refresh_all_profiles,
    set_default_profile,
)
from cli_tool.core.utils.aws import check_aws_cli
from cli_tool.core.utils.config_manager import get_config_value


def _set_default_hint() -> str:
    """Return a hint pointing to the exact set-default command, using the configured profile if known."""
    profile = get_config_value("aws_login.default_credentials_profile")
    cmd = f"devo aws-login set-default {profile}" if profile else "devo aws-login set-default"
    return f"[dim]  Run '{cmd}' to refresh them.[/dim]\n"


console = Console()


def _warn_expiry(expiry_str: str) -> None:
    """Warn if credentials are expired or expiring soon."""
    expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if expiry_dt <= now:
        console.print("[yellow]⚠ Default credentials in ~/.aws/credentials have expired.[/yellow]")
        console.print(_set_default_hint())
        return
    minutes_left = int((expiry_dt - now).total_seconds() / 60)
    if minutes_left < 30:
        console.print(f"[yellow]⚠ Default credentials expire in {minutes_left} min.[/yellow]")
        console.print(_set_default_hint())


def _check_credentials_via_cli(in_default: bool) -> None:
    """Check [default] credentials expiry via AWS CLI and warn if needed."""
    import subprocess

    result = subprocess.run(
        ["aws", "configure", "export-credentials", "--profile", "default"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        creds = json.loads(result.stdout)
        expiry_str = creds.get("Expiration")
        if expiry_str:
            _warn_expiry(expiry_str)
    elif in_default:
        console.print("[yellow]⚠ Default credentials in ~/.aws/credentials may be expired.[/yellow]")
        console.print(_set_default_hint())


def _check_default_credentials_expiry():
    """Warn if [default] credentials in ~/.aws/credentials are expired or missing."""
    credentials_path = Path.home() / ".aws" / "credentials"
    if not credentials_path.exists():
        return

    in_default = False

    try:
        with open(credentials_path, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped == "[default]":
                    in_default = True
                elif stripped.startswith("[") and in_default:
                    break

        _check_credentials_via_cli(in_default)
    except Exception:
        pass


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

    # Warn if [default] credentials are expired or expiring soon
    _check_default_credentials_expiry()

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
@click.option("--set-env", is_flag=True, default=False, help="Also export AWS_PROFILE in shell config (~/.bashrc, ~/.zshrc, etc.).")
def set_default_cmd(profile, set_env):
    """Set a profile as the default.

    Writes temporary credentials as [default] in ~/.aws/credentials so the
    AWS CLI works without --profile. By default, the shell config file is NOT
    modified.

    Pass --set-env to also persist AWS_PROFILE in your shell config
    (~/. bashrc, ~/.zshrc, or equivalent). This behaviour can be enabled
    permanently via: devo config set aws_login.set_env_profile true

    Examples:
      devo aws-login set-default production
      devo aws-login set-default  # interactive selection
      devo aws-login set-default production --set-env
    """
    set_default_profile(profile, set_env=set_env or None)


if __name__ == "__main__":
    aws_login()
