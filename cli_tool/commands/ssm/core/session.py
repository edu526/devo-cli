"""SSM session management"""

import json
import platform
import subprocess
from typing import Optional

from rich.console import Console

console = Console()

_TOKEN_EXPIRED_PATTERNS = [
    "expiredtokenexception",
    "the security token included in the request is expired",
    "token has expired",
    "credentials have expired",
    "authfailure",
    "sso session associated with this profile has expired",
    "sso session has expired",
    "is otherwise invalid",
    "the security token included in the request is invalid",
    "the security token included in the request is expired",
    "invalidclienttokenid",
    "expiredtoken",
    "ssotokenloaderror",
    "tokenretrievalerror",
    "credentialretrievalerror",
    "unauthorizedssotokenerror",
    "nocredentialserror",
    "error loading sso token",
]


class SSMSession:
    """Manages AWS SSM sessions"""

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
    def _is_token_expired(region: str = "us-east-1", profile: Optional[str] = None) -> bool:
        """Check if AWS tokens are definitively expired.

        Returns True only when the STS call explicitly indicates token expiry.
        Returns False on network errors or any other non-expiry failures so that
        reconnect attempts are not incorrectly suppressed.
        We use the AWS CLI via export-credentials rather than boto3 to ensure
        we share the same credential cache as the AWS CLI.
        """
        if not profile:
            # If no profile is provided, we can't easily check via export-credentials
            # but usually profile is provided for SSO sessions.
            return False

        try:
            from cli_tool.commands.aws_login.core.credentials import check_profile_credentials_available

            available, error_msg = check_profile_credentials_available(profile)
            if available:
                return False

            if error_msg:
                error_text = error_msg.lower()
                return any(pattern in error_text for pattern in _TOKEN_EXPIRED_PATTERNS)
            return False
        except Exception:
            return False

    @staticmethod
    def _build_port_forwarding_cmd(
        bastion: str,
        host: str,
        port: int,
        local_port: int,
        region: str = "us-east-1",
        profile: Optional[str] = None,
    ) -> list:
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
        return cmd

    @staticmethod
    def spawn_port_forwarding_to_remote(
        bastion: str,
        host: str,
        port: int,
        local_port: int,
        region: str = "us-east-1",
        profile: Optional[str] = None,
        local_address: str = "127.0.0.1",
    ) -> subprocess.Popen:
        """Same as start_port_forwarding_to_remote but returns the live Popen handle.

        Caller is responsible for plugin preflight. Use stop_one() / proc.terminate()
        to end the session without touching other active connections.
        """
        cmd = SSMSession._build_port_forwarding_cmd(bastion, host, port, local_port, region, profile)

        # Start the AWS process in a new session (process group) on Unix so it doesn't receive
        # SIGINT directly when the user presses Ctrl+C. The parent process will catch SIGINT
        # and cleanly terminate the child process instead, preventing ugly tracebacks.
        start_new_session = platform.system() != "Windows"

        return subprocess.Popen(
            cmd,
            shell=platform.system() == "Windows",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=start_new_session,
        )

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
        """Start port forwarding to a remote host through a bastion instance.

        Blocks until the session ends. local_address is documented but unused by
        aws ssm start-session; socat/netsh redirection is handled by PortForwarder.
        """
        if not SSMSession._check_session_manager_plugin():
            SSMSession._show_plugin_installation_guide()
            return 1

        proc = SSMSession.spawn_port_forwarding_to_remote(
            bastion=bastion,
            host=host,
            port=port,
            local_port=local_port,
            region=region,
            profile=profile,
            local_address=local_address,
        )
        stdout, stderr = proc.communicate()

        if proc.returncode != 0 and stderr:
            error_lower = stderr.lower()
            if "sessionmanagerplugin is not found" in error_lower or "session-manager-plugin" in error_lower:
                SSMSession._show_plugin_installation_guide()
                return 1
            console.print(stderr)

        return proc.returncode

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
