"""AWS profile selection and credential verification utilities."""

import json
import os
import subprocess

import click

from cli_tool.config import AWS_ACCOUNT_ID, AWS_REQUIRED_ROLE, AWS_SSO_URL

# Configuration
REQUIRED_ACCOUNT = AWS_ACCOUNT_ID
REQUIRED_ROLE = AWS_REQUIRED_ROLE


def get_aws_profiles():
    """Get available AWS profiles from credentials file."""
    credentials_file = os.path.expanduser("~/.aws/credentials")
    if not os.path.exists(credentials_file):
        return []

    profiles = []
    try:
        with open(credentials_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    profile = line[1:-1]
                    profiles.append(profile)
    except Exception:
        pass

    return profiles


def verify_aws_credentials(profile=None, required_account=None):
    """Verify AWS credentials and account.

    Args:
      profile: AWS profile name (optional)
      required_account: Required AWS account ID (optional)

    Returns:
      Tuple of (account_id, user_arn)
    """
    cmd = ["aws", "sts", "get-caller-identity", "--output", "json"]
    if profile:
        cmd.extend(["--profile", profile])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return None, None

        identity = json.loads(result.stdout)
        return identity.get("Account"), identity.get("Arn")
    except Exception:
        return None, None


def select_aws_profile(required_account=None, show_messages=True):
    """Interactive AWS profile selection.

    Args:
      required_account: Required AWS account ID (optional)
      show_messages: If True, show informational messages

    Returns:
      Selected profile name or None
    """
    if show_messages:
        click.echo(click.style("No active AWS credentials found", fg="yellow"))
        click.echo("")
        click.echo(click.style("Get your AWS credentials from:", fg="blue"))
        click.echo(f"  {AWS_SSO_URL}")
        click.echo("")

    profiles = get_aws_profiles()

    if not profiles:
        if show_messages:
            click.echo(click.style("No AWS profiles found", fg="red"))
            click.echo("")
            click.echo(click.style("Get your AWS credentials from:", fg="blue"))
            click.echo(f"  {AWS_SSO_URL}")
            click.echo("")
            click.echo("Then run: aws configure")
        return None

    # If only one profile, use it automatically
    if len(profiles) == 1:
        selected_profile = profiles[0]

        # Verify the profile works
        account_id, user_arn = verify_aws_credentials(selected_profile, required_account)
        if not account_id:
            if show_messages:
                click.echo("")
                click.echo(
                    click.style(
                        f"Error: Profile '{selected_profile}' has invalid or expired credentials",
                        fg="red",
                    )
                )
                click.echo("")
                click.echo(click.style("Get fresh credentials from:", fg="blue"))
                click.echo(f"  {AWS_SSO_URL}")
                click.echo("")
                click.echo(f"Then run: aws configure --profile {selected_profile}")
            return None

        # Check account if required
        if required_account and account_id != required_account:
            if show_messages:
                click.echo("")
                click.echo(click.style(f"Error: Profile is for account {account_id}", fg="red"))
                click.echo(click.style(f"Required account: {required_account}", fg="red"))
                click.echo("")
            return None

        if show_messages:
            click.echo(click.style(f"✓ Using profile: {selected_profile}", fg="green"))
        return selected_profile

    # Always show the profile list
    click.echo(click.style("Available AWS profiles:", fg="blue"))
    for i, profile in enumerate(profiles, 1):
        click.echo(f"  {i}. {profile}")
    click.echo("")

    choice = click.prompt(
        "Select a profile number (or press Enter to skip)",
        type=str,
        default="",
        show_default=False,
    )

    if not choice:
        if show_messages:
            click.echo("")
            click.echo(click.style("No profile selected", fg="yellow"))
            click.echo("")
        return None

    try:
        index = int(choice) - 1
        if 0 <= index < len(profiles):
            selected_profile = profiles[index]

            # Verify the selected profile works
            account_id, user_arn = verify_aws_credentials(selected_profile, required_account)
            if not account_id:
                if show_messages:
                    click.echo("")
                    click.echo(
                        click.style(
                            f"Error: Selected profile '{selected_profile}' has invalid or expired credentials",
                            fg="red",
                        )
                    )
                    click.echo("")
                    click.echo(click.style("Get fresh credentials from:", fg="blue"))
                    click.echo(f"  {AWS_SSO_URL}")
                    click.echo("")
                    click.echo(f"Then run: aws configure --profile {selected_profile}")
                return None

            # Check account if required
            if required_account and account_id != required_account:
                if show_messages:
                    click.echo("")
                    click.echo(
                        click.style(
                            f"Error: Selected profile is for account {account_id}",
                            fg="red",
                        )
                    )
                    click.echo(click.style(f"Required account: {required_account}", fg="red"))
                    click.echo("")
                return None

            return selected_profile
    except ValueError:
        pass

    if show_messages:
        click.echo(click.style("Invalid selection", fg="red"))
    return None


def ensure_aws_profile(profile=None, required_account=None, show_messages=True):
    """Ensure AWS profile is configured and valid.

    Args:
      profile: AWS profile name (optional)
      required_account: Required AWS account ID (optional)
      show_messages: If True, show informational messages

    Returns:
      Tuple of (profile, account_id, user_arn) or (None, None, None) if failed
    """
    # Check current credentials
    account_id, user_arn = verify_aws_credentials(profile, required_account)

    # If credentials are valid and account matches (if required), return them
    if account_id:
        if not required_account or account_id == required_account:
            return profile, account_id, user_arn

        # Wrong account
        if show_messages:
            click.echo(click.style(f"Current credentials are for account: {account_id}", fg="yellow"))
            if required_account:
                click.echo(click.style(f"Required account: {required_account}", fg="yellow"))
            click.echo("")

    # Try to select a profile
    selected_profile = select_aws_profile(required_account, show_messages)
    if not selected_profile:
        return None, None, None

    # Verify the selected profile
    account_id, user_arn = verify_aws_credentials(selected_profile, required_account)
    if not account_id:
        return None, None, None

    # Check account if required
    if required_account and account_id != required_account:
        if show_messages:
            click.echo("")
            click.echo(click.style("Error: Selected profile is for wrong AWS account", fg="red"))
            click.echo(click.style(f"Expected: {required_account}", fg="red"))
            click.echo(click.style(f"Got: {account_id}", fg="red"))
            click.echo("")
        return None, None, None

    return selected_profile, account_id, user_arn
