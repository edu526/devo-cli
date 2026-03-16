"""Instance shell command."""

import time

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMConfigManager, SSMSession

console = Console()

_RECONNECT_DELAY = 3


@click.command()
@click.argument("name")
def connect_instance(name):
    """Connect to a configured instance via interactive shell"""
    config_manager = SSMConfigManager()
    instance_config = config_manager.get_instance(name)

    if not instance_config:
        console.print(f"[red]Instance '{name}' not found in config[/red]")
        console.print("\nAvailable instances:")
        for inst_name in config_manager.list_instances().keys():
            console.print(f"  - {inst_name}")
        return

    if SSMSession._is_token_expired(region=instance_config["region"], profile=instance_config.get("profile")):
        console.print("\n[red]❌ AWS tokens are expired.[/red]")
        console.print("[yellow]Run 'devo aws-login refresh' to renew your tokens.[/yellow]")
        return

    console.print(f"[cyan]Connecting to {name} ({instance_config['instance_id']})...[/cyan]")
    console.print("[yellow]Type 'exit' to close the session[/yellow]\n")

    while True:
        try:
            returncode = SSMSession.start_session(
                instance_id=instance_config["instance_id"],
                region=instance_config["region"],
                profile=instance_config.get("profile"),
            )
        except KeyboardInterrupt:
            console.print("\n[green]Session closed[/green]")
            return

        if returncode == 0:
            # Clean exit — user typed 'exit' inside the shell
            return

        # Session terminated unexpectedly — check token validity before reconnecting
        if SSMSession._is_token_expired(region=instance_config["region"], profile=instance_config.get("profile")):
            console.print("\n[red]❌ AWS tokens are expired.[/red]")
            console.print("[yellow]Run 'devo aws-login refresh' to renew your tokens.[/yellow]")
            return

        # Tokens are still valid — schedule a reconnect
        try:
            console.print(f"\n[yellow]Session disconnected. Reconnecting in {_RECONNECT_DELAY}s... (Ctrl+C to cancel)[/yellow]")
            time.sleep(_RECONNECT_DELAY)
        except KeyboardInterrupt:
            console.print("\n[green]Connection closed[/green]")
            return

        console.print(f"[cyan]Reconnecting to {name} ({instance_config['instance_id']})...[/cyan]\n")
