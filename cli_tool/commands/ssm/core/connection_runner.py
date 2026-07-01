"""Core connection runner — business logic for SSM database tunnels.

Moved from commands/ssm/commands/database/connect.py so both the CLI and the
sidecar REST API can share the same implementation without duplicating logic.
"""

import logging
import socket
import subprocess
import threading
import time
from typing import Callable, Literal, Optional

from rich.console import Console
from rich.table import Table

from cli_tool.commands.ssm.core import PortForwarder, SSMSession
from cli_tool.commands.ssm.core.states import (
    CONNECTED,
    ERROR,
    EXPIRED_CREDENTIALS,
    PROBE_TIMEOUT_SECONDS,
    RECONNECTING,
    STARTING,
    STOPPED,
    TRANSIENT_STATES,
)

logger = logging.getLogger(__name__)
console = Console()

_RECONNECT_DELAY = 3
_TOKENS_EXPIRED_MSG = "\n[red]❌ AWS tokens are expired.[/red]"
_TOKENS_REFRESH_MSG = "[yellow]Run 'devo aws-login refresh' to renew your tokens.[/yellow]"


# ---------------------------------------------------------------------------
# ConnectionRecord + ForwarderRegistry
# ---------------------------------------------------------------------------


class ConnectionRecord:
    """Live state snapshot for one active database connection."""

    def __init__(self, name: str, local_port: Optional[int] = None) -> None:
        self.name = name
        self.state: Literal[STARTING, CONNECTED, RECONNECTING, EXPIRED_CREDENTIALS, ERROR, STOPPED] = STARTING
        self.local_port: Optional[int] = local_port
        self.pf: Optional[PortForwarder] = None
        self.ssm_proc: Optional[subprocess.Popen] = None
        self.stop_event = threading.Event()
        self.error: Optional[str] = None
        # Real-time metrics
        self.started_at: Optional[float] = None  # time.monotonic() at first start
        self.attempts: int = 0  # number of SSM connect attempts so far
        self.last_error_at: Optional[float] = None  # wall-clock epoch of last failure
        self.probe_thread: Optional[threading.Thread] = None


class ForwarderRegistry:
    """Thread-safe registry for active connections and PortForwarder cleanup.

    Supports two usage modes:
    - CLI path: add()/remove()/stop_all() + global stop_event (Ctrl+C).
    - Sidecar path: register()/stop_one()/emit() + per-record stop_event.
    Both modes are fully composable.
    """

    def __init__(self) -> None:
        self._forwarders: list[PortForwarder] = []
        self._records: dict[str, ConnectionRecord] = {}
        self._observers: list[Callable[[str, dict], None]] = []
        self._lock = threading.Lock()
        self.stop_event = threading.Event()

    # --- CLI path: PortForwarder list ---

    def add(self, pf: PortForwarder) -> None:
        with self._lock:
            self._forwarders.append(pf)

    def remove(self, pf: PortForwarder) -> None:
        with self._lock:
            try:
                self._forwarders.remove(pf)
            except ValueError:
                pass

    def stop_all(self) -> None:
        with self._lock:
            forwarders = list(self._forwarders)
            record_names = list(self._records.keys())

        for pf in forwarders:
            pf.stop_all()
        for name in record_names:
            self.stop_one(name)

    # --- Sidecar path: per-connection records ---

    def register(self, name: str, record: ConnectionRecord) -> None:
        with self._lock:
            self._records[name] = record

    def get(self, name: str) -> Optional[ConnectionRecord]:
        with self._lock:
            return self._records.get(name)

    def list_records(self) -> dict[str, ConnectionRecord]:
        with self._lock:
            return dict(self._records)

    def remove_record(self, name: str) -> None:
        with self._lock:
            self._records.pop(name, None)

    def stop_one(self, name: str) -> None:
        """Stop a single connection without touching others."""
        with self._lock:
            record = self._records.get(name)
        if record is None:
            return
        record.stop_event.set()
        proc = record.ssm_proc
        pf = record.pf
        if proc is not None:
            import sys

            try:
                if sys.platform == "win32":
                    import psutil

                    try:
                        parent = psutil.Process(proc.pid)
                        for child in parent.children(recursive=True):
                            try:
                                child.terminate()
                            except psutil.NoSuchProcess:
                                pass
                        parent.terminate()
                    except psutil.NoSuchProcess:
                        pass
                else:
                    import os
                    import signal

                    try:
                        if proc.pid > 1:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except Exception:
                try:
                    import os
                    import signal

                    if sys.platform != "win32":
                        if proc.pid > 1:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.terminate()
                except Exception:
                    pass
        if pf is not None:
            pf.stop_all()

    # --- Sidecar path: observer fan-out ---

    def add_observer(self, fn: Callable[[str, dict], None]) -> None:
        with self._lock:
            self._observers.append(fn)

    def emit(self, event: str, payload: dict) -> None:
        with self._lock:
            observers = list(self._observers)
        for fn in observers:
            try:
                fn(event, payload)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------


def _find_free_port(preferred_port: int) -> int:
    """Return preferred_port if free, otherwise the next available port."""
    port = preferred_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free ports available")


def _is_port_bindable(address: str, port: int) -> bool:
    """Return True if address:port can be bound (no existing listener)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((address, port))
            return True
        except OSError:
            import platform
            import subprocess

            if platform.system() == "Windows" and address != "127.0.0.1":
                # Check if the port is occupied by our own stale port proxy rule.
                # If so, we can safely "bind" because our elevated start command will overwrite it.
                try:
                    res = subprocess.run(["netsh", "interface", "portproxy", "show", "v4tov4"], capture_output=True, text=True)
                    for line in res.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 2 and parts[0] == address and parts[1] == str(port):
                            return True
                except Exception:
                    pass
            return False


def _is_wildcard_bind_blocking(port: int) -> bool:
    """Return True if port is held by a wildcard listener (0.0.0.0 or ::).

    Probes unused loopback IPs. If none can be bound, something is listening on
    a wildcard address — typically a local Postgres/MySQL with listen_addresses='*'.
    """
    for probe in ("127.0.0.91", "127.0.0.173"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((probe, port))
                return False
            except OSError:
                continue
    return True


# ---------------------------------------------------------------------------
# Token / reconnect helpers
# ---------------------------------------------------------------------------


def _validate_tokens(databases: dict) -> bool:
    """Check AWS tokens for all unique (profile, region) combos. Returns False if any expired."""
    checked: set = set()
    for db_config in databases.values():
        profile = db_config.get("profile")
        region = db_config.get("region", "us-east-1")
        key = (profile, region)
        if key not in checked:
            checked.add(key)
            if SSMSession._is_token_expired(region=region, profile=profile):
                console.print(_TOKENS_EXPIRED_MSG)
                console.print(_TOKENS_REFRESH_MSG)
                return False
    return True


def _wait_before_reconnect(name: str, stop_event: Optional[threading.Event] = None) -> bool:
    """Sleep before reconnecting. Returns False if Ctrl+C or shutdown requested."""
    try:
        console.print(f"\n[yellow]Connection lost. Reconnecting in {_RECONNECT_DELAY}s... (Ctrl+C to cancel)[/yellow]")
        if stop_event is not None:
            if stop_event.wait(_RECONNECT_DELAY):
                return False
        else:
            time.sleep(_RECONNECT_DELAY)
    except KeyboardInterrupt:
        console.print("\n[green]Connection closed[/green]")
        return False
    console.print(f"[cyan]Reconnecting to {name}...[/cyan]\n")
    return True


# ---------------------------------------------------------------------------
# Core connection loop
# ---------------------------------------------------------------------------


def _run_attempt(
    db_config: dict,
    actual_local_port: int,
    use_hostname_forwarding: bool,
    registry: Optional[ForwarderRegistry] = None,
    record: Optional[ConnectionRecord] = None,
) -> int:
    """Run a single SSM connection attempt. Returns the SSM exit code.

    When record is provided (sidecar path), uses Popen so stop_one() can
    terminate the process independently. CLI path uses the blocking variant
    so Ctrl+C propagates normally via SIGINT to the process group.
    """
    local_address = db_config.get("local_address", "127.0.0.1")
    pf = None
    if use_hostname_forwarding:
        pf = PortForwarder()
        if registry is not None:
            registry.add(pf)
        logger.info("[TIMING][%s] Starting portproxy (UAC) setup...", db_config.get("host", "?"))
        _t0 = time.monotonic()
        pf.start_forward(local_address, db_config["port"], actual_local_port, allow_uac_prompt=(record is not None))
        logger.info("[TIMING][%s] portproxy done in %.1fs", db_config.get("host", "?"), time.monotonic() - _t0)
    if record is not None:
        record.pf = pf

    try:
        if record is not None:
            logger.info("[TIMING][%s] Spawning SSM process...", db_config.get("host", "?"))
            _t1 = time.monotonic()
            proc = SSMSession.spawn_port_forwarding_to_remote(
                bastion=db_config["bastion"],
                host=db_config["host"],
                port=db_config["port"],
                local_port=actual_local_port,
                region=db_config["region"],
                profile=db_config.get("profile"),
            )
            logger.info("[TIMING][%s] SSM process spawned in %.1fs (pid=%s)", db_config.get("host", "?"), time.monotonic() - _t1, proc.pid)
            record.ssm_proc = proc
            stdout, stderr = proc.communicate()
            rc = proc.returncode
            logger.info("SSM process for %s exited with code %s", db_config["host"], rc)
            if rc != 0 and stderr:
                logger.error(f"SSM Error: {stderr.strip()}")
                error_lower = stderr.lower()
                if "sessionmanagerplugin is not found" in error_lower or "session-manager-plugin" in error_lower:
                    SSMSession._show_plugin_installation_guide()
                else:
                    from rich.panel import Panel

                    console.print(
                        Panel(
                            stderr.strip(),
                            title=f"[bold red]AWS Error — {db_config['host']}[/bold red]",
                            border_style="red",
                            padding=(0, 1),
                        )
                    )
                    if "accessdenied" in error_lower or "could not be found" in error_lower:
                        record.error_message = stderr.strip()
            record.ssm_proc = None
            return rc
        else:
            proc = SSMSession.spawn_port_forwarding_to_remote(
                bastion=db_config["bastion"],
                host=db_config["host"],
                port=db_config["port"],
                local_port=actual_local_port,
                region=db_config["region"],
                profile=db_config.get("profile"),
                capture_output=False,
            )
            while proc.poll() is None:
                if registry is not None and registry.stop_event.is_set():
                    import os
                    import signal
                    import sys

                    try:
                        if sys.platform != "win32":
                            if proc.pid > 1:
                                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        else:
                            import psutil

                            try:
                                parent = psutil.Process(proc.pid)
                                for child in parent.children(recursive=True):
                                    try:
                                        child.terminate()
                                    except psutil.NoSuchProcess:
                                        pass
                                parent.terminate()
                            except psutil.NoSuchProcess:
                                pass
                    except Exception:
                        pass
                    break
                import time as _t

                _t.sleep(0.2)
            rc = proc.returncode or 0
            return rc
    finally:
        if record is not None:
            record.pf = None
        if pf is not None:
            pf.stop_all()
            if registry is not None:
                registry.remove(pf)


def _run_connection_loop(
    name: str,
    db_config: dict,
    actual_local_port: int,
    use_hostname_forwarding: bool,
    registry: Optional[ForwarderRegistry] = None,
    record: Optional[ConnectionRecord] = None,
) -> None:
    """Core connection loop: optional socat + SSM + auto-reconnect.

    CLI path: record=None, uses global registry.stop_event for Ctrl+C shutdown.
    Sidecar path: record provided, also checks record.stop_event for per-connection stop.
    """
    global_stop = registry.stop_event if registry is not None else None
    per_stop = record.stop_event if record is not None else None

    def _should_stop() -> bool:
        return (global_stop is not None and global_stop.is_set()) or (per_stop is not None and per_stop.is_set())

    def _emit_state(state: str, **kwargs) -> None:
        if record is not None:
            record.state = state
            if "error" in kwargs:
                record.error = kwargs["error"]
                import time as _t

                record.last_error_at = _t.time()
        if registry is not None:
            payload: dict = {"name": name, "state": state, "local_port": actual_local_port}
            payload.update(kwargs)
            registry.emit("connection.state_changed", payload)

    def _emit_metrics() -> None:
        """Push a connection.metrics event with the live counters.

        Called periodically by the metrics thread. Best-effort: the
        registry.emit path swallows observer errors so a slow consumer
        never affects the connection loop.
        """
        if record is None or registry is None:
            return
        if record.started_at is None:
            return
        import time as _t

        uptime = max(0.0, _t.monotonic() - record.started_at)
        registry.emit(
            "connection.metrics",
            {
                "name": name,
                "uptime_seconds": uptime,
                "attempts": record.attempts,
                "last_error_at": record.last_error_at,
                "state": record.state,
            },
        )

    def _probe_then_emit_connected(port: int, timeout: float = PROBE_TIMEOUT_SECONDS) -> None:
        """Probe localhost:port in background; emit 'connected' when ready."""
        deadline = time.monotonic() + timeout
        attempt = 0
        _probe_start = time.monotonic()
        while time.monotonic() < deadline:
            if _should_stop():
                return
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    elapsed = time.monotonic() - _probe_start
                    logger.info("[TIMING][%s] Port %s ready after %.1fs (%d probe attempt(s))", name, port, elapsed, attempt + 1)
                    if (record is None or record.state in TRANSIENT_STATES) and not _should_stop():
                        _emit_state(CONNECTED)
                    return
            except OSError:
                attempt += 1
                time.sleep(0.5)
        # Timed out
        logger.warning("[TIMING][%s] Probe timed out after %.1fs waiting for port %s", name, PROBE_TIMEOUT_SECONDS, port)

    _emit_state(STARTING)
    if record is not None and record.started_at is None:
        import time as _t

        record.started_at = _t.monotonic()

    # Background metrics emitter: every 5 s, push a connection.metrics
    # event. The thread is a daemon and exits when the connection loop
    # terminates (because _should_stop unblocks the wait).
    if record is not None:

        def _metrics_loop() -> None:
            while not _should_stop():
                _emit_metrics()
                if per_stop is not None:
                    if per_stop.wait(5.0):
                        return
                elif global_stop is not None:
                    if global_stop.wait(5.0):
                        return
                else:
                    time.sleep(5.0)

        threading.Thread(target=_metrics_loop, daemon=True).start()

    def _join_probe() -> None:
        if record is not None and record.probe_thread is not None:
            record.probe_thread.join(timeout=0.5)
            record.probe_thread = None

    is_reconnect = False
    reconnect_attempts = 0
    MAX_RECONNECT_ATTEMPTS = 5
    while True:
        if _should_stop():
            _emit_state(STOPPED)
            _join_probe()
            return
        if is_reconnect:
            console.print(f"[green]✓ Reconnected to {name}[/green]\n")
        if record is not None:
            record.probe_thread = threading.Thread(target=_probe_then_emit_connected, args=(actual_local_port,), daemon=True)
            record.probe_thread.start()
        else:
            threading.Thread(target=_probe_then_emit_connected, args=(actual_local_port,), daemon=True).start()
        if record is not None:
            record.attempts += 1
        if SSMSession._is_token_expired(region=db_config["region"], profile=db_config.get("profile")):
            console.print(_TOKENS_EXPIRED_MSG)
            console.print(_TOKENS_REFRESH_MSG)
            _emit_state(EXPIRED_CREDENTIALS)
            _join_probe()
            return

        try:
            import time as _t

            _attempt_start = _t.monotonic()
            _run_attempt(db_config, actual_local_port, use_hostname_forwarding, registry, record)

            if record is not None and getattr(record, "error_message", None):
                console.print(f"[red]✗ {name}: {record.error_message}[/red]")
                _emit_state(ERROR, error=record.error_message)
                _join_probe()
                return

            if _t.monotonic() - _attempt_start > 10:
                reconnect_attempts = 0
            else:
                reconnect_attempts += 1

            if reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                msg = f"Failed to connect after {MAX_RECONNECT_ATTEMPTS} attempts. Aborting."
                console.print(f"[red]✗ {name}: {msg}[/red]")
                _emit_state(ERROR, error=msg)
                _join_probe()
                return

        except KeyboardInterrupt:
            console.print("\n[green]Connection closed[/green]")
            _emit_state(STOPPED)
            _join_probe()
            return
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            _emit_state(ERROR, error=str(e))
            _join_probe()
            return

        if _should_stop():
            _emit_state(STOPPED)
            _join_probe()
            return

        if SSMSession._is_token_expired(region=db_config["region"], profile=db_config.get("profile")):
            console.print(_TOKENS_EXPIRED_MSG)
            console.print(_TOKENS_REFRESH_MSG)
            _emit_state(EXPIRED_CREDENTIALS)
            _join_probe()
            return

        _emit_state(RECONNECTING)
        if not _wait_before_reconnect(name, per_stop or global_stop):
            _emit_state(STOPPED)
            _join_probe()
            return

        is_reconnect = True


# ---------------------------------------------------------------------------
# Table / thread builders
# ---------------------------------------------------------------------------


def _process_db_for_table(
    name: str,
    db_config: dict,
    no_hosts: bool,
    managed_hosts: set,
    get_unique_local_port: Callable[[int], int],
) -> tuple[tuple, Optional[int], bool]:
    """Build a table row for a DB entry.

    Returns (row_tuple, actual_local_port, use_hostname_forwarding).
    actual_local_port is None if the DB should not be connected.
    """
    local_address = db_config.get("local_address", "127.0.0.1")
    configured_for_forwarding = local_address != "127.0.0.1"
    use_hostname_forwarding = configured_for_forwarding and not no_hosts
    profile = db_config.get("profile", "default")
    remote = f"{db_config['host']}:{db_config['port']}"

    if not configured_for_forwarding and not no_hosts:
        connect_to = f"{local_address}:{db_config['port']}"
        return (name, connect_to, "-", remote, profile, "[yellow]⚠ No hostname forwarding[/yellow]"), None, False

    if use_hostname_forwarding and db_config["host"] not in managed_hosts:
        connect_to = f"{local_address}:{db_config['port']}"
        return (name, connect_to, "-", remote, profile, "[yellow]⚠ Not in /etc/hosts[/yellow]"), None, True

    if use_hostname_forwarding and not _is_port_bindable(local_address, db_config["port"]):
        connect_to = f"{local_address}:{db_config['port']}"
        if _is_wildcard_bind_blocking(db_config["port"]):
            console.print(
                f"[red]✗ {name}: Port {db_config['port']} is held by a service listening on a wildcard address (0.0.0.0/::), "
                f"which blocks every loopback IP (127.0.0.X). "
                f"Reconfigure it to bind only to 127.0.0.1 (e.g. Postgres: listen_addresses='localhost') "
                f"or run with --no-hosts.[/red]"
            )
            status = "[red]✗ Port blocked by wildcard bind[/red]"
        else:
            console.print(
                f"[red]✗ {name}: Port {db_config['port']} on {local_address} is occupied by a local service. Stop it or use --no-hosts.[/red]"
            )
            status = "[red]✗ Port occupied by local service[/red]"
        return (name, connect_to, "-", remote, profile, status), None, True

    fallback_port = db_config["port"] if use_hostname_forwarding else 15432
    preferred_local_port = db_config.get("local_port", fallback_port)
    actual_local_port = get_unique_local_port(preferred_local_port)

    if use_hostname_forwarding:
        import platform

        if platform.system() == "Windows":
            import ctypes
            import os
            import subprocess

            if ctypes.windll.shell32.IsUserAnAdmin() == 0 and "PYTEST_CURRENT_TEST" not in os.environ:
                rule_exists = False
                try:
                    res = subprocess.run(["netsh", "interface", "portproxy", "show", "v4tov4"], capture_output=True, text=True)
                    for line in res.stdout.splitlines():
                        parts = line.split()
                        if (
                            len(parts) >= 4
                            and parts[0] == local_address
                            and parts[1] == str(db_config["port"])
                            and parts[2] == "127.0.0.1"
                            and parts[3] == str(actual_local_port)
                        ):
                            rule_exists = True
                            break
                except Exception:
                    pass

                if not rule_exists:
                    console.print(f"[red]✗ {name}: Permission denied. Please run your terminal as Administrator to configure port forwarding.[/red]")
                    status = "[red]✗ Requires Administrator[/red]"
                    return (name, f"{local_address}:{db_config['port']}", "-", remote, profile, status), None, True

    if actual_local_port != preferred_local_port:
        console.print(f"[yellow]⚠ {name}: Port {preferred_local_port} in use, using {actual_local_port} instead[/yellow]")
    status = f"[yellow]✓ Port {actual_local_port}[/yellow]" if actual_local_port != preferred_local_port else "[green]✓ Connected[/green]"

    connect_to = f"{local_address}:{db_config['port']}" if use_hostname_forwarding else f"127.0.0.1:{actual_local_port}"

    return (name, connect_to, str(actual_local_port), remote, profile, status), actual_local_port, use_hostname_forwarding


def _make_connection_table() -> Table:
    """Create the standard connection summary table."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Database", style="green")
    table.add_column("Connect To", style="cyan")
    table.add_column("Local Port", style="yellow", justify="right")
    table.add_column("Remote", style="dim")
    table.add_column("Profile", style="dim")
    table.add_column("Status", style="white")
    return table


def _build_threads(
    databases: dict,
    no_hosts: bool,
    managed_hosts: set,
    table: Table,
    registry: ForwarderRegistry,
) -> tuple[list, int, int]:
    """Populate table rows and start a thread per connectable DB.

    Returns (threads, port_conflicts, missing_hosts).
    """
    threads = []
    used_local_ports: set = set()
    next_available_port = 15432
    port_conflicts = 0
    missing_hosts = 0

    def get_unique_local_port(preferred_port: int) -> int:
        nonlocal next_available_port
        port = preferred_port
        if port in used_local_ports:
            port = next_available_port
        while port in used_local_ports or _find_free_port(port) != port:
            port += 1
        next_available_port = max(next_available_port, port + 1)
        used_local_ports.add(port)
        return port

    for name, db_config in databases.items():
        row, actual_local_port, use_hostname_forwarding = _process_db_for_table(name, db_config, no_hosts, managed_hosts, get_unique_local_port)
        table.add_row(*row)

        if actual_local_port is None:
            status = row[-1]
            if "occupied" in status:
                port_conflicts += 1
            elif "hosts" in status.lower():
                missing_hosts += 1
            continue

        thread = threading.Thread(
            target=_run_connection_loop,
            args=(name, db_config, actual_local_port, use_hostname_forwarding, registry),
            daemon=True,
        )
        thread.start()
        threads.append((name, thread))
        time.sleep(0.5)

    return threads, port_conflicts, missing_hosts


def _databases_needing_setup(databases: dict, managed_hosts: set) -> list[str]:
    """Return names of DBs that lack hostname forwarding config or /etc/hosts entry."""
    needs = []
    for name, cfg in databases.items():
        local_address = cfg.get("local_address", "127.0.0.1")
        if local_address == "127.0.0.1":
            needs.append(name)
        elif cfg["host"] not in managed_hosts:
            needs.append(name)
    return needs
