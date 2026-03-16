"""AWS SSO login flow."""

import subprocess
import sys
from datetime import datetime, timezone

import click
from rich.console import Console

from cli_tool.commands.aws_login.commands.setup import configure_sso_profile
from cli_tool.commands.aws_login.core.config import list_aws_profiles, parse_sso_config, select_profile_interactively
from cli_tool.commands.aws_login.core.credentials import (
    get_profile_credentials_expiration,
    verify_credentials,
    write_default_credentials,
)
from cli_tool.core.utils.config_manager import get_config_value

console = Console()

_CONFIGURE_HINT = "  devo aws-login configure"
_MANUAL_SSO_HINT = "  aws configure sso"


def _resolve_profile_name() -> str:
    """Prompt user to select or configure a profile. Returns profile name or exits."""
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found in ~/.aws/config[/yellow]\n")
        console.print("Would you like to configure a new SSO profile?")
        if click.confirm("Configure SSO profile now?", default=True):
            profile_name = configure_sso_profile()
            if not profile_name:
                sys.exit(1)
            console.print("\n[blue]Profile configured! Now logging in...[/blue]\n")
            return profile_name
        console.print("\nTo configure SSO, run:")
        console.print(_CONFIGURE_HINT)
        console.print("\nOr manually:")
        console.print(_MANUAL_SSO_HINT)
        sys.exit(1)
    return select_profile_interactively(profiles)


def _show_login_success(profile_name: str, identity: dict) -> None:
    """Display successful login info including credential expiration."""
    console.print("\n[green]✓ Credentials cached successfully[/green]")
    console.print(f"\nAccount: {identity['account']}")
    console.print(f"ARN: {identity['arn']}")

    expiration = get_profile_credentials_expiration(profile_name)
    if expiration:
        expiration_local = expiration.astimezone()
        now_utc = datetime.now(timezone.utc)
        time_left = expiration - now_utc
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        expiration_str = expiration_local.strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"\n[yellow]Credentials expire at: {expiration_str} (local time)[/yellow]")
        console.print(f"[yellow]Time remaining: {hours}h {minutes}m[/yellow]")
    else:
        console.print("\n[yellow]Note: Account credentials typically expire in 1 hour[/yellow]")

    console.print("\nTo use this profile:")
    console.print(f"  export AWS_PROFILE={profile_name}")
    console.print("  # or")
    console.print(f"  aws s3 ls --profile {profile_name}")


def _update_default_credentials_if_needed(profile_name: str) -> None:
    """Re-write [default] credentials if profile_name is the configured default."""
    if get_config_value("aws_login.default_credentials_profile") != profile_name:
        return
    console.print(f"\n[blue]Updating [default] credentials for '{profile_name}'...[/blue]")
    result = write_default_credentials(profile_name)
    if result:
        console.print("[green]✓ ~/.aws/credentials [default] updated[/green]")
        if result.get("expiration"):
            console.print(f"[dim]  Expires: {result['expiration']}[/dim]")
    else:
        console.print("[yellow]⚠ Could not update [default] credentials[/yellow]")


def _run_sso_login(profile_name: str) -> None:
    """Execute AWS SSO login and handle result."""
    cmd = ["aws", "sso", "login", "--profile", profile_name]
    try:
        result = subprocess.run(cmd, timeout=120)
        if result.returncode == 0:
            console.print("[green]✓ SSO authentication successful[/green]")
            identity = verify_credentials(profile_name)
            if identity:
                _show_login_success(profile_name, identity)
            else:
                console.print("[yellow]Warning: Authentication succeeded but credentials verification failed[/yellow]")
            _update_default_credentials_if_needed(profile_name)
        else:
            console.print("[red]✗ SSO authentication failed[/red]")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]✗ SSO authentication timed out[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Authentication cancelled[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error during authentication: {e}[/red]")
        sys.exit(1)


def perform_login(profile_name=None):
    """Perform SSO login for a profile."""
    if not profile_name:
        profile_name = _resolve_profile_name()

    console.print(f"\n[blue]Logging in to AWS with profile: {profile_name}[/blue]")

    # Parse SSO config
    sso_config = parse_sso_config(profile_name)
    if not sso_config:
        console.print(f"[yellow]Profile '{profile_name}' is not configured for SSO[/yellow]")
        console.print("\nTo configure SSO, run:")
        console.print(_CONFIGURE_HINT)
        console.print("\nOr manually:")
        console.print(f"  aws configure sso --profile {profile_name}")
        sys.exit(1)

    # Show SSO info
    console.print(f"\nSSO URL: {sso_config.get('sso_start_url', 'N/A')}")
    console.print(f"Account: {sso_config.get('sso_account_id', 'N/A')}")
    console.print(f"Role: {sso_config.get('sso_role_name', 'N/A')}")
    console.print(f"Region: {sso_config.get('region', 'N/A')}")

    # Start SSO login
    console.print("\n[yellow]Opening browser for SSO authentication...[/yellow]")

    with console.status("[blue]Waiting for SSO authentication...", spinner="dots"):
        _run_sso_login(profile_name)
