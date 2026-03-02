"""Manual port forwarding command for SSM."""

import click
from rich.console import Console

from cli_tool.commands.ssm.core import SSMSession

console = Console()


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

        console.print(f"[cyan]Forwarding {host}:{port} -> localhost:{local_port}[/cyan]")
        console.print(f"[dim]Via bastion: {bastion}[/dim]")
        if profile:
            console.print(f"[dim]Profile: {profile}[/dim]")
        console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

        try:
            SSMSession.start_port_forwarding_to_remote(bastion=bastion, host=host, port=port, local_port=local_port, region=region, profile=profile)
        except KeyboardInterrupt:
            console.print("\n[green]Connection closed[/green]")


def forward_command():
    """Return forward command registration function."""
    return register_forward_command
