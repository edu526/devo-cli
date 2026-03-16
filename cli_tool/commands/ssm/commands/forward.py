"""Manual port forwarding command for SSM."""

import time

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMSession

console = Console()

_RECONNECT_DELAY = 3


def register_forward_command(ssm_group):
    """Register manual port forwarding command to the SSM group."""

    @ssm_group.command("forward")
    @click.option("--bastion", required=True, help="Bastion instance ID")
    @click.option("--host", required=True, help="Database/service endpoint")
    @click.option("--port", default=5432, type=int, help="Remote port")
    @click.option("--local-port", type=int, help="Local port (default: same as remote)")
    @click.option("--region", default="us-east-1", help="AWS region")
    @click.option("--profile", help="AWS profile (optional, uses default if not specified)")
    def forward_manual(bastion, host, port, local_port, region, profile):
        """Manual port forwarding (without using config)

        Note: This command allows --profile for one-off connections.
        For saved database configurations, profile is stored in config.
        """
        if not local_port:
            local_port = port

        if SSMSession._is_token_expired(region=region, profile=profile):
            console.print("\n[red]❌ AWS tokens are expired.[/red]")
            console.print("[yellow]Run 'devo aws-login refresh' to renew your tokens.[/yellow]")
            return

        console.print(f"[cyan]Forwarding {host}:{port} -> localhost:{local_port}[/cyan]")
        console.print(f"[dim]Via bastion: {bastion}[/dim]")
        if profile:
            console.print(f"[dim]Profile: {profile}[/dim]")
        console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

        while True:
            try:
                exit_code = SSMSession.start_port_forwarding_to_remote(
                    bastion=bastion, host=host, port=port, local_port=local_port, region=region, profile=profile
                )
            except KeyboardInterrupt:
                console.print("\n[green]Connection closed[/green]")
                return

            if exit_code == 0:
                console.print("[green]Connection closed[/green]")
                return

            # Connection dropped unexpectedly — check token validity
            if SSMSession._is_token_expired(region=region, profile=profile):
                console.print("\n[red]❌ AWS tokens are expired.[/red]")
                console.print("[yellow]Run 'devo aws-login refresh' to renew your tokens.[/yellow]")
                return

            # Tokens valid — reconnect after delay
            try:
                console.print(f"\n[yellow]Connection lost. Reconnecting in {_RECONNECT_DELAY}s... (Ctrl+C to cancel)[/yellow]")
                time.sleep(_RECONNECT_DELAY)
            except KeyboardInterrupt:
                console.print("\n[green]Connection closed[/green]")
                return

            console.print(f"[cyan]Reconnecting {host}:{port} -> localhost:{local_port}...[/cyan]\n")


def forward_command():
    """Return forward command registration function."""
    return register_forward_command
