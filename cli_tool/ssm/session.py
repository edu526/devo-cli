"""SSM session management"""

import json
import subprocess
from typing import Optional


class SSMSession:
    """Manages AWS SSM sessions"""

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

        return subprocess.run(cmd).returncode

    @staticmethod
    def start_session(instance_id: str, region: str = "us-east-1", profile: Optional[str] = None) -> int:
        """Start an interactive session with an instance"""
        cmd = ["aws", "ssm", "start-session", "--target", instance_id, "--region", region]

        if profile:
            cmd.extend(["--profile", profile])

        return subprocess.run(cmd).returncode

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

        return subprocess.run(cmd).returncode
