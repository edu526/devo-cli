"""Interactive SSO profile configuration."""

import json
import subprocess

import click
from rich.console import Console

from cli_tool.aws_login.core.config import (
    get_aws_config_path,
    get_existing_sso_sessions,
    get_profile_config,
)
from cli_tool.aws_login.core.credentials import get_sso_cache_token

console = Console()


def configure_profile_with_existing_session(profile_name, session_name):
    """Configure a profile using an existing SSO session."""
    console.print("[yellow]Logging in to get available accounts...[/yellow]\n")

    # First, ensure we're logged in to the SSO session
    login_cmd = ["aws", "sso", "login", "--sso-session", session_name]

    try:
        result = subprocess.run(login_cmd, timeout=120)

        if result.returncode != 0:
            console.print("[red]✗ SSO authentication failed[/red]")
            return None

    except subprocess.TimeoutExpired:
        console.print("[red]✗ SSO authentication timed out[/red]")
        return None
    except KeyboardInterrupt:
        console.print("\n[yellow]Authentication cancelled[/yellow]")
        return None

    # Get the SSO session config to find the start URL
    config_path = get_aws_config_path()
    session_section = f"[sso-session {session_name}]"
    sso_start_url = None
    sso_region = None

    try:
        with open(config_path, "r") as f:
            in_session = False
            for line in f:
                line = line.strip()
                if line == session_section:
                    in_session = True
                elif line.startswith("["):
                    in_session = False
                elif in_session and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key == "sso_start_url":
                        sso_start_url = value
                    elif key == "sso_region":
                        sso_region = value
    except Exception:
        pass

    if not sso_start_url:
        console.print("[red]Could not find SSO start URL[/red]")
        console.print("\n[blue]Enter account and role details manually:[/blue]\n")
        account_id = click.prompt("AWS Account ID", type=str)
        role_name = click.prompt("Role name", default="AdministratorAccess", type=str)
        region = click.prompt("Default region", default="us-east-1", type=str)
    else:
        # Try to get access token from cache
        access_token = get_sso_cache_token(sso_start_url)

        if access_token:
            # List available accounts
            console.print("\n[blue]Fetching available accounts...[/blue]\n")

            list_accounts_cmd = ["aws", "sso", "list-accounts", "--access-token", access_token, "--region", sso_region or "us-east-1"]

            try:
                result = subprocess.run(list_accounts_cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    accounts_data = json.loads(result.stdout)
                    accounts = accounts_data.get("accountList", [])

                    if accounts:
                        console.print("[green]Available accounts:[/green]")
                        for i, account in enumerate(accounts, 1):
                            account_id = account.get("accountId")
                            account_name = account.get("accountName", "N/A")
                            console.print(f"  {i}. {account_name} ({account_id})")

                        account_choice = click.prompt("\nSelect account", type=int, default=1)

                        if 1 <= account_choice <= len(accounts):
                            selected_account = accounts[account_choice - 1]
                            account_id = selected_account["accountId"]

                            # Get roles for this account
                            console.print(f"\n[blue]Fetching roles for account {account_id}...[/blue]\n")

                            list_roles_cmd = [
                                "aws",
                                "sso",
                                "list-account-roles",
                                "--access-token",
                                access_token,
                                "--account-id",
                                account_id,
                                "--region",
                                sso_region or "us-east-1",
                            ]

                            result = subprocess.run(list_roles_cmd, capture_output=True, text=True, timeout=30)

                            if result.returncode == 0:
                                roles_data = json.loads(result.stdout)
                                roles = roles_data.get("roleList", [])

                                if roles:
                                    console.print("[green]Available roles:[/green]")
                                    for i, role in enumerate(roles, 1):
                                        role_name_item = role.get("roleName")
                                        console.print(f"  {i}. {role_name_item}")

                                    role_choice = click.prompt("\nSelect role", type=int, default=1)

                                    if 1 <= role_choice <= len(roles):
                                        role_name = roles[role_choice - 1]["roleName"]
                                    else:
                                        console.print("[yellow]Invalid selection, using default[/yellow]")
                                        role_name = roles[0]["roleName"]
                                else:
                                    console.print("[yellow]No roles found, enter manually[/yellow]")
                                    role_name = click.prompt("Role name", default="AdministratorAccess", type=str)
                            else:
                                console.print("[yellow]Could not fetch roles, enter manually[/yellow]")
                                role_name = click.prompt("Role name", default="AdministratorAccess", type=str)

                            region = click.prompt("\nDefault region", default="us-east-1", type=str)
                        else:
                            console.print("[red]Invalid selection[/red]")
                            return None
                    else:
                        console.print("[yellow]No accounts found[/yellow]")
                        console.print("\n[blue]Enter account and role details manually:[/blue]\n")
                        account_id = click.prompt("AWS Account ID", type=str)
                        role_name = click.prompt("Role name", default="AdministratorAccess", type=str)
                        region = click.prompt("Default region", default="us-east-1", type=str)
                else:
                    console.print(f"[yellow]Could not list accounts: {result.stderr}[/yellow]")
                    console.print("\n[blue]Enter account and role details manually:[/blue]\n")
                    account_id = click.prompt("AWS Account ID", type=str)
                    role_name = click.prompt("Role name", default="AdministratorAccess", type=str)
                    region = click.prompt("Default region", default="us-east-1", type=str)
            except Exception as e:
                console.print(f"[yellow]Error listing accounts: {e}[/yellow]")
                console.print("\n[blue]Enter account and role details manually:[/blue]\n")
                account_id = click.prompt("AWS Account ID", type=str)
                role_name = click.prompt("Role name", default="AdministratorAccess", type=str)
                region = click.prompt("Default region", default="us-east-1", type=str)
        else:
            console.print("[yellow]Could not get access token from cache[/yellow]")
            console.print("\n[blue]Enter account and role details manually:[/blue]\n")
            account_id = click.prompt("AWS Account ID", type=str)
            role_name = click.prompt("Role name", default="AdministratorAccess", type=str)
            region = click.prompt("Default region", default="us-east-1", type=str)

    # Write profile configuration
    config_path = get_aws_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    profile_section = f"[profile {profile_name}]" if profile_name != "default" else "[default]"

    new_profile = f"""
{profile_section}
sso_session = {session_name}
sso_account_id = {account_id}
sso_role_name = {role_name}
region = {region}
output = json
"""

    # Append new profile
    with open(config_path, "a") as f:
        f.write("\n")
        f.write(new_profile.strip())
        f.write("\n")

    console.print(f"\n[green]✓ Profile '{profile_name}' configured successfully[/green]")
    return profile_name


def configure_sso_profile(profile_name=None):
    """Interactive SSO profile configuration using AWS CLI."""
    console.print("\n[blue]═══ AWS SSO Configuration ═══[/blue]\n")

    # Profile name
    if not profile_name:
        profile_name = click.prompt(
            "Profile name",
            default="default",
            type=str,
        )

    # Check if profile already exists
    existing_config = get_profile_config(profile_name)
    if existing_config:
        console.print(f"[yellow]⚠ Profile '{profile_name}' already exists:[/yellow]\n")
        if "sso_account_id" in existing_config:
            console.print(f"  Account: {existing_config.get('sso_account_id')}")
        if "sso_role_name" in existing_config:
            console.print(f"  Role: {existing_config.get('sso_role_name')}")
        if "sso_start_url" in existing_config:
            console.print(f"  SSO URL: {existing_config.get('sso_start_url')}")

        # Check if it's an SSO profile
        is_sso = "sso_start_url" in existing_config or "sso_session" in existing_config

        console.print("\nOptions:")
        if is_sso:
            console.print("  1. Keep and login (recommended)")
        else:
            console.print("  1. Keep profile (not SSO, cannot login)")
        console.print("  2. Reconfigure (overwrite)")
        console.print("  3. New profile name")
        console.print("  4. Cancel")
        choice = click.prompt("\nSelect", type=int, default=1)
        if choice == 1:
            if not is_sso:
                console.print(f"[yellow]Profile '{profile_name}' is not configured for SSO[/yellow]")
                console.print("Choose option 2 to reconfigure it for SSO")
                return None
            return profile_name
        elif choice == 2:
            if not click.confirm(f"\n⚠ Overwrite '{profile_name}'?", default=False):
                return None
        elif choice == 3:
            new_name = click.prompt("\nNew name", type=str)
            if get_profile_config(new_name):
                console.print(f"[red]'{new_name}' exists too[/red]")
                return None
            profile_name = new_name
        else:
            return None
        console.print("")

    # Check for existing SSO sessions
    existing_sessions = get_existing_sso_sessions()

    if existing_sessions:
        console.print("[green]Found existing SSO sessions:[/green]")
        session_list = list(existing_sessions.items())
        for i, (session_name, config) in enumerate(session_list, 1):
            sso_url = config.get("sso_start_url", "N/A")
            console.print(f"  {i}. {session_name} - {sso_url}")
        console.print(f"  {len(session_list) + 1}. Create new SSO session")
        console.print("")

        choice = click.prompt("Select SSO session", type=int, default=1)

        if 1 <= choice <= len(session_list):
            # Use existing session
            session_name, session_config = session_list[choice - 1]
            console.print(f"\n[cyan]Using SSO session: {session_name}[/cyan]")
            console.print(f"SSO URL: {session_config.get('sso_start_url', 'N/A')}\n")

            # Configure profile with existing session
            return configure_profile_with_existing_session(profile_name, session_name)

    console.print(f"[cyan]Configuring profile: {profile_name}[/cyan]\n")

    # Use AWS CLI's built-in SSO configuration
    console.print("[yellow]Using AWS CLI to configure SSO...[/yellow]")
    console.print("[dim]This will open your browser to authenticate and select account/role[/dim]\n")

    cmd = ["aws", "configure", "sso", "--profile", profile_name]

    try:
        # Run AWS CLI configure sso interactively
        result = subprocess.run(cmd)

        if result.returncode == 0:
            console.print(f"\n[green]✓ Profile '{profile_name}' configured successfully[/green]")
            return profile_name
        else:
            console.print("\n[red]✗ Configuration failed[/red]")
            return None

    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration cancelled[/yellow]")
        return None
    except Exception as e:
        console.print(f"\n[red]Error during configuration: {e}[/red]")
        return None
