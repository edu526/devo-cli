"""Refresh expired/expiring credentials for all profiles."""

import subprocess
import sys
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table

from cli_tool.commands.aws_login.core.config import get_profile_config, list_aws_profiles
from cli_tool.commands.aws_login.core.credentials import (
    check_profile_needs_refresh,
    verify_credentials,
)

console = Console()


def _build_sso_login_cmd(first_profile: str) -> list:
    """Build the 'aws sso login' command for the given profile."""
    prof_config = get_profile_config(first_profile)
    if prof_config and "sso_session" in prof_config:
        return ["aws", "sso", "login", "--sso-session", prof_config["sso_session"]]
    return ["aws", "sso", "login", "--profile", first_profile]


def _verify_session_profiles(session_profs: list) -> tuple:
    """Verify credentials for each profile in the session. Returns (verified_count, failed_count)."""
    console.print("[green]✓ Session refreshed successfully[/green]")
    verified = failed = 0
    for prof in session_profs:
        if verify_credentials(prof):
            console.print(f"  ✓ {prof}")
            verified += 1
        else:
            console.print(f"  ✗ {prof} (verification failed)")
            failed += 1
    return verified, failed


def _refresh_session(_session_key: str, session_profs: list) -> tuple:
    """Login to an SSO session and verify all profiles in it.

    Returns (success, verified_count, failed_count).
    """
    console.print(f"\n[blue]Refreshing session for {len(session_profs)} profile(s)...[/blue]")
    login_cmd = _build_sso_login_cmd(session_profs[0])

    try:
        result = subprocess.run(login_cmd, timeout=120)
        if result.returncode != 0:
            console.print("[red]✗ Session refresh failed[/red]")
            for prof in session_profs:
                console.print(f"  ✗ {prof}")
            return False, 0, len(session_profs)

        verified, failed = _verify_session_profiles(session_profs)
        return True, verified, failed

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Session refresh timed out[/red]")
        return False, 0, len(session_profs)
    except KeyboardInterrupt:
        console.print("\n[yellow]Refresh cancelled[/yellow]")
        sys.exit(1)


def _classify_profiles(profiles: list) -> tuple:
    """Classify each profile as needing refresh or still valid.

    Returns (profiles_to_refresh, profiles_valid) where:
      - profiles_to_refresh: list of (prof, reason)
      - profiles_valid: list of (prof, time_remaining_str)
    """
    profiles_to_refresh = []
    profiles_valid = []

    for prof, _source in profiles:
        needs_refresh, expiration, reason = check_profile_needs_refresh(prof)
        if needs_refresh:
            profiles_to_refresh.append((prof, reason))
        elif expiration:
            now_utc = datetime.now(timezone.utc)
            time_left = expiration - now_utc
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            profiles_valid.append((prof, f"{hours}h {minutes}m remaining"))

    return profiles_to_refresh, profiles_valid


def _show_valid_profiles_table(profiles_valid: list) -> None:
    """Render a Rich table of valid profiles and their remaining time."""
    table = Table(title="Profile Status")
    table.add_column("Profile", style="cyan")
    table.add_column("Time Remaining", style="green")
    for prof, time_info in profiles_valid:
        table.add_row(prof, time_info)
    console.print(table)


def _group_profiles_by_session(profiles_to_refresh: list) -> dict:
    """Group profiles by their SSO session key to minimise login prompts."""
    session_profiles = {}
    for prof, _reason in profiles_to_refresh:
        prof_config = get_profile_config(prof)
        if not prof_config:
            continue
        key = prof_config.get("sso_session") or prof_config.get("sso_start_url")
        if key:
            session_profiles.setdefault(key, []).append(prof)
    return session_profiles


def _confirm_refresh(profiles_to_refresh: list) -> bool:
    """Display profiles that need refresh and ask for user confirmation. Returns True if confirmed."""
    console.print(f"[yellow]Found {len(profiles_to_refresh)} profile(s) that need refresh:[/yellow]\n")
    for prof, reason in profiles_to_refresh:
        console.print(f"  • {prof}: {reason}")
    console.print("")
    return click.confirm("Refresh these profiles?", default=True)


def _refresh_all_sessions(session_profiles: dict) -> tuple:
    """Refresh each session group and aggregate counts. Returns (success_count, fail_count)."""
    success_count = 0
    fail_count = 0
    for session_key, session_profs in session_profiles.items():
        _, verified, failed = _refresh_session(session_key, session_profs)
        success_count += verified
        fail_count += failed
    return success_count, fail_count


def refresh_all_profiles():
    """Refresh all profiles that are expired or expiring soon."""
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found[/yellow]")
        sys.exit(0)

    console.print("[blue]Checking all profiles for expiration...[/blue]\n")

    profiles_to_refresh, profiles_valid = _classify_profiles(profiles)

    if not profiles_to_refresh:
        console.print("[green]✓ All profiles have valid credentials[/green]\n")
        if profiles_valid:
            _show_valid_profiles_table(profiles_valid)
        sys.exit(0)

    if not _confirm_refresh(profiles_to_refresh):
        console.print("[yellow]Refresh cancelled[/yellow]")
        sys.exit(0)

    # Group profiles by SSO session to minimize logins
    session_profiles = _group_profiles_by_session(profiles_to_refresh)

    success_count, fail_count = _refresh_all_sessions(session_profiles)

    # Summary
    console.print("\n[blue]═══ Refresh Summary ═══[/blue]")
    console.print(f"[green]✓ Refreshed: {success_count}[/green]")
    if fail_count > 0:
        console.print(f"[red]✗ Failed: {fail_count}[/red]")
