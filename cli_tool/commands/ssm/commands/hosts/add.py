"""Hosts add command."""

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMConfigManager
from cli_tool.commands.ssm.utils import HostsManager

console = Console()


@click.command()
@click.argument("name")
def hosts_add_single(name):
    """Add a single database hostname to /etc/hosts"""
    config_manager = SSMConfigManager()
    hosts_manager = HostsManager()

    db_config = config_manager.get_database(name)

    if not db_config:
        console.print(f"[red]Database '{name}' not found[/red]")
        return

    # Get or assign loopback IP
    if "local_address" not in db_config or db_config["local_address"] == "127.0.0.1":
        local_address = hosts_manager.get_next_loopback_ip()

        # Update config
        config = config_manager.load()
        config["databases"][name]["local_address"] = local_address
        config_manager.save(config)
    else:
        local_address = db_config["local_address"]

    try:
        hosts_manager.add_entry(local_address, db_config["host"])
        console.print(f"[green]Added {db_config['host']} -> {local_address}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
