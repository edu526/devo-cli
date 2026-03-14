"""AWS utilities and session management."""

import json
import subprocess
from typing import Optional

import boto3
import click
from botocore.config import Config


def select_profile(current_profile: Optional[str] = None, allow_none: bool = False) -> Optional[str]:
    """
    Select AWS profile interactively if not provided.

    Args:
        current_profile: Current profile from context or environment
        allow_none: If True, allows returning None (for commands that don't require AWS)

    Returns:
        Selected profile name or None
    """
    from cli_tool.core.utils.aws_profile import get_aws_profiles

    # If profile already set, use it
    if current_profile:
        return current_profile

    # Get available profiles (list of tuples: (name, source))
    profiles = get_aws_profiles()

    if len(profiles) == 0:
        if allow_none:
            return None
        click.echo(click.style("No AWS profiles found", fg="red"))
        click.echo("To configure SSO, run: devo aws-login --configure")
        raise click.Abort()

    if len(profiles) == 1:
        # Auto-select if only one profile exists
        profile_name, source = profiles[0]
        click.echo(click.style(f"✓ Using profile: {profile_name} [{source}]", fg="green"))
        click.echo("")
        return profile_name

    # Multiple profiles - prompt user to select
    click.echo(click.style("Available profiles:", fg="blue"))
    for i, (profile_name, source) in enumerate(profiles, 1):
        # Format source label
        if source == "sso":
            source_label = click.style("[sso]", fg="cyan")
        elif source == "static":
            source_label = click.style("[static]", fg="yellow")
        elif source == "both":
            source_label = click.style("[sso+static]", fg="green")
        else:
            source_label = click.style("[config]", fg="white")

        # Highlight default profile if it exists
        if profile_name == "default":
            click.echo(f"  {i}. {profile_name} {source_label} [default]")
        else:
            click.echo(f"  {i}. {profile_name} {source_label}")
    click.echo("")

    # Set default choice to "default" profile if it exists, otherwise first
    profile_names = [p[0] for p in profiles]
    default_choice = profile_names.index("default") + 1 if "default" in profile_names else 1

    # Loop until we get valid input
    while True:
        try:
            choice_str = click.prompt("Select profile number", type=str, default=str(default_choice))
            # Strip any whitespace and non-numeric characters (handles escape codes)
            choice_str = "".join(c for c in choice_str if c.isdigit())

            if not choice_str:
                choice = default_choice
            else:
                choice = int(choice_str)

            if 1 <= choice <= len(profiles):
                profile_name, source = profiles[choice - 1]
                click.echo(click.style(f"✓ Using profile: {profile_name} [{source}]", fg="green"))
                click.echo("")
                return profile_name
            else:
                click.echo(click.style(f"Invalid selection. Please enter a number between 1 and {len(profiles)}", fg="red"))
        except (ValueError, KeyboardInterrupt):
            click.echo(click.style("\nInvalid input. Please enter a number.", fg="red"))
        except click.Abort:
            raise


def check_aws_cli() -> bool:
    """Check if AWS CLI is installed (does not check credentials)"""
    try:
        # Check if AWS CLI is installed
        version_result = subprocess.run(["aws", "--version"], capture_output=True, text=True, timeout=5)
        if version_result.returncode != 0:
            click.echo("❌ AWS CLI is not installed. Please install it first.", err=True)
            return False

        return True
    except FileNotFoundError:
        click.echo("❌ AWS CLI is not installed. Please install it first.", err=True)
        return False
    except Exception as e:
        click.echo(f"❌ Error checking AWS CLI: {str(e)}", err=True)
        return False


def _get_credentials_from_cli(profile_name: Optional[str] = None):
    """Get credentials using AWS CLI export-credentials command."""
    cmd = ["aws", "configure", "export-credentials"]
    if profile_name:
        cmd.extend(["--profile", profile_name])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            creds = json.loads(result.stdout)
            return {
                "access_key": creds.get("AccessKeyId"),
                "secret_key": creds.get("SecretAccessKey"),
                "token": creds.get("SessionToken"),
                "expiry_time": creds.get("Expiration"),
            }
    except Exception:
        return None

    return None


def create_aws_session(profile_name: Optional[str] = None, region_name: Optional[str] = None) -> boto3.Session:
    """
    Create a boto3 session with proper credential handling.

    This function uses AWS CLI to get credentials, bypassing boto3's SSO token refresh.

    Args:
      profile_name: AWS profile name
      region_name: AWS region

    Returns:
      boto3.Session configured to use cached credentials
    """
    # Try to get credentials from AWS CLI
    creds = _get_credentials_from_cli(profile_name)

    if creds and creds["access_key"]:
        # Create session with explicit credentials
        session = boto3.Session(
            aws_access_key_id=creds["access_key"],
            aws_secret_access_key=creds["secret_key"],
            aws_session_token=creds["token"],
            region_name=region_name,
        )
        return session

    # Fallback to default session (will use environment or config)
    return boto3.Session(profile_name=profile_name, region_name=region_name)


def create_aws_client(service_name: str, profile_name: Optional[str] = None, region_name: Optional[str] = None, **kwargs):
    """
    Create a boto3 client with proper credential handling.

    Args:
      service_name: AWS service name (e.g., 'dynamodb', 's3')
      profile_name: AWS profile name
      region_name: AWS region
      **kwargs: Additional arguments to pass to boto3.client()

    Returns:
      boto3 client for the specified service
    """
    session = create_aws_session(profile_name, region_name)

    # Create client config
    config = Config(retries={"max_attempts": 3, "mode": "standard"})

    return session.client(service_name, config=config, **kwargs)
