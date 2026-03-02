"""Hosts setup command."""

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMConfigManager
from cli_tool.commands.ssm.utils import HostsManager

console = Console()


@click.command()
def hosts_setup():
    """Setup /etc/hosts entries for all configured databases"""
    config_manager = SSMConfigManager()
    hosts_manager = HostsManager()
    databases = config_manager.list_databases()

    if not databases:
        console.print("[yellow]No databases configured[/yellow]")
        return

    console.print("[cyan]Setting up /etc/hosts entries...[/cyan]\n")

    success_count = 0
    error_count = 0

    # Track used local_port values to detect conflicts
    used_local_ports = {}
    next_available_port = 15432  # Start from a high port for auto-assignment

    for name, db_config in databases.items():
        # Get or assign loopback IP
        if "local_address" not in db_config or db_config["local_address"] == "127.0.0.1":
            # Assign new loopback IP
            local_address = hosts_manager.get_next_loopback_ip()

            # Update config
            config = config_manager.load()
            config["databases"][name]["local_address"] = local_address
            config_manager.save(config)
        else:
            local_address = db_config["local_address"]

        # Check for local_port conflicts (multiple DBs trying to use same local port)
        local_port = db_config.get("local_port", db_config["port"])

        if local_port in used_local_ports:
            console.print(f"[yellow]⚠[/yellow] {name}: Local port {local_port} already used by {used_local_ports[local_port]}")
            console.print(f"[dim]  Assigning unique local port {next_available_port}...[/dim]")

            # Assign unique local port
            local_port = next_available_port
            next_available_port += 1

            # Update config with new local_port
            config = config_manager.load()
            config["databases"][name]["local_port"] = local_port
            config_manager.save(config)

        used_local_ports[local_port] = name

        # Add to /etc/hosts
        try:
            hosts_manager.add_entry(local_address, db_config["host"])
            console.print(f"[green]✓[/green] {name}: {db_config['host']} -> {local_address}:{db_config['port']} (local: {local_port})")
            success_count += 1
        except Exception as e:
            console.print(f"[red]✗[/red] {name}: {e}")
            error_count += 1

    # Show appropriate completion message
    if error_count > 0 and success_count == 0:
        console.print("\n[red]Setup failed![/red]")
        console.print("[yellow]All entries failed. Please run your terminal as Administrator.[/yellow]")
    elif error_count > 0:
        console.print("\n[yellow]Setup partially complete[/yellow]")
        console.print(f"[dim]{success_count} succeeded, {error_count} failed[/dim]")
    else:
        console.print("\n[green]Setup complete![/green]")
        console.print("\n[dim]Your microservices can now use the real hostnames in their configuration.[/dim]")
