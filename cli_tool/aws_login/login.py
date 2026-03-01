"""AWS SSO login flow."""

import subprocess
import sys
from datetime import datetime, timezone

import click
from rich.console import Console

from cli_tool.aws_login.config import list_aws_profiles, parse_sso_config
from cli_tool.aws_login.credentials import (
    get_profile_credentials_expiration,
    verify_credentials,
)
from cli_tool.aws_login.setup import configure_sso_profile

console = Console()


def perform_login(profile_name=None):
    """Perform SSO login for a profile."""
    if not profile_name:
        # Show available profiles
        profiles = list_aws_profiles()
        if not profiles:
            console.print("[yellow]No AWS profiles found in ~/.aws/config[/yellow]\n")
            console.print("Would you like to configure a new SSO profile?")

            if click.confirm("Configure SSO profile now?", default=True):
                profile_name = configure_sso_profile()
                if not profile_name:
                    sys.exit(1)
                console.print("\n[blue]Profile configured! Now logging in...[/blue]\n")
            else:
                console.print("\nTo configure SSO manually, run:")
                console.print("  aws configure sso")
                console.print("\nOr use:")
                console.print("  devo aws-login --configure")
                sys.exit(1)
        else:
            console.print("[blue]Available profiles:[/blue]")
            for i, prof in enumerate(profiles, 1):
                console.print(f"  {i}. {prof}")

            choice = click.prompt("\nSelect profile number", type=int)
            if 1 <= choice <= len(profiles):
                profile_name = profiles[choice - 1]
            else:
                console.print("[red]Invalid selection[/red]")
                sys.exit(1)

    console.print(f"\n[blue]Logging in to AWS with profile: {profile_name}[/blue]")

    # Parse SSO config
    sso_config = parse_sso_config(profile_name)
    if not sso_config:
        console.print(f"[yellow]Profile '{profile_name}' is not configured for SSO[/yellow]")
        console.print("\nTo configure SSO, run:")
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
        # Use AWS CLI SSO login
        cmd = ["aws", "sso", "login", "--profile", profile_name]

        try:
            result = subprocess.run(cmd, timeout=120)

            if result.returncode == 0:
                console.print("[green]✓ SSO authentication successful[/green]")

                # Verify credentials
                identity = verify_credentials(profile_name)
                if identity:
                    console.print("\n[green]✓ Credentials cached successfully[/green]")
                    console.print(f"\nAccount: {identity['account']}")
                    console.print(f"ARN: {identity['arn']}")

                    # Get actual expiration time of account credentials
                    expiration = get_profile_credentials_expiration(profile_name)
                    if expiration:
                        # Convert to local time for display
                        expiration_local = expiration.astimezone()

                        # Calculate time left using UTC times
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
                else:
                    console.print("[yellow]Warning: Authentication succeeded but credentials verification failed[/yellow]")

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
