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


def _refresh_session(_session_key: str, session_profs: list) -> tuple:
    """Login to an SSO session and verify all profiles in it.

    Returns (success, verified_count, failed_count).
    """
    console.print(f"\n[blue]Refreshing session for {len(session_profs)} profile(s)...[/blue]")
    first_profile = session_profs[0]
    prof_config = get_profile_config(first_profile)

    if prof_config and "sso_session" in prof_config:
        login_cmd = ["aws", "sso", "login", "--sso-session", prof_config["sso_session"]]
    else:
        login_cmd = ["aws", "sso", "login", "--profile", first_profile]

    try:
        result = subprocess.run(login_cmd, timeout=120)
        if result.returncode != 0:
            console.print("[red]✗ Session refresh failed[/red]")
            for prof in session_profs:
                console.print(f"  ✗ {prof}")
            return False, 0, len(session_profs)

        console.print("[green]✓ Session refreshed successfully[/green]")
        verified = failed = 0
        for prof in session_profs:
            if verify_credentials(prof):
                console.print(f"  ✓ {prof}")
                verified += 1
            else:
                console.print(f"  ✗ {prof} (verification failed)")
                failed += 1
        return True, verified, failed

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Session refresh timed out[/red]")
        return False, 0, len(session_profs)
    except KeyboardInterrupt:
        console.print("\n[yellow]Refresh cancelled[/yellow]")
        sys.exit(1)


def refresh_all_profiles():
    """Refresh all profiles that are expired or expiring soon."""
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found[/yellow]")
        sys.exit(0)

    console.print("[blue]Checking all profiles for expiration...[/blue]\n")

    profiles_to_refresh = []
    profiles_valid = []

    for prof, source in profiles:
        needs_refresh, expiration, reason = check_profile_needs_refresh(prof)

        if needs_refresh:
            profiles_to_refresh.append((prof, reason))
        else:
            if expiration:
                # Calculate time left using UTC times
                now_utc = datetime.now(timezone.utc)
                time_left = expiration - now_utc
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                profiles_valid.append((prof, f"{hours}h {minutes}m remaining"))

    if not profiles_to_refresh:
        console.print("[green]✓ All profiles have valid credentials[/green]\n")

        if profiles_valid:
            table = Table(title="Profile Status")
            table.add_column("Profile", style="cyan")
            table.add_column("Time Remaining", style="green")

            for prof, time_info in profiles_valid:
                table.add_row(prof, time_info)

            console.print(table)

        sys.exit(0)

    # Show profiles that need refresh
    console.print(f"[yellow]Found {len(profiles_to_refresh)} profile(s) that need refresh:[/yellow]\n")

    for prof, reason in profiles_to_refresh:
        console.print(f"  • {prof}: {reason}")

    console.print("")

    if not click.confirm("Refresh these profiles?", default=True):
        console.print("[yellow]Refresh cancelled[/yellow]")
        sys.exit(0)

    # Group profiles by SSO session to minimize logins
    session_profiles = {}
    for prof, reason in profiles_to_refresh:
        prof_config = get_profile_config(prof)
        if prof_config:
            sso_session = prof_config.get("sso_session")
            sso_url = prof_config.get("sso_start_url")

            key = sso_session or sso_url
            if key:
                if key not in session_profiles:
                    session_profiles[key] = []
                session_profiles[key].append(prof)

    # Refresh each session
    success_count = 0
    fail_count = 0

    for session_key, session_profs in session_profiles.items():
        _, verified, failed = _refresh_session(session_key, session_profs)
        success_count += verified
        fail_count += failed

    # Summary
    console.print("\n[blue]═══ Refresh Summary ═══[/blue]")
    console.print(f"[green]✓ Refreshed: {success_count}[/green]")
    if fail_count > 0:
        console.print(f"[red]✗ Failed: {fail_count}[/red]")
