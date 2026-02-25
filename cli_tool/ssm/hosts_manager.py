"""Manage /etc/hosts entries for SSM connections"""

import platform
import subprocess
from pathlib import Path
from typing import List, Tuple


class HostsManager:
    """Manages /etc/hosts entries for SSM port forwarding"""

    MARKER_START = "# DEVO-CLI-SSM-START - Do not edit manually"
    MARKER_END = "# DEVO-CLI-SSM-END"

    @staticmethod
    def get_hosts_file_path() -> Path:
        """Get the hosts file path for the current OS"""
        system = platform.system()
        if system == "Windows":
            return Path("C:/Windows/System32/drivers/etc/hosts")
        else:  # Linux, macOS, Unix
            return Path("/etc/hosts")

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

    def add_entry(self, ip: str, hostname: str):
        """Add a hostname entry to /etc/hosts"""
        content = self._read_hosts()

        # Initialize managed section if it doesn't exist
        if self.MARKER_START not in content:
            content += f"\n{self.MARKER_START}\n{self.MARKER_END}\n"

        # Check if entry already exists
        entries = self.get_managed_entries()
        for existing_ip, existing_host in entries:
            if existing_host == hostname:
                if existing_ip == ip:
                    return  # Entry already exists
                else:
                    # Update IP
                    self.remove_entry(hostname)
                    break

        # Add new entry
        entry = f"{ip} {hostname}"
        new_content = content.replace(self.MARKER_END, f"{entry}\n{self.MARKER_END}")

        self._write_hosts(new_content)

    def remove_entry(self, hostname: str):
        """Remove a hostname entry from /etc/hosts"""
        content = self._read_hosts()

        if self.MARKER_START not in content:
            return

        lines = content.split("\n")
        filtered_lines = []
        in_managed_section = False

        for line in lines:
            if self.MARKER_START in line:
                in_managed_section = True
                filtered_lines.append(line)
                continue

            if self.MARKER_END in line:
                in_managed_section = False
                filtered_lines.append(line)
                continue

            if in_managed_section:
                # Skip lines containing the hostname
                if hostname not in line or line.strip().startswith("#"):
                    filtered_lines.append(line)
            else:
                filtered_lines.append(line)

        self._write_hosts("\n".join(filtered_lines))

    def clear_all(self):
        """Remove all Devo CLI managed entries"""
        content = self._read_hosts()

        if self.MARKER_START not in content:
            return

        # Remove entire managed section
        start_idx = content.find(self.MARKER_START)
        end_idx = content.find(self.MARKER_END)

        if start_idx != -1 and end_idx != -1:
            # Include the end marker line
            end_idx = content.find("\n", end_idx) + 1
            new_content = content[:start_idx] + content[end_idx:]
            self._write_hosts(new_content)

    def _read_hosts(self) -> str:
        """Read /etc/hosts file"""
        if not self.HOSTS_FILE.exists():
            return ""
        return self.HOSTS_FILE.read_text()

    def _write_hosts(self, content: str):
        """Write to hosts file (requires elevated privileges)"""
        system = platform.system()

        try:
            if system == "Windows":
                # Windows: Write directly (requires running as Administrator)
                try:
                    self.HOSTS_FILE.write_text(content, encoding="utf-8")
                except PermissionError:
                    raise Exception(
                        "Permission denied. Please run your terminal as Administrator:\n"
                        "  1. Right-click on Command Prompt or PowerShell\n"
                        "  2. Select 'Run as administrator'\n"
                        "  3. Run the command again"
                    )
            else:
                # Linux/macOS: Use sudo tee
                process = subprocess.Popen(
                    ["sudo", "tee", str(self.HOSTS_FILE)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate(input=content.encode())

                if process.returncode != 0:
                    raise Exception(f"Failed to write hosts file: {stderr.decode()}")

        except Exception as e:
            raise Exception(f"Error writing hosts file: {e}")

    def get_next_loopback_ip(self) -> str:
        """Get the next available loopback IP address"""
        entries = self.get_managed_entries()
        used_ips = {ip for ip, _ in entries}

        # Start from 127.0.0.2 (127.0.0.1 is standard localhost)
        for i in range(2, 255):
            ip = f"127.0.0.{i}"
            if ip not in used_ips:
                return ip

        raise Exception("No available loopback IPs (127.0.0.2-254 all in use)")
