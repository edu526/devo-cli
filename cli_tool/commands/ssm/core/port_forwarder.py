"""Manage port forwarding for loopback IP forwarding"""

import platform
import signal
import socket
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
        self._register_signal_handlers()

    def _register_signal_handlers(self) -> None:
        """Register SIGTERM/SIGHUP handlers to clean up socat on graceful termination."""
        if self.system == "Windows":
            return

        def _cleanup_handler(signum, frame):
            self.stop_all()
            signal.raise_signal(signum)

        signals = [getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)]
        for sig in [s for s in signals if s is not None]:
            try:
                signal.signal(sig, _cleanup_handler)
            except (OSError, ValueError):
                pass  # Not in main thread or signal not available

    @staticmethod
    def _check_port_free(address: str, port: int) -> None:
        """Raise OSError if address:port is already in use by another process."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((address, port))
            except OSError:
                raise OSError(
                    f"Port {port} is already in use at {address}.\n"
                    "A local service (e.g. a local database) is occupying this port.\n"
                    "Stop that service or use --no-hosts to connect without hostname forwarding."
                )

    def start_forward(self, local_address: str, local_port: int, target_port: int, allow_uac_prompt: bool = True) -> Optional[int]:
        """
        Start port forwarding from local_address:local_port to 127.0.0.1:target_port

        Returns: PID of process (Linux/macOS) or None (Windows uses netsh)
        """
        key = f"{local_address}:{local_port}"

        # Stop existing forward if any
        if key in self.processes:
            self.stop_forward(local_address, local_port)

        if self.system == "Windows":
            self._start_forward_windows(local_address, local_port, target_port, allow_uac_prompt)
            return None
        else:
            return self._start_forward_unix(local_address, local_port, target_port)

    def _kill_orphaned_socat(self, local_address: str, local_port: int) -> None:
        """Kill any orphaned socat process listening on local_address:local_port.

        This handles the case where a previous session was terminated abruptly
        (terminal closed, laptop lid, SIGKILL) leaving socat processes behind
        that hold the port and prevent new connections.
        """
        try:
            pattern = f"socat.*TCP-LISTEN:{local_port},bind={local_address}"
            subprocess.run(["pkill", "-f", pattern], capture_output=True)
            # Give the OS a moment to release the port
            import time

            time.sleep(0.2)
        except Exception:
            pass

    def _start_forward_unix(self, local_address: str, local_port: int, target_port: int) -> int:
        """Start forwarding using socat (Linux/macOS)"""
        key = f"{local_address}:{local_port}"

        # Kill any orphaned socat on this port before starting a new one.
        # This prevents "address already in use" errors when reconnecting after
        # an abrupt termination (closed terminal, laptop sleep, etc.).
        self._kill_orphaned_socat(local_address, local_port)

        # On macOS, ensure loopback alias is configured before binding
        if self.system == "Darwin" and local_address.startswith("127.0.0.") and local_address != "127.0.0.1":
            self._ensure_loopback_alias_macos(local_address)

        # Check if socat is installed
        if not self._is_command_available("socat"):
            system_name = "macOS" if self.system == "Darwin" else "Linux"
            install_cmd = "brew install socat" if self.system == "Darwin" else "sudo apt-get install socat"

            raise FileNotFoundError(f"socat is not installed on {system_name}. Install it with:\n  {install_cmd}")

        # Start socat
        cmd = ["socat", f"TCP-LISTEN:{local_port},bind={local_address},reuseaddr,fork", f"TCP:127.0.0.1:{target_port}"]

        try:
            start_new_session = platform.system() != "Windows"
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=start_new_session)  # noqa: S603

            # Give socat a moment to start and check if it failed immediately
            import time

            time.sleep(0.1)

            if process.poll() is not None:
                # Process died immediately, get error
                _, stderr_bytes = process.communicate()
                error_msg = stderr_bytes.decode() if stderr_bytes else "Unknown error"
                raise RuntimeError(f"socat failed to start: {error_msg}")

            self.processes[key] = process
            return process.pid

        except FileNotFoundError:
            raise FileNotFoundError("socat command not found. This should not happen as we checked for it earlier.")

    def _kill_orphaned_portproxy(self, local_address: str, local_port: int) -> None:
        """Remove any stale netsh portproxy rule on local_address:local_port.

        Windows portproxy rules are persisted in the registry and survive abrupt
        CLI termination (closed terminal, laptop sleep, SIGKILL). Without this,
        a previous session's rule keeps holding the loopback IP and blocks the
        new bind. Mirrors `_kill_orphaned_socat` for the Windows backend.
        """
        cmd = [
            "netsh",
            "interface",
            "portproxy",
            "delete",
            "v4tov4",
            f"listenaddress={local_address}",
            f"listenport={local_port}",
        ]
        try:
            subprocess.run(cmd, capture_output=True)  # noqa: S603 — cleanup is best-effort
        except Exception:
            pass

    def _start_forward_windows(self, local_address: str, local_port: int, target_port: int, allow_uac_prompt: bool = True) -> None:
        """Start forwarding using netsh portproxy (Windows) with UAC elevation."""
        import ctypes
        import ctypes.wintypes
        import subprocess

        key = f"{local_address}:{local_port}"

        # Check if the exact rule already exists to avoid unnecessary UAC prompts (e.g., on auto-reconnect)
        try:
            res = subprocess.run(["netsh", "interface", "portproxy", "show", "v4tov4"], capture_output=True, text=True)
            for line in res.stdout.splitlines():
                parts = line.split()
                if (
                    len(parts) >= 4
                    and parts[0] == local_address
                    and parts[1] == str(local_port)
                    and parts[2] == "127.0.0.1"
                    and parts[3] == str(target_port)
                ):
                    self.processes[key] = None
                    return
        except Exception:
            pass

        # Clear any stale rule and add the new one
        delete_cmd = f"netsh interface portproxy delete v4tov4 listenaddress={local_address} listenport={local_port}"
        add_cmd = (
            f"netsh interface portproxy add v4tov4 listenaddress={local_address} listenport={local_port} "
            f"connectaddress=127.0.0.1 connectport={target_port}"
        )

        if not allow_uac_prompt:
            try:
                subprocess.run(["cmd.exe", "/c", f"{delete_cmd} & {add_cmd}"], capture_output=True, text=True, check=True)
                self.processes[key] = None
                return
            except subprocess.CalledProcessError as e:
                error_output = (e.stderr or "") + (e.stdout or "")
                error_lower = error_output.lower()

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
                    raise PermissionError(
                        "Permission denied. Please run your terminal as Administrator:\n"
                        "  1. Right-click on Git Bash, Command Prompt or PowerShell\n"
                        "  2. Select 'Run as administrator'\n"
                        "  3. Run the command again"
                    )
                else:
                    raise RuntimeError(f"Failed to create port proxy: {error_output.strip() or 'Unknown error'}")

        # If UAC prompt IS allowed, use ShellExecuteExW
        combined_cmd = f'/c "{delete_cmd} & {add_cmd}"'

        SEE_MASK_NOCLOSEPROCESS = 0x00000040

        class SHELLEXECUTEINFOW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.DWORD),
                ("fMask", ctypes.wintypes.ULONG),
                ("hwnd", ctypes.wintypes.HWND),
                ("lpVerb", ctypes.c_wchar_p),
                ("lpFile", ctypes.c_wchar_p),
                ("lpParameters", ctypes.c_wchar_p),
                ("lpDirectory", ctypes.c_wchar_p),
                ("nShow", ctypes.c_int),
                ("hInstApp", ctypes.wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", ctypes.c_wchar_p),
                ("hkeyClass", ctypes.wintypes.HKEY),
                ("dwHotKey", ctypes.wintypes.DWORD),
                ("hIconOrMonitor", ctypes.wintypes.HANDLE),
                ("hProcess", ctypes.wintypes.HANDLE),
            ]

        info = SHELLEXECUTEINFOW()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = SEE_MASK_NOCLOSEPROCESS
        info.lpVerb = "runas"
        info.lpFile = "cmd.exe"
        info.lpParameters = combined_cmd
        info.nShow = 0  # SW_HIDE

        import threading

        if not hasattr(self.__class__, "_uac_lock"):
            self.__class__._uac_lock = threading.Lock()

        with self.__class__._uac_lock:
            if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
                error_code = ctypes.windll.kernel32.GetLastError()
                if error_code in (1223, 5):  # ERROR_CANCELLED or ERROR_ACCESS_DENIED
                    raise PermissionError("Elevation cancelled. Please allow the UAC prompt to configure port forwarding.")
                raise RuntimeError(f"Failed to elevate netsh command. Error code: {error_code}")

            process = info.hProcess
            if process:
                # Wait up to 30 seconds for the elevated process to finish
                wait_res = ctypes.windll.kernel32.WaitForSingleObject(process, 30000)
                if wait_res != 0:
                    ctypes.windll.kernel32.CloseHandle(process)
                    raise RuntimeError("Elevated netsh process timed out.")

                exit_code = ctypes.wintypes.DWORD()
                ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(process)

                if exit_code.value != 0:
                    raise RuntimeError(f"Elevated netsh failed with exit code {exit_code.value}")

        # Store a marker (netsh doesn't return a process)
        self.processes[key] = None

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
        process = self.processes.get(key)
        if process:
            import os
            import signal

            try:
                if process.pid > 1:
                    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                        sig = getattr(signal, "SIGKILL", 9)
                        os.killpg(os.getpgid(process.pid), sig)
                    else:
                        process.kill()
            except ProcessLookupError:
                pass
        if key in self.processes:
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
        # list() is necessary here because stop_forward modifies self.processes during iteration
        for key in list(self.processes.keys()):  # NOSONAR
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
            raise OSError(f"Failed to configure loopback alias {ip}: {stderr.strip() or 'Unknown error'}")

    def __del__(self):
        """Cleanup on deletion"""
        self.stop_all()
