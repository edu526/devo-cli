"""SSM session management"""

import ctypes
import json
import platform
import subprocess
from typing import Optional

from rich.console import Console

console = Console()


class SSMSession:
    """Manages AWS SSM sessions"""

    @staticmethod
    def _is_windows_admin() -> bool:
        """Check if running with administrator privileges on Windows"""
        if platform.system() != "Windows":
            return True
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def _check_session_manager_plugin() -> bool:
        """Check if AWS Session Manager plugin is installed"""
        try:
            subprocess.run(["session-manager-plugin"], shell=platform.system() == "Windows", capture_output=True, text=True, timeout=2)
            # Plugin is installed if command exists (even if it returns error about usage)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _show_plugin_installation_guide() -> None:
        """Show installation guide for Session Manager plugin"""
        console.print("\n[red]❌ AWS Session Manager Plugin Not Installed[/red]\n")
        console.print("[yellow]The Session Manager plugin is required for SSM connections[/yellow]")
        console.print("[dim]This is different from the AWS CLI and must be installed separately[/dim]\n")

        if platform.system() == "Windows":
            console.print("[cyan]Installation for Windows:[/cyan]")
            console.print("  https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-windows.html\n")
        elif platform.system() == "Darwin":
            console.print("[cyan]Installation for macOS:[/cyan]")
            console.print("  https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-macos-overview.html\n")
        else:
            console.print("[cyan]Installation for Linux:[/cyan]")
            console.print("  Debian/Ubuntu: https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-debian-and-ubuntu.html")
            console.print("  RedHat/CentOS: https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-linux.html\n")

        console.print("[cyan]Verify installation:[/cyan]")
        console.print("  session-manager-plugin\n")

    @staticmethod
    def start_port_forwarding_to_remote(
        bastion: str,
        host: str,
        port: int,
        local_port: int,
        region: str = "us-east-1",
        profile: Optional[str] = None,
        local_address: str = "127.0.0.1",
    ) -> int:
        """
        Start port forwarding to a remote host through a bastion instance.
        Used for connecting to RDS, ElastiCache, etc.

        Args:
          local_address: Local IP to bind to (e.g., '127.0.0.2' for loopback aliases)
        """
        # Note: AWS SSM Session Manager plugin doesn't support binding to specific IPs
        # We need to use socat or similar tool to redirect from loopback alias to 127.0.0.1
        # For now, we'll document this limitation and provide a workaround

        # Check if Session Manager plugin is installed
        if not SSMSession._check_session_manager_plugin():
            SSMSession._show_plugin_installation_guide()
            return 1

        parameters = {"host": [host], "portNumber": [str(port)], "localPortNumber": [str(local_port)]}

        cmd = [
            "aws",
            "ssm",
            "start-session",
            "--target",
            bastion,
            "--document-name",
            "AWS-StartPortForwardingSessionToRemoteHost",
            "--region",
            region,
            "--parameters",
            json.dumps(parameters),
        ]

        if profile:
            cmd.extend(["--profile", profile])

        # On Windows, use shell=True to find aws in PATH
        # Don't capture output so user can see real-time feedback and errors
        result = subprocess.run(cmd, shell=platform.system() == "Windows")

        return result.returncode

    @staticmethod
    def start_session(instance_id: str, region: str = "us-east-1", profile: Optional[str] = None) -> int:
        """Start an interactive session with an instance"""
        cmd = ["aws", "ssm", "start-session", "--target", instance_id, "--region", region]

        if profile:
            cmd.extend(["--profile", profile])

        # On Windows, use shell=True to find aws in PATH
        return subprocess.run(cmd, shell=platform.system() == "Windows").returncode

    @staticmethod
    def start_port_forwarding(instance_id: str, remote_port: int, local_port: int, region: str = "us-east-1", profile: Optional[str] = None) -> int:
        """Start port forwarding to an instance"""
        cmd = [
            "aws",
            "ssm",
            "start-session",
            "--target",
            instance_id,
            "--document-name",
            "AWS-StartPortForwardingSession",
            "--region",
            region,
            "--parameters",
            f"portNumber={remote_port},localPortNumber={local_port}",
        ]

        if profile:
            cmd.extend(["--profile", profile])

        # On Windows, use shell=True to find aws in PATH
        return subprocess.run(cmd, shell=platform.system() == "Windows").returncode
