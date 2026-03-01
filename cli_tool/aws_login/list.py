"""List AWS profiles."""

import sys

from rich.console import Console
from rich.table import Table

from cli_tool.aws_login.config import list_aws_profiles
from cli_tool.aws_login.credentials import verify_credentials

console = Console()


def list_profiles():
    """List all available AWS profiles with their status."""
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found in ~/.aws/config[/yellow]")
        console.print("\nTo configure SSO, run:")
        console.print("  aws configure sso")
        sys.exit(0)

    table = Table(title="Available AWS Profiles")
    table.add_column("Profile", style="cyan")
    table.add_column("Status", style="green")

    for prof in profiles:
        identity = verify_credentials(prof)
        status = "✓ Active" if identity else "✗ Expired/Invalid"
        table.add_row(prof, status)

    console.print(table)
