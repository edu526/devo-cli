"""Status display for AWS profiles."""

import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from cli_tool.aws_login.config import get_profile_config, list_aws_profiles
from cli_tool.aws_login.credentials import get_profile_credentials_expiration

console = Console()


def show_status():
    """Show detailed expiration status for all profiles."""
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found[/yellow]")
        sys.exit(0)

    console.print("[blue]═══ AWS Profile Expiration Status ═══[/blue]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Profile", style="cyan", width=20)
    table.add_column("Source", style="dim", width=12)
    table.add_column("Status", width=15)
    table.add_column("Expires At (Local)", width=25)
    table.add_column("Time Remaining", width=20)

    for prof, source in profiles:
        # For static credentials, show appropriate message
        if source == "static":
            table.add_row(prof, source, "[dim]Static[/dim]", "N/A", "N/A")
            continue

        prof_config = get_profile_config(prof)

        if not prof_config:
            table.add_row(prof, source, "[yellow]No Config[/yellow]", "N/A", "N/A")
            continue

        # Check if SSO profile
        has_sso = "sso_start_url" in prof_config or "sso_session" in prof_config

        if not has_sso:
            table.add_row(prof, source, "[dim]Not SSO[/dim]", "N/A", "N/A")
            continue

        # Get expiration of account credentials (not SSO token)
        expiration = get_profile_credentials_expiration(prof)

        if not expiration:
            table.add_row(prof, source, "[red]No Credentials[/red]", "N/A", "N/A")
            continue

        # Calculate time left
        now_utc = datetime.now(timezone.utc)
        time_left = expiration - now_utc

        # Convert to local time for display
        expiration_local = expiration.astimezone()
        expires_str = expiration_local.strftime("%Y-%m-%d %H:%M:%S")

        # Status and time remaining
        if time_left.total_seconds() <= 0:
            status_str = "[red]Expired[/red]"
            time_str = "[red]Expired[/red]"
        elif time_left.total_seconds() <= 600:  # 10 minutes
            minutes_left = int(time_left.total_seconds() / 60)
            status_str = "[yellow]Expiring Soon[/yellow]"
            time_str = f"[yellow]{minutes_left}m[/yellow]"
        else:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            status_str = "[green]Valid[/green]"
            time_str = f"[green]{hours}h {minutes}m[/green]"

        table.add_row(prof, source, status_str, expires_str, time_str)

    console.print(table)
    console.print(f"\n[dim]Current time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
    console.print(f"\n[dim]Current time (Local): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
