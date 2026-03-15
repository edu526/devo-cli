"""Interactive SSO profile configuration."""

import json
import subprocess

import click
from rich.console import Console

from cli_tool.commands.aws_login.core.config import (
    get_aws_config_path,
    get_existing_sso_sessions,
    get_profile_config,
    remove_profile_section,
)
from cli_tool.commands.aws_login.core.credentials import get_sso_cache_token

console = Console()

_CANNOT_USE_DEFAULT = "[red]✗ Cannot use 'default' as a profile name.[/red]"
_USE_SET_DEFAULT_HINT = "[dim]Use 'devo aws-login set-default' to set a profile as default.[/dim]"
_ROLE_NAME_PROMPT = "Role name"
_MANUAL_ACCOUNT_ROLE_PROMPT = "\n[blue]Enter account and role details manually:[/blue]\n"


def _prompt_manual_account_role_region() -> tuple:
    """Prompt user to enter account, role, and region manually."""
    account_id = click.prompt("AWS Account ID", type=str)
    role_name = click.prompt(_ROLE_NAME_PROMPT, default="AdministratorAccess", type=str)
    region = click.prompt("Default region", default="us-east-1", type=str)
    return account_id, role_name, region


def _read_sso_session_config(config_path, session_name: str) -> tuple:
    """Read sso_start_url and sso_region from a named sso-session section."""
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
    return sso_start_url, sso_region


def _select_role_from_list(roles: list) -> str:
    """Display role list and prompt user to select one. Returns the selected role name."""
    console.print("[green]Available roles:[/green]")
    for i, role in enumerate(roles, 1):
        console.print(f"  {i}. {role.get('roleName')}")
    role_choice = click.prompt("\nSelect role", type=int, default=1)
    return roles[role_choice - 1]["roleName"] if 1 <= role_choice <= len(roles) else roles[0]["roleName"]


def _fetch_role_for_account(account_id: str, sso_region: str, access_token: str) -> str:
    """Fetch available roles for an account and prompt user to select one. Falls back to manual entry."""
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
        roles = json.loads(result.stdout).get("roleList", [])
        if roles:
            return _select_role_from_list(roles)
        console.print("[yellow]No roles found, enter manually[/yellow]")
    else:
        console.print("[yellow]Could not fetch roles, enter manually[/yellow]")

    return click.prompt(_ROLE_NAME_PROMPT, default="AdministratorAccess", type=str)


def _select_account_from_list(accounts: list, sso_region: str, access_token: str) -> tuple:
    """Display account list, prompt selection, then fetch and select a role. Returns (account_id, role_name, region)."""
    console.print("[green]Available accounts:[/green]")
    for i, account in enumerate(accounts, 1):
        account_id = account.get("accountId")
        account_name = account.get("accountName", "N/A")
        console.print(f"  {i}. {account_name} ({account_id})")

    account_choice = click.prompt("\nSelect account", type=int, default=1)
    if not (1 <= account_choice <= len(accounts)):
        console.print("[red]Invalid selection[/red]")
        return None, None, None

    selected_account = accounts[account_choice - 1]
    account_id = selected_account["accountId"]

    role_name = _fetch_role_for_account(account_id, sso_region, access_token)

    region = click.prompt("\nDefault region", default="us-east-1", type=str)
    return account_id, role_name, region


def _resolve_account_role_region(access_token: str, sso_region: str) -> tuple:
    """Fetch accounts via SSO and interactively select account/role/region. Falls back to manual entry."""
    console.print("\n[blue]Fetching available accounts...[/blue]\n")
    list_accounts_cmd = ["aws", "sso", "list-accounts", "--access-token", access_token, "--region", sso_region or "us-east-1"]
    try:
        result = subprocess.run(list_accounts_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            accounts = json.loads(result.stdout).get("accountList", [])
            if accounts:
                return _select_account_from_list(accounts, sso_region, access_token)
            console.print("[yellow]No accounts found[/yellow]")
        else:
            console.print(f"[yellow]Could not list accounts: {result.stderr}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Error listing accounts: {e}[/yellow]")

    console.print(_MANUAL_ACCOUNT_ROLE_PROMPT)
    return _prompt_manual_account_role_region()


def _write_profile_config(profile_name: str, session_name: str, account_id: str, role_name: str, region: str) -> None:
    """Write the profile section to ~/.aws/config."""
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
    remove_profile_section(profile_name)
    with open(config_path, "a") as f:
        f.write("\n")
        f.write(new_profile.strip())
        f.write("\n")


def _sso_login_for_session(session_name: str) -> bool:
    """Run 'aws sso login' for the given session. Returns True on success."""
    console.print("[yellow]Logging in to get available accounts...[/yellow]\n")
    try:
        result = subprocess.run(["aws", "sso", "login", "--sso-session", session_name], timeout=120)
        if result.returncode != 0:
            console.print("[red]✗ SSO authentication failed[/red]")
            return False
    except subprocess.TimeoutExpired:
        console.print("[red]✗ SSO authentication timed out[/red]")
        return False
    except KeyboardInterrupt:
        console.print("\n[yellow]Authentication cancelled[/yellow]")
        return False
    return True


def _resolve_account_role_region_for_session(sso_start_url: str, sso_region: str) -> tuple:
    """Resolve account/role/region using SSO cache token or fall back to manual entry."""
    access_token = get_sso_cache_token(sso_start_url)
    if access_token:
        return _resolve_account_role_region(access_token, sso_region)
    console.print("[yellow]Could not get access token from cache[/yellow]")
    console.print(_MANUAL_ACCOUNT_ROLE_PROMPT)
    return _prompt_manual_account_role_region()


def configure_profile_with_existing_session(profile_name, session_name):
    """Configure a profile using an existing SSO session."""
    if not _sso_login_for_session(session_name):
        return None

    config_path = get_aws_config_path()
    sso_start_url, sso_region = _read_sso_session_config(config_path, session_name)

    if not sso_start_url:
        console.print("[red]Could not find SSO start URL[/red]")
        console.print(_MANUAL_ACCOUNT_ROLE_PROMPT)
        account_id, role_name, region = _prompt_manual_account_role_region()
    else:
        account_id, role_name, region = _resolve_account_role_region_for_session(sso_start_url, sso_region)
        if account_id is None:
            return None

    _write_profile_config(profile_name, session_name, account_id, role_name, region)
    console.print(f"\n[green]✓ Profile '{profile_name}' configured successfully[/green]")
    return profile_name


def _print_existing_profile_info(existing_config: dict) -> None:
    """Print details of an existing profile configuration."""
    if "sso_account_id" in existing_config:
        console.print(f"  Account: {existing_config.get('sso_account_id')}")
    if "sso_role_name" in existing_config:
        console.print(f"  Role: {existing_config.get('sso_role_name')}")
    if "sso_start_url" in existing_config:
        console.print(f"  SSO URL: {existing_config.get('sso_start_url')}")


def _handle_choice_keep(profile_name: str, is_sso: bool) -> tuple:
    """Handle 'keep and login' choice. Returns (profile_name, should_continue)."""
    if not is_sso:
        console.print(f"[yellow]Profile '{profile_name}' is not configured for SSO[/yellow]")
        console.print("Choose option 2 to reconfigure it for SSO")
        return None, False
    return profile_name, False


def _handle_choice_overwrite(profile_name: str) -> tuple:
    """Handle 'reconfigure/overwrite' choice. Returns (profile_name, should_continue)."""
    if not click.confirm(f"\n⚠ Overwrite '{profile_name}'?", default=False):
        return None, False
    console.print("")
    return profile_name, True


def _handle_choice_new_name() -> tuple:
    """Handle 'new profile name' choice. Returns (new_name, should_continue)."""
    new_name = click.prompt("\nNew name", type=str)
    if new_name.lower() == "default":
        console.print(_CANNOT_USE_DEFAULT)
        console.print(_USE_SET_DEFAULT_HINT)
        return None, False
    if get_profile_config(new_name):
        console.print(f"[red]'{new_name}' exists too[/red]")
        return None, False
    console.print("")
    return new_name, True


def _handle_existing_profile_choice(profile_name: str, existing_config: dict) -> tuple:
    """Prompt user for action when profile already exists.

    Returns (resolved_profile_name, should_continue) where should_continue=False means abort.
    """
    console.print(f"[yellow]⚠ Profile '{profile_name}' already exists:[/yellow]\n")
    _print_existing_profile_info(existing_config)

    is_sso = "sso_start_url" in existing_config or "sso_session" in existing_config

    console.print("\nOptions:")
    console.print("  1. Keep and login (recommended)" if is_sso else "  1. Keep profile (not SSO, cannot login)")
    console.print("  2. Reconfigure (overwrite)")
    console.print("  3. New profile name")
    console.print("  4. Cancel")
    choice = click.prompt("\nSelect", type=int, default=1)

    if choice == 1:
        return _handle_choice_keep(profile_name, is_sso)
    if choice == 2:
        return _handle_choice_overwrite(profile_name)
    if choice == 3:
        return _handle_choice_new_name()
    return None, False


def _select_or_create_session(profile_name: str) -> str:
    """Let user pick an existing SSO session or fall through to create a new one.

    Returns the profile_name if an existing session was used, otherwise None
    (caller should proceed with 'aws configure sso').
    """
    existing_sessions = get_existing_sso_sessions()
    if not existing_sessions:
        return None

    session_list = list(existing_sessions.items())
    console.print("[green]Found existing SSO sessions:[/green]")
    for i, (session_name, config) in enumerate(session_list, 1):
        sso_url = config.get("sso_start_url", "N/A")
        console.print(f"  {i}. {session_name} - {sso_url}")
    console.print(f"  {len(session_list) + 1}. Create new SSO session")
    console.print("")

    choice = click.prompt("Select SSO session", type=int, default=1)

    if 1 <= choice <= len(session_list):
        session_name, session_config = session_list[choice - 1]
        console.print(f"\n[cyan]Using SSO session: {session_name}[/cyan]")
        console.print(f"SSO URL: {session_config.get('sso_start_url', 'N/A')}\n")
        return configure_profile_with_existing_session(profile_name, session_name)

    return None


def _run_aws_configure_sso(profile_name: str) -> str:
    """Run 'aws configure sso' interactively and return profile_name on success, None on failure."""
    console.print(f"[cyan]Configuring profile: {profile_name}[/cyan]\n")
    console.print("[yellow]Using AWS CLI to configure SSO...[/yellow]")
    console.print("[dim]This will open your browser to authenticate and select account/role[/dim]\n")

    try:
        result = subprocess.run(["aws", "configure", "sso", "--profile", profile_name])
        if result.returncode == 0:
            console.print(f"\n[green]✓ Profile '{profile_name}' configured successfully[/green]")
            return profile_name
        console.print("\n[red]✗ Configuration failed[/red]")
        return None
    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration cancelled[/yellow]")
        return None
    except Exception as e:
        console.print(f"\n[red]Error during configuration: {e}[/red]")
        return None


def configure_sso_profile(profile_name=None):
    """Interactive SSO profile configuration using AWS CLI."""
    console.print("\n[blue]═══ AWS SSO Configuration ═══[/blue]\n")

    if not profile_name:
        profile_name = click.prompt("Profile name", type=str)

    if profile_name.lower() == "default":
        console.print(_CANNOT_USE_DEFAULT)
        console.print(_USE_SET_DEFAULT_HINT)
        return None

    # Check if profile already exists
    existing_config = get_profile_config(profile_name)
    if existing_config:
        profile_name, should_continue = _handle_existing_profile_choice(profile_name, existing_config)
        if profile_name is None:
            return None
        if not should_continue:
            # choice was "keep and login" — return the confirmed profile name directly
            return profile_name

    # Check for existing SSO sessions and let user pick one
    result = _select_or_create_session(profile_name)
    if result is not None:
        return result

    return _run_aws_configure_sso(profile_name)
