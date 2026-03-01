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
    from cli_tool.utils.aws_profile import get_aws_profiles

    # If profile already set, use it
    if current_profile:
        return current_profile

    # Get available profiles
    profiles = get_aws_profiles()

    if len(profiles) == 0:
        if allow_none:
            return None
        click.echo(click.style("No AWS profiles found", fg="red"))
        click.echo("Configure AWS CLI first: aws configure")
        raise click.Abort()

    if len(profiles) == 1:
        # Auto-select if only one profile exists
        profile = profiles[0]
        click.echo(click.style(f"✓ Using profile: {profile}", fg="green"))
        click.echo("")
        return profile

    # Multiple profiles - prompt user to select
    click.echo(click.style("Multiple AWS profiles found:", fg="blue"))
    for i, p in enumerate(profiles, 1):
        # Highlight default profile if it exists
        if p == "default":
            click.echo(f"  {i}. {p} [default]")
        else:
            click.echo(f"  {i}. {p}")
    click.echo("")

    # Set default choice to "default" profile if it exists, otherwise first
    default_choice = profiles.index("default") + 1 if "default" in profiles else 1
    choice = click.prompt("Select a profile number", type=int, default=default_choice)

    if 1 <= choice <= len(profiles):
        profile = profiles[choice - 1]
        click.echo(click.style(f"✓ Using profile: {profile}", fg="green"))
        click.echo("")
        return profile
    else:
        click.echo(click.style("Invalid selection", fg="red"))
        raise click.Abort()


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
        pass

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
