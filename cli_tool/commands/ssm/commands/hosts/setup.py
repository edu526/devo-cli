"""Hosts setup command."""

from typing import Optional

import click
from rich.console import Console

from cli_tool.commands.ssm.commands.database.connect import _find_free_port
from cli_tool.commands.ssm.core import SSMConfigManager
from cli_tool.commands.ssm.utils import HostsManager

console = Console()


def setup_databases(db_names: Optional[list[str]] = None) -> tuple[list[str], list[str]]:
    """Assign loopback IPs, allocate free local ports and add /etc/hosts entries.

    If `db_names` is None, every configured database is processed. Otherwise only
    the named subset is touched. Returns (succeeded, failed) name lists.
    """
    config_manager = SSMConfigManager()
    hosts_manager = HostsManager()
    databases = config_manager.list_databases()

    if db_names is not None:
        databases = {n: c for n, c in databases.items() if n in db_names}

    succeeded: list[str] = []
    failed: list[str] = []
    used_local_ports: dict[int, str] = {}
    next_available_port = 15432  # high port for auto-assignment

    for name, db_config in databases.items():
        # Compute (do not persist yet) the loopback IP
        needs_address = "local_address" not in db_config or db_config["local_address"] == "127.0.0.1"
        local_address = hosts_manager.get_next_loopback_ip() if needs_address else db_config["local_address"]

        # Compute (do not persist yet) the local port
        original_local_port = db_config.get("local_port", db_config["port"])
        preferred_port = original_local_port
        while preferred_port in used_local_ports:
            preferred_port = next_available_port
            next_available_port += 1
        local_port = _find_free_port(preferred_port)
        next_available_port = max(next_available_port, local_port + 1)
        needs_port_save = local_port != original_local_port
        used_local_ports[local_port] = name

        # Side-effecting write FIRST. If it fails the config stays clean.
        try:
            hosts_manager.add_entry(local_address, db_config["host"])
        except Exception as e:
            console.print(f"[red]✗[/red] {name}: {e}")
            failed.append(name)
            continue

        # Persist new values only after the hosts entry was successfully written
        if needs_address or needs_port_save:
            config = config_manager.load()
            if needs_address:
                config["databases"][name]["local_address"] = local_address
            if needs_port_save:
                config["databases"][name]["local_port"] = local_port
            config_manager.save(config)

        if needs_port_save:
            console.print(f"[yellow]⚠[/yellow] {name}: Local port conflict, assigned {local_port}")
        console.print(f"[green]✓[/green] {name}: {db_config['host']} -> {local_address}:{db_config['port']} (local: {local_port})")
        succeeded.append(name)

    return succeeded, failed


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
