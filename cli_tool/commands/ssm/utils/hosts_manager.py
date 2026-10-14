"""Manage /etc/hosts entries for SSM connections"""

import ipaddress
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

# Valid hostname pattern: labels separated by dots, no path traversal or special chars
_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$")


def _is_windows_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class HostsFileLocked(PermissionError):
    """Writing the hosts file was denied even with administrator rights.

    The file's own permissions let administrators write it, so something else
    stops it: usually an antivirus protecting it, sometimes the read-only flag.
    The message says which, and what the user can do.
    """

    # The `devo ssm hosts` commands exit with it, so the desktop (which runs
    # them elevated and only sees the exit code) can tell this case apart.
    exit_code = 3


def describe_hosts_lock() -> str:
    """Why the hosts file can't be written even as administrator, for the user."""
    import stat

    from cli_tool.commands.ssm.utils.security_software import active_antivirus

    path = HostsManager.get_hosts_file_path()
    try:
        read_only = bool(os.stat(path).st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
    except (OSError, AttributeError):  # st_file_attributes only exists on Windows
        read_only = False
    if read_only:
        return f'Your hosts file is marked read-only. Uncheck "Read-only" in its properties ({path}) and try again.'

    antivirus = active_antivirus()
    if antivirus:
        return (
            f"{' / '.join(antivirus)} is blocking changes to your hosts file, even with administrator rights. "
            "Pause its protection for a moment (or allow changes to the hosts file in its settings) and try again."
        )
    return (
        "Something is blocking changes to your hosts file, even with administrator rights, usually an antivirus. "
        "Pause it for a moment and try again."
    )


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
        # Kept for backward compatibility in get_managed_entries / _filter_hostname_from_lines,
        # but _read_hosts and _write_hosts always resolve the path from the class constants.
        self.HOSTS_FILE = self.get_hosts_file_path()

    def get_managed_entries(self) -> List[Tuple[str, str]]:
        """Get all entries managed by Devo CLI"""
        if not self.HOSTS_FILE.exists():
            return []

        return self._entries_in(self.HOSTS_FILE.read_text())

    @classmethod
    def _entries_in(cls, content: str) -> List[Tuple[str, str]]:
        """(ip, hostname) entries of the managed section of `content`."""
        if cls.MARKER_START not in content:
            return []

        # Extract managed section
        start_idx = content.find(cls.MARKER_START)
        end_idx = content.find(cls.MARKER_END)

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
            elif in_managed_section and hostname in line.split()[1:] and not line.strip().startswith("#"):
                # Whole-name match: "db.x.rds…" must not take "reader-db.x.rds…" with it.
                removed_ips.append(line.split()[0])
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
        if not removed_ips:
            return  # nothing to do: don't write (that needs elevation)
        # Several hostnames can share a loopback IP: keep the aliases still in use.
        still_used = {ip for ip, _host in self._entries_in("\n".join(filtered_lines))}
        unused_ips = [ip for ip in dict.fromkeys(removed_ips) if ip not in still_used]
        self._check_can_remove_aliases(unused_ips)
        self._write_hosts("\n".join(filtered_lines))

        # On macOS, remove loopback aliases that are no longer used
        if platform.system() == "Darwin":
            for ip in unused_ips:
                if ip.startswith("127.0.0.") and ip != "127.0.0.1":
                    self._remove_loopback_alias_macos(ip)

    def clear_all(self):
        """Remove all Devo CLI managed entries"""
        content = self._read_hosts()

        if self.MARKER_START not in content:
            return

        # Get all managed IPs for cleanup
        managed_ips = [ip for ip, _ in self.get_managed_entries()]
        self._check_can_remove_aliases(managed_ips)

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

    @staticmethod
    def _check_can_remove_aliases(ips: List[str]):
        """Raise PermissionError up front when removing these IPs' macOS
        loopback aliases needs elevation (always, from the sidecar).

        Otherwise the hosts file would be written and the alias removal fail
        afterwards; the elevated retry then finds the entries gone and never
        removes the aliases.
        """
        if platform.system() != "Darwin" or os.environ.get("DEVO_SIDECAR") != "1":
            return
        if any(ip.startswith("127.0.0.") and ip != "127.0.0.1" for ip in ips):
            raise PermissionError("Permission denied. Needs elevation to remove loopback alias.")

    def _read_hosts(self) -> str:
        """Read /etc/hosts file using the validated, constant path."""
        hosts_path = self.get_hosts_file_path()
        if not hosts_path.exists():
            return ""
        return hosts_path.read_text()

    def _write_hosts(self, content: str):
        """Write to hosts file (requires elevated privileges).

        Always resolves the path from the static constant to prevent
        any path-manipulation attack via the mutable instance attribute.
        """
        system = platform.system()
        is_sidecar = os.environ.get("DEVO_SIDECAR") == "1"

        if system == "Windows":
            hosts_path = Path(HostsManager.WINDOWS_HOSTS_FILE)
            try:
                hosts_path.write_text(content, encoding="utf-8")
            except PermissionError as e:
                if _is_windows_admin():
                    raise HostsFileLocked(describe_hosts_lock()) from e
                raise PermissionError(
                    "Permission denied. Please run your terminal as Administrator:\n"
                    "  1. Right-click on Command Prompt or PowerShell\n"
                    "  2. Select 'Run as administrator'\n"
                    "  3. Run the command again"
                ) from e
        elif is_sidecar:
            hosts_path = self.get_hosts_file_path()
            try:
                hosts_path.write_text(content, encoding="utf-8")
            except PermissionError as e:
                raise PermissionError("Permission denied. Needs elevation.") from e
        else:
            # Use the class-level constant directly — never a variable derived
            # from user input — so the subprocess call is safe from injection.
            process = subprocess.Popen(
                ["sudo", "tee", HostsManager.UNIX_HOSTS_FILE],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _, stderr = process.communicate(input=content.encode())

            if process.returncode != 0:
                raise OSError(f"Failed to write hosts file: {stderr.decode()}")

    def get_next_loopback_ip(self, taken: Iterable[str] = ()) -> str:
        """Get the next available loopback IP address.

        `taken`: IPs already assigned to databases in the config. Those whose
        hostname forwarding is paused have no entry in the hosts file, but
        their IP comes back with them: it isn't free.
        """
        entries = self.get_managed_entries()
        used_ips = {ip for ip, _ in entries} | set(taken)

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
            is_sidecar = os.environ.get("DEVO_SIDECAR") == "1"
            if is_sidecar:
                raise PermissionError("Permission denied. Needs elevation to configure loopback alias.")
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
            is_sidecar = os.environ.get("DEVO_SIDECAR") == "1"
            if is_sidecar:
                raise PermissionError("Permission denied. Needs elevation to remove loopback alias.")
            subprocess.run(["sudo", "ifconfig", "lo0", "-alias", ip], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            # Ignore errors on cleanup
            pass
