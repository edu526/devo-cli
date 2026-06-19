"""Hosts setup command."""

from typing import Optional

import click
from rich.console import Console

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.hosts_setup import setup_databases as _run_setup

console = Console()


def setup_databases(db_names: Optional[list[str]] = None) -> tuple[list[str], list[str]]:
    """Run setup and print per-db results. Returns (succeeded_names, failed_names).

    Thin CLI wrapper around the pure core in `cli_tool.commands.ssm.core.hosts_setup`.
    Kept for backward-compat with callers/tests that expect name-only lists.
    """
    succeeded, failed = _run_setup(db_names)

    for entry in succeeded:
        port_note = ""
        if entry["port_reassigned"]:
            port_note = f" (local port conflict, assigned {entry['local_port']})"
        console.print(f"[green]✓[/green] {entry['name']}: {entry['host']} -> {entry['ip']}:{entry['local_port']}{port_note}")
    for entry in failed:
        console.print(f"[red]✗[/red] {entry['name']}: {entry['error']}")

    return [e["name"] for e in succeeded], [e["name"] for e in failed]


@click.command()
def hosts_setup():
    """Setup /etc/hosts entries for all configured databases"""
    config_manager = SSMConfigManager()
    databases = config_manager.list_databases()

    if not databases:
        console.print("[yellow]No databases configured[/yellow]")
        return

    console.print("[cyan]Setting up /etc/hosts entries...[/cyan]\n")

    succeeded, failed = setup_databases()

    if failed and not succeeded:
        console.print("\n[red]Setup failed![/red]")
        console.print("[yellow]All entries failed. Please run your terminal as Administrator.[/yellow]")
    elif failed:
        console.print("\n[yellow]Setup partially complete[/yellow]")
        console.print(f"[dim]{len(succeeded)} succeeded, {len(failed)} failed[/dim]")
    else:
        console.print("\n[green]Setup complete![/green]")
        console.print("\n[dim]Your microservices can now use the real hostnames in their configuration.[/dim]")
