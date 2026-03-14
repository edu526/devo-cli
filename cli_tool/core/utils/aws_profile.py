"""AWS profile selection and credential verification utilities."""

import json
import subprocess

import click

from cli_tool.config import AWS_ACCOUNT_ID, AWS_REQUIRED_ROLE, AWS_SSO_URL

# Configuration
REQUIRED_ACCOUNT = AWS_ACCOUNT_ID
REQUIRED_ROLE = AWS_REQUIRED_ROLE


def get_aws_profiles():
    """
    Get available AWS profiles from config and credentials files.

    Returns:
        List of tuples (profile_name, source) where source is:
        - 'sso': Profile only in config with SSO configuration
        - 'static': Profile only in credentials
        - 'both': Profile in both config and credentials
        - 'config': Profile in config without SSO
    """
    from cli_tool.commands.aws_login.core.config import list_aws_profiles

    # Get profiles with source information
    profiles = list_aws_profiles()

    return profiles if profiles else []


def verify_aws_credentials(profile=None, required_account=None):  # noqa: ARG001
    """Verify AWS credentials and account.

    Args:
      profile: AWS profile name (optional)
      required_account: Required AWS account ID (optional, unused — kept for API compatibility)

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


def _verify_and_check_account(profile_name: str, required_account, show_messages: bool) -> bool:
    """Verify credentials for a profile and optionally check the account ID.

    Returns True if credentials are valid and account matches (when required).
    """
    account_id, _ = verify_aws_credentials(profile_name)
    if not account_id:
        if show_messages:
            click.echo("")
            click.echo(click.style(f"Error: Profile '{profile_name}' has invalid or expired credentials", fg="red"))
            click.echo("")
            click.echo(click.style("Get fresh credentials from:", fg="blue"))
            click.echo(f"  {AWS_SSO_URL}")
            click.echo("")
            click.echo(f"Then run: aws configure --profile {profile_name}")
        return False

    if required_account and account_id != required_account:
        if show_messages:
            click.echo("")
            click.echo(click.style(f"Error: Profile is for account {account_id}", fg="red"))
            click.echo(click.style(f"Required account: {required_account}", fg="red"))
            click.echo("")
        return False

    return True


def _pick_profile_from_list(profiles: list, required_account, show_messages: bool):
    """Prompt the user to pick a profile from a list. Returns profile name or None."""
    click.echo(click.style("Available AWS profiles:", fg="blue"))
    for i, (profile_name, source) in enumerate(profiles, 1):
        click.echo(f"  {i}. {profile_name} [{source}]")
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
            selected_profile, _ = profiles[index]
            if not _verify_and_check_account(selected_profile, required_account, show_messages):
                return None
            return selected_profile
    except ValueError:
        pass

    if show_messages:
        click.echo(click.style("Invalid selection", fg="red"))
    return None


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

    if len(profiles) == 1:
        selected_profile, source = profiles[0]
        if not _verify_and_check_account(selected_profile, required_account, show_messages):
            return None
        if show_messages:
            click.echo(click.style(f"✓ Using profile: {selected_profile} [{source}]", fg="green"))
        return selected_profile

    return _pick_profile_from_list(profiles, required_account, show_messages)


def _handle_wrong_account(account_id: str, required_account: str, show_messages: bool) -> None:
    """Print an error message when the selected profile belongs to the wrong account."""
    if show_messages:
        click.echo("")
        click.echo(click.style("Error: Selected profile is for wrong AWS account", fg="red"))
        click.echo(click.style(f"Expected: {required_account}", fg="red"))
        click.echo(click.style(f"Got: {account_id}", fg="red"))
        click.echo("")


def ensure_aws_profile(profile=None, required_account=None, show_messages=True):
    """Ensure AWS profile is configured and valid.

    Args:
      profile: AWS profile name (optional)
      required_account: Required AWS account ID (optional)
      show_messages: If True, show informational messages

    Returns:
      Tuple of (profile, account_id, user_arn) or (None, None, None) if failed
    """
    account_id, user_arn = verify_aws_credentials(profile, required_account)

    if account_id:
        if not required_account or account_id == required_account:
            return profile, account_id, user_arn

        if show_messages:
            click.echo(click.style(f"Current credentials are for account: {account_id}", fg="yellow"))
            click.echo(click.style(f"Required account: {required_account}", fg="yellow"))
            click.echo("")

    selected_profile = select_aws_profile(required_account, show_messages)
    if not selected_profile:
        return None, None, None

    account_id, user_arn = verify_aws_credentials(selected_profile, required_account)
    if not account_id:
        return None, None, None

    if required_account and account_id != required_account:
        _handle_wrong_account(account_id, required_account, show_messages)
        return None, None, None

    return selected_profile, account_id, user_arn
