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
        result = subprocess.run(cmd, shell=platform.system() == "Windows", capture_output=True, text=True)

        # Check for common AWS permission errors
        if result.returncode != 0:
            error_output = result.stderr.lower()

            if "403" in error_output or "forbidden" in error_output or "unauthorizedrequest" in error_output:
                console.print("\n[red]❌ AWS Permission Error (403 Forbidden)[/red]\n")
                console.print("[yellow]Common causes:[/yellow]")
                console.print("  1. Missing IAM permissions for SSM Session Manager")
                console.print("  2. Instance not registered with SSM (SSM Agent not running)")
                console.print("  3. Wrong AWS profile or credentials")
                console.print("  4. Instance doesn't have required IAM role\n")

                console.print("[cyan]Required IAM permissions:[/cyan]")
                console.print("  - ssm:StartSession")
                console.print("  - ssm:TerminateSession")
                console.print("  - ec2:DescribeInstances\n")

                console.print("[cyan]Troubleshooting steps:[/cyan]")
                profile_flag = f" --profile {profile}" if profile else ""
                console.print(f"  1. Verify your AWS profile: [dim]aws sts get-caller-identity{profile_flag}[/dim]")
                console.print(
                    f"  2. Check instance SSM status: [dim]aws ssm describe-instance-information "
                    f"--instance-id {bastion} --region {region}{profile_flag}[/dim]"
                )
                console.print("  3. Verify IAM permissions in AWS Console")
                console.print("  4. Ensure the bastion instance has SSM Agent installed and running\n")

            elif "invalidinstanceid" in error_output or "does not exist" in error_output:
                console.print("\n[red]❌ Instance Not Found[/red]\n")
                console.print(f"[yellow]The bastion instance '{bastion}' doesn't exist or is not accessible[/yellow]")
                profile_flag = f" --profile {profile}" if profile else ""
                console.print(f"[dim]Check: aws ec2 describe-instances --instance-ids {bastion} " f"--region {region}{profile_flag}[/dim]\n")

            elif "credentials" in error_output or "not configured" in error_output:
                console.print("\n[red]❌ AWS Credentials Error[/red]\n")
                console.print("[yellow]AWS credentials not configured or expired[/yellow]")
                console.print(f"[dim]Run: aws configure{' --profile ' + profile if profile else ''}[/dim]\n")

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
