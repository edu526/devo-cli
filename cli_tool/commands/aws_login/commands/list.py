"""List AWS profiles with detailed status."""

import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from cli_tool.commands.aws_login.core.config import get_profile_config, list_aws_profiles
from cli_tool.commands.aws_login.core.credentials import get_profile_credentials_expiration
from cli_tool.core.ui.brand import spinner

console = Console()


def _build_profile_row(prof: str, source: str) -> tuple:
    """Return (prof, source, status_str, expires_str, time_str) for a single profile."""
    if source == "static":
        return (prof, source, "[dim]Static[/dim]", "N/A", "N/A")

    prof_config = get_profile_config(prof)
    if not prof_config:
        return (prof, source, "[yellow]No Config[/yellow]", "N/A", "N/A")

    has_sso = "sso_start_url" in prof_config or "sso_session" in prof_config
    if not has_sso:
        return (prof, source, "[dim]Not SSO[/dim]", "N/A", "N/A")

    expiration = get_profile_credentials_expiration(prof)
    if not expiration:
        return (prof, source, "[red]No Credentials[/red]", "N/A", "N/A")

    now_utc = datetime.now(timezone.utc)
    time_left = expiration - now_utc
    expiration_local = expiration.astimezone()
    expires_str = expiration_local.strftime("%Y-%m-%d %H:%M:%S")

    if time_left.total_seconds() <= 0:
        status_str = "[red]Expired[/red]"
        time_str = "[red]Expired[/red]"
    elif time_left.total_seconds() <= 600:
        minutes_left = int(time_left.total_seconds() / 60)
        status_str = "[yellow]Expiring Soon[/yellow]"
        time_str = f"[yellow]{minutes_left}m[/yellow]"
    else:
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        status_str = "[green]Valid[/green]"
        time_str = f"[green]{hours}h {minutes}m[/green]"

    return (prof, source, status_str, expires_str, time_str)


def list_profiles():
    """List all available AWS profiles with detailed status."""
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found[/yellow]")
        sys.exit(0)

    console.print("[blue]═══ AWS Profiles ═══[/blue]\n")

    rows = []
    with spinner("Checking credentials for all profiles..."):
        for prof, source in profiles:
            rows.append(_build_profile_row(prof, source))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Profile", style="cyan", width=20)
    table.add_column("Source", style="dim", width=12)
    table.add_column("Status", width=15)
    table.add_column("Expires At (Local)", width=25)
    table.add_column("Time Remaining", width=20)

    for row in rows:
        table.add_row(*row)

    console.print(table)
