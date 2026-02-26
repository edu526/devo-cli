"""Manage port forwarding for loopback IP forwarding"""

import platform
import subprocess
from typing import Dict, Optional


class PortForwarder:
    """
    Manages port forwarding from loopback aliases to 127.0.0.1

    AWS SSM Session Manager plugin only binds to 127.0.0.1, so we use
    platform-specific tools to forward from 127.0.0.x:port to 127.0.0.1:port

    - Linux/macOS: socat
    - Windows: netsh portproxy
    """

    def __init__(self):
        self.processes: Dict[str, Optional[subprocess.Popen]] = {}
        self.system = platform.system()

    def start_forward(self, local_address: str, local_port: int, target_port: int) -> Optional[int]:
        """
        Start port forwarding from local_address:local_port to 127.0.0.1:target_port

        Returns: PID of process (Linux/macOS) or None (Windows uses netsh)
        """
        key = f"{local_address}:{local_port}"

        # Stop existing forward if any
        if key in self.processes:
            self.stop_forward(local_address, local_port)

        if self.system == "Windows":
            return self._start_forward_windows(local_address, local_port, target_port)
        else:
            return self._start_forward_unix(local_address, local_port, target_port)

    def _start_forward_unix(self, local_address: str, local_port: int, target_port: int) -> int:
        """Start forwarding using socat (Linux/macOS)"""
        key = f"{local_address}:{local_port}"

        # On macOS, ensure loopback alias is configured before binding
        if self.system == "Darwin" and local_address.startswith("127.0.0.") and local_address != "127.0.0.1":
            self._ensure_loopback_alias_macos(local_address)

        # Check if socat is installed
        if not self._is_command_available("socat"):
            system_name = "macOS" if self.system == "Darwin" else "Linux"
            install_cmd = "brew install socat" if self.system == "Darwin" else "sudo apt-get install socat"

            raise Exception(f"socat is not installed on {system_name}. Install it with:\n" f"  {install_cmd}")

        # Start socat
        cmd = ["socat", f"TCP-LISTEN:{local_port},bind={local_address},reuseaddr,fork", f"TCP:127.0.0.1:{target_port}"]

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Give socat a moment to start and check if it failed immediately
            import time

            time.sleep(0.1)

            if process.poll() is not None:
                # Process died immediately, get error
                _, stderr = process.communicate()
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"socat failed to start: {error_msg}")

            self.processes[key] = process
            return process.pid

        except FileNotFoundError:
            raise Exception("socat command not found. This should not happen as we checked for it earlier.")

    def _start_forward_windows(self, local_address: str, local_port: int, target_port: int) -> None:
        """Start forwarding using netsh portproxy (Windows)"""
        key = f"{local_address}:{local_port}"

        # netsh portproxy requires admin privileges
        cmd = [
            "netsh",
            "interface",
            "portproxy",
            "add",
            "v4tov4",
            f"listenaddress={local_address}",
            f"listenport={local_port}",
            "connectaddress=127.0.0.1",
            f"connectport={target_port}",
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Store a marker (netsh doesn't return a process)
            self.processes[key] = None

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else ""
            stdout = e.stdout if e.stdout else ""
            error_output = stderr + stdout
            error_lower = error_output.lower()

            # Check for permission/elevation errors in multiple languages
            permission_keywords = [
                "access is denied",
                "denied",
                "acceso denegado",
                "requiere elevación",
                "requiere elevacion",
                "requires elevation",
                "ejecutar como administrador",
                "run as administrator",
            ]

            if any(keyword in error_lower for keyword in permission_keywords):
                raise Exception(
                    "Permission denied. Please run your terminal as Administrator:\n"
                    "  1. Right-click on Git Bash, Command Prompt or PowerShell\n"
                    "  2. Select 'Run as administrator'\n"
                    "  3. Run the command again"
                )
            else:
                raise Exception(f"Failed to create port proxy: {error_output.strip() or 'Unknown error'}")

    def stop_forward(self, local_address: str, local_port: int):
        """Stop port forwarding"""
        key = f"{local_address}:{local_port}"

        if key not in self.processes:
            return

        if self.system == "Windows":
            self._stop_forward_windows(local_address, local_port)
        else:
            self._stop_forward_unix(key)

    def _stop_forward_unix(self, key: str):
        """Stop socat process"""
        process = self.processes[key]
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        del self.processes[key]

    def _stop_forward_windows(self, local_address: str, local_port: int):
        """Remove netsh portproxy rule"""
        key = f"{local_address}:{local_port}"

        cmd = ["netsh", "interface", "portproxy", "delete", "v4tov4", f"listenaddress={local_address}", f"listenport={local_port}"]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            pass  # Ignore errors on cleanup

        if key in self.processes:
            del self.processes[key]

    def stop_all(self):
        """Stop all port forwarding"""
        for key in list(self.processes.keys()):
            local_address, local_port = key.split(":")
            self.stop_forward(local_address, int(local_port))

    def _is_command_available(self, command: str) -> bool:
        """Check if a command is available"""
        try:
            subprocess.run(
                ["which", command] if self.system != "Windows" else ["where", command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _ensure_loopback_alias_macos(self, ip: str):
        """Ensure loopback alias is configured on macOS"""
        # Check if alias already exists
        try:
            result = subprocess.run(["ifconfig", "lo0"], capture_output=True, text=True, check=True)
            if ip in result.stdout:
                return  # Already configured
        except subprocess.CalledProcessError:
            pass

        # Add loopback alias
        from rich.console import Console

        console = Console()
        console.print(f"[dim]Configuring loopback alias {ip} on macOS...[/dim]")

        try:
            subprocess.run(["sudo", "ifconfig", "lo0", "alias", ip, "up"], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else ""
            raise Exception(f"Failed to configure loopback alias {ip}: {stderr.strip() or 'Unknown error'}")

    def __del__(self):
        """Cleanup on deletion"""
        self.stop_all()
