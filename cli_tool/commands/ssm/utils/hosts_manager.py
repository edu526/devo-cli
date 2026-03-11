"""Manage /etc/hosts entries for SSM connections"""

import ipaddress
import platform
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

# Valid hostname pattern: labels separated by dots, no path traversal or special chars
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$")


class HostsManager:
    """Manages /etc/hosts entries for SSM port forwarding"""

    MARKER_START = "# DEVO-CLI-SSM-START - Do not edit manually"
    MARKER_END = "# DEVO-CLI-SSM-END"
    UNIX_HOSTS_FILE = "/etc/hosts"
    WINDOWS_HOSTS_FILE = "C:/Windows/System32/drivers/etc/hosts"

    @staticmethod
    def get_hosts_file_path() -> Path:
        """Get the hosts file path for the current OS"""
        system = platform.system()
        if system == "Windows":
            return Path(HostsManager.WINDOWS_HOSTS_FILE)
        else:  # Linux, macOS, Unix
            return Path(HostsManager.UNIX_HOSTS_FILE)

    def __init__(self):
        self.HOSTS_FILE = self.get_hosts_file_path()

    def get_managed_entries(self) -> List[Tuple[str, str]]:
        """Get all entries managed by Devo CLI"""
        if not self.HOSTS_FILE.exists():
            return []

        content = self.HOSTS_FILE.read_text()

        if self.MARKER_START not in content:
            return []

        # Extract managed section
        start_idx = content.find(self.MARKER_START)
        end_idx = content.find(self.MARKER_END)

        if start_idx == -1 or end_idx == -1:
            return []

        managed_section = content[start_idx:end_idx]
        entries = []

        for line in managed_section.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    entries.append((parts[0], parts[1]))

        return entries

    def _update_existing_entry(self, ip: str, hostname: str) -> bool:
        """Check if entry exists and update if IP changed. Returns True if entry already correct."""
        entries = self.get_managed_entries()
        for existing_ip, existing_host in entries:
            if existing_host == hostname:
                if existing_ip == ip:
                    return True  # Entry already exists with correct IP
                # IP changed — remove old entry so caller can re-add
                self.remove_entry(hostname)
                return False
        return False

    @staticmethod
    def _validate_ip(ip: str):
        """Raise ValueError if ip is not a valid IP address."""
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            raise ValueError(f"Invalid IP address: {ip!r}")

    @staticmethod
    def _validate_hostname(hostname: str):
        """Raise ValueError if hostname contains unsafe characters."""
        if not hostname or not _HOSTNAME_RE.match(hostname):
            raise ValueError(f"Invalid or unsafe hostname: {hostname!r}")

    def add_entry(self, ip: str, hostname: str):
        """Add a hostname entry to /etc/hosts"""
        self._validate_ip(ip)
        self._validate_hostname(hostname)
        # On macOS, configure loopback alias if needed
        if platform.system() == "Darwin" and ip.startswith("127.0.0.") and ip != "127.0.0.1":
            self._configure_loopback_alias_macos(ip)

        content = self._read_hosts()

        # Initialize managed section if it doesn't exist
        if self.MARKER_START not in content:
            content += f"\n{self.MARKER_START}\n{self.MARKER_END}\n"

        # Check if entry already exists (returns True if no change needed)
        if self._update_existing_entry(ip, hostname):
            return

        # Re-read after potential remove_entry call
        content = self._read_hosts()
        if self.MARKER_START not in content:
            content += f"\n{self.MARKER_START}\n{self.MARKER_END}\n"

        # Add new entry
        entry = f"{ip} {hostname}"
        new_content = content.replace(self.MARKER_END, f"{entry}\n{self.MARKER_END}")
        self._write_hosts(new_content)

    def _filter_hostname_from_lines(self, lines: List[str], hostname: str) -> tuple:
        """Filter hostname lines from managed section. Returns (filtered_lines, removed_ips)."""
        filtered_lines = []
        removed_ips = []
        in_managed_section = False

        for line in lines:
            if self.MARKER_START in line:
                in_managed_section = True
                filtered_lines.append(line)
            elif self.MARKER_END in line:
                in_managed_section = False
                filtered_lines.append(line)
            elif in_managed_section and hostname in line and not line.strip().startswith("#"):
                parts = line.strip().split()
                if len(parts) >= 2:
                    removed_ips.append(parts[0])
            else:
                filtered_lines.append(line)

        return filtered_lines, removed_ips

    def remove_entry(self, hostname: str):
        """Remove a hostname entry from /etc/hosts"""
        self._validate_hostname(hostname)
        content = self._read_hosts()

        if self.MARKER_START not in content:
            return

        filtered_lines, removed_ips = self._filter_hostname_from_lines(content.split("\n"), hostname)
        self._write_hosts("\n".join(filtered_lines))

        # On macOS, remove loopback aliases that are no longer used
        if platform.system() == "Darwin":
            for ip in removed_ips:
                if ip.startswith("127.0.0.") and ip != "127.0.0.1":
                    self._remove_loopback_alias_macos(ip)

    def clear_all(self):
        """Remove all Devo CLI managed entries"""
        content = self._read_hosts()

        if self.MARKER_START not in content:
            return

        # Get all managed IPs for cleanup
        managed_ips = [ip for ip, _ in self.get_managed_entries()]

        # Remove entire managed section
        start_idx = content.find(self.MARKER_START)
        end_idx = content.find(self.MARKER_END)

        if start_idx != -1 and end_idx != -1:
            # Include the end marker line
            end_idx = content.find("\n", end_idx) + 1
            new_content = content[:start_idx] + content[end_idx:]
            self._write_hosts(new_content)

        # On macOS, remove all loopback aliases
        if platform.system() == "Darwin":
            for ip in managed_ips:
                if ip.startswith("127.0.0.") and ip != "127.0.0.1":
                    self._remove_loopback_alias_macos(ip)

    def _read_hosts(self) -> str:
        """Read /etc/hosts file"""
        if not self.HOSTS_FILE.exists():
            return ""
        return self.HOSTS_FILE.read_text()

    def _write_hosts(self, content: str):
        """Write to hosts file (requires elevated privileges)"""
        system = platform.system()

        if system == "Windows":
            # Windows: Write directly (requires running as Administrator)
            try:
                self.HOSTS_FILE.write_text(content, encoding="utf-8")
            except PermissionError as e:
                raise PermissionError(
                    "Permission denied. Please run your terminal as Administrator:\n"
                    "  1. Right-click on Command Prompt or PowerShell\n"
                    "  2. Select 'Run as administrator'\n"
                    "  3. Run the command again"
                ) from e
        else:
            # Linux/macOS: Use sudo tee with a fixed, validated path (not user-controlled)
            hosts_path = self.get_hosts_file_path()
            if hosts_path != Path(self.UNIX_HOSTS_FILE):
                raise ValueError(f"Unexpected hosts file path: {hosts_path}")
            process = subprocess.Popen(
                ["sudo", "tee", self.UNIX_HOSTS_FILE], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            _, stderr = process.communicate(input=content.encode())

            if process.returncode != 0:
                raise OSError(f"Failed to write hosts file: {stderr.decode()}")

    def get_next_loopback_ip(self) -> str:
        """Get the next available loopback IP address"""
        entries = self.get_managed_entries()
        used_ips = {ip for ip, _ in entries}

        # Start from 127.0.0.2 (127.0.0.1 is standard localhost)
        for i in range(2, 255):
            ip = f"127.0.0.{i}"
            if ip not in used_ips:
                return ip

        raise RuntimeError("No available loopback IPs (127.0.0.2-254 all in use)")

    def _configure_loopback_alias_macos(self, ip: str):
        """Configure loopback alias on macOS using ifconfig"""
        from rich.console import Console

        # Validate IP is a safe loopback address (127.0.0.x where x is 2-254)
        if not re.match(r"^127\.0\.0\.(?:[2-9]|[1-9]\d|1\d{2}|2[0-4]\d|25[0-4])$", ip):
            raise ValueError(f"Invalid loopback IP address: {ip}")

        console = Console()

        # Check if alias already exists
        try:
            result = subprocess.run(["ifconfig", "lo0"], capture_output=True, text=True, check=True)
            if ip in result.stdout:
                return  # Already configured
        except subprocess.CalledProcessError:
            pass

        # Add loopback alias
        console.print(f"[dim]Configuring loopback alias {ip} on macOS...[/dim]")
        try:
            subprocess.run(["sudo", "ifconfig", "lo0", "alias", ip, "up"], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else ""
            raise OSError(f"Failed to configure loopback alias {ip}: {stderr.strip() or 'Unknown error'}") from e

    def _remove_loopback_alias_macos(self, ip: str):
        """Remove loopback alias on macOS using ifconfig"""
        try:
            # Check if alias exists before trying to remove
            result = subprocess.run(["ifconfig", "lo0"], capture_output=True, text=True, check=True)
            if ip not in result.stdout:
                return  # Not configured, nothing to remove

            # Remove loopback alias
            subprocess.run(["sudo", "ifconfig", "lo0", "-alias", ip], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            # Ignore errors on cleanup
            pass
