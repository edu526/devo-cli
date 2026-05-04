"""Database connect command."""

import socket
import sys
import threading
import time
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from cli_tool.commands.ssm.core import PortForwarder, SSMConfigManager, SSMSession
from cli_tool.commands.ssm.utils import HostsManager

console = Console()

_RECONNECT_DELAY = 3
_TOKENS_EXPIRED_MSG = "\n[red]❌ AWS tokens are expired.[/red]"
_TOKENS_REFRESH_MSG = "[yellow]Run 'devo aws-login refresh' to renew your tokens.[/yellow]"


# ---------------------------------------------------------------------------
# ForwarderRegistry
# ---------------------------------------------------------------------------


class ForwarderRegistry:
    """Thread-safe registry of active PortForwarder instances for Ctrl+C cleanup.

    Also exposes a `stop_event` so daemon worker threads can detect that the
    main thread has initiated shutdown and bail out instead of entering the
    auto-reconnect loop.
    """

    def __init__(self):
        self._forwarders: list = []
        self._lock = threading.Lock()
        self.stop_event = threading.Event()

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
            for pf in self._forwarders:
                pf.stop_all()


# ---------------------------------------------------------------------------
# Helpers
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
    """Return True if address:port can be bound (no existing listener occupies it)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((address, port))
            return True
        except OSError:
            return False


def _is_wildcard_bind_blocking(port: int) -> bool:
    """Return True if `port` is held by a wildcard listener (0.0.0.0 or ::).

    Probes unused loopback IPs. If none can be bound, something is listening on
    a wildcard address and is blocking every loopback IP — typically a local
    Postgres/MySQL configured with `listen_addresses = '*'`.
    """
    for probe in ("127.0.0.91", "127.0.0.173"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((probe, port))
                return False
            except OSError:
                continue
    return True


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
            # Wakes up immediately when the main thread sets the event.
            if stop_event.wait(_RECONNECT_DELAY):
                return False
        else:
            time.sleep(_RECONNECT_DELAY)
    except KeyboardInterrupt:
        console.print("\n[green]Connection closed[/green]")
        return False
    console.print(f"[cyan]Reconnecting to {name}...[/cyan]\n")
    return True


def _run_attempt(
    db_config: dict,
    actual_local_port: int,
    use_hostname_forwarding: bool,
    registry: Optional[ForwarderRegistry] = None,
) -> int:
    """Run a single SSM connection attempt. Returns the SSM exit code."""
    local_address = db_config.get("local_address", "127.0.0.1")
    pf = None
    if use_hostname_forwarding:
        pf = PortForwarder()
        if registry is not None:
            registry.add(pf)
        pf.start_forward(local_address, db_config["port"], actual_local_port)

    try:
        return SSMSession.start_port_forwarding_to_remote(
            bastion=db_config["bastion"],
            host=db_config["host"],
            port=db_config["port"],
            local_port=actual_local_port,
            region=db_config["region"],
            profile=db_config.get("profile"),
        )
    finally:
        if pf is not None:
            pf.stop_all()
            if registry is not None:
                registry.remove(pf)


def _process_db_for_table(
    name: str,
    db_config: dict,
    no_hosts: bool,
    managed_hosts: set,
    get_unique_local_port,
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

    # Not configured for hostname forwarding and --no-hosts not requested: suggest hosts setup
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

    # In --no-hosts mode, avoid using the remote DB port as the local SSM port (it may be
    # occupied by a local DB service). Fall back to 15432 if local_port is not configured.
    fallback_port = db_config["port"] if use_hostname_forwarding else 15432
    preferred_local_port = db_config.get("local_port", fallback_port)
    actual_local_port = get_unique_local_port(preferred_local_port)
    if actual_local_port != preferred_local_port:
        console.print(f"[yellow]⚠ {name}: Port {preferred_local_port} in use, using {actual_local_port} instead[/yellow]")
    status = f"[yellow]✓ Port {actual_local_port}[/yellow]" if actual_local_port != preferred_local_port else "[green]✓ Connected[/green]"

    if use_hostname_forwarding:
        connect_to = f"{local_address}:{db_config['port']}"
    else:
        connect_to = f"127.0.0.1:{actual_local_port}"

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


# ---------------------------------------------------------------------------
# Core connection loop
# ---------------------------------------------------------------------------


def _run_connection_loop(
    name: str,
    db_config: dict,
    actual_local_port: int,
    use_hostname_forwarding: bool,
    registry: Optional[ForwarderRegistry] = None,
) -> None:
    """Core connection loop: optional socat + SSM + auto-reconnect."""
    stop_event = registry.stop_event if registry is not None else None
    is_reconnect = False
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        if is_reconnect:
            console.print(f"[green]✓ Reconnected to {name}[/green]\n")
        try:
            _run_attempt(db_config, actual_local_port, use_hostname_forwarding, registry)
        except KeyboardInterrupt:
            console.print("\n[green]Connection closed[/green]")
            return
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            return

        # Main thread initiated shutdown while the SSM session was alive — bail
        # out before printing the misleading "Connection lost. Reconnecting..."
        if stop_event is not None and stop_event.is_set():
            return

        if SSMSession._is_token_expired(region=db_config["region"], profile=db_config.get("profile")):
            console.print(_TOKENS_EXPIRED_MSG)
            console.print(_TOKENS_REFRESH_MSG)
            return

        if not _wait_before_reconnect(name, stop_event):
            return

        is_reconnect = True


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _build_threads(
    databases: dict,
    no_hosts: bool,
    managed_hosts: set,
    table: Table,
    registry: "ForwarderRegistry",
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


def _is_windows_admin() -> bool:
    """Return True if the current Windows process is elevated.

    Non-Windows always returns True: on Linux/macOS the hosts file write is done
    via `sudo`, which prompts the user — no pre-check needed.
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _maybe_run_auto_setup(databases: dict, managed_hosts: set, no_auto_setup: bool) -> set:
    """Offer to run hosts setup for DBs missing config; return the (possibly refreshed) managed_hosts."""
    if no_auto_setup:
        return managed_hosts
    if not sys.stdin.isatty():
        return managed_hosts

    pending = _databases_needing_setup(databases, managed_hosts)
    if not pending:
        return managed_hosts

    # On Windows we need elevation upfront; warn instead of prompting a doomed run.
    if not _is_windows_admin():
        console.print(f"\n[yellow]⚠ {len(pending)} database(s) need hostname forwarding setup:[/yellow] {', '.join(pending)}")
        console.print(
            "[dim]Setup requires Administrator on Windows. Re-open PowerShell as Administrator "
            "and run `devo ssm connect` (or `devo ssm hosts setup`) again.[/dim]\n"
        )
        return managed_hosts

    sudo_note = "(requires Administrator)" if sys.platform == "win32" else "(requires sudo)"
    console.print(f"\n[yellow]⚠ {len(pending)} database(s) need hostname forwarding setup:[/yellow] {', '.join(pending)}")
    console.print("[dim]Setup will assign loopback IPs and add entries to /etc/hosts " + sudo_note + ".[/dim]")

    try:
        proceed = click.confirm("Run setup now?", default=True)
    except click.Abort:
        return managed_hosts

    if not proceed:
        return managed_hosts

    # Local import avoids a circular import at module load time
    from cli_tool.commands.ssm.commands.hosts.setup import setup_databases

    succeeded, failed = setup_databases(pending)
    if succeeded:
        # Reload managed hosts and the live db_config dicts so the caller sees fresh values
        refreshed = SSMConfigManager().list_databases()
        for name in succeeded:
            if name in databases and name in refreshed:
                databases[name].update(refreshed[name])
        managed_hosts = {host for _, host in HostsManager().get_managed_entries()}
    if failed:
        hint = "re-open PowerShell as Administrator" if sys.platform == "win32" else "re-run with sudo"
        console.print(f"[red]✗ Setup failed for {len(failed)} database(s) ({', '.join(failed)}) — {hint} and retry.[/red]")
    console.print()
    return managed_hosts


def _print_no_connect_tip(port_conflicts: int, missing_hosts: int) -> None:
    console.print("[yellow]No databases to connect[/yellow]")
    if port_conflicts > 0:
        console.print("[dim]Stop the local service occupying port 5432, or use --no-hosts to connect via localhost.[/dim]")
    elif missing_hosts > 0:
        console.print("[dim]Run: devo ssm hosts setup[/dim]")


def _connect_databases(databases: dict, no_hosts: bool, no_auto_setup: bool = False) -> None:
    """Connect to one or more databases in parallel threads."""
    if not _validate_tokens(databases):
        return

    managed_hosts = {host for _, host in HostsManager().get_managed_entries()}
    if not no_hosts:
        managed_hosts = _maybe_run_auto_setup(databases, managed_hosts, no_auto_setup)

    console.print("[cyan]Starting connections...[/cyan]\n")

    table = _make_connection_table()
    registry = ForwarderRegistry()
    threads, port_conflicts, missing_hosts = _build_threads(databases, no_hosts, managed_hosts, table, registry)

    console.print(table)
    console.print()

    if not threads:
        _print_no_connect_tip(port_conflicts, missing_hosts)
        return

    console.print("[green]Connection(s) started![/green]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

    try:
        while any(thread.is_alive() for _, thread in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        # Absorb extra Ctrl+C presses during cleanup so the user never sees
        # an unhandled traceback if they hit it twice.
        try:
            console.print("\n[cyan]Stopping all connections...[/cyan]")
            # Signal daemon threads first so they exit their reconnect loop
            # cleanly instead of printing "Connection lost. Reconnecting...".
            registry.stop_event.set()
            registry.stop_all()
            for _, thread in threads:
                thread.join(timeout=2)
            console.print("[green]All connections closed[/green]")
        except KeyboardInterrupt:
            pass


def _show_database_selection(databases: dict) -> str | None:
    """Show interactive database selection menu. Returns selected name or None."""
    db_list = list(databases.keys())
    console.print("[cyan]Select database to connect:[/cyan]\n")

    for i, db_name in enumerate(db_list, 1):
        db = databases[db_name]
        profile_text = db.get("profile", "default")
        console.print(f"  {i}. {db_name} ({db['host']}) [dim](profile: {profile_text})[/dim]")

    console.print(f"  {len(db_list) + 1}. Connect to all databases")
    console.print()

    try:
        choice = click.prompt("Enter number", type=int, default=1)
        if choice < 1 or choice > len(db_list) + 1:
            console.print("[red]Invalid selection[/red]")
            return None
        if choice == len(db_list) + 1:
            return "ALL"
        return db_list[choice - 1]
    except (KeyboardInterrupt, click.Abort):
        console.print("\n[yellow]Cancelled[/yellow]")
        return None


@click.command()
@click.argument("name", required=False)
@click.option("--no-hosts", is_flag=True, help="Disable hostname forwarding (use localhost)")
@click.option("--all", "connect_all", is_flag=True, help="Connect to all configured databases at once")
@click.option("--no-auto-setup", is_flag=True, help="Don't prompt to run hosts setup for unconfigured databases")
def connect_database(name, no_hosts, connect_all, no_auto_setup):
    """Connect to a configured database (uses hostname forwarding by default)"""
    config_manager = SSMConfigManager()
    databases = config_manager.list_databases()

    if not databases:
        console.print("[red]No databases configured[/red]")
        console.print("\nAdd a database with: devo ssm database add")
        return

    if connect_all:
        _connect_databases(databases, no_hosts, no_auto_setup)
        return

    if not name:
        selection = _show_database_selection(databases)
        if selection is None:
            return
        if selection == "ALL":
            _connect_databases(databases, no_hosts, no_auto_setup)
            return
        name = selection

    db_config = config_manager.get_database(name)

    if not db_config:
        console.print(f"[red]Database '{name}' not found in config[/red]")
        console.print("\nAvailable databases:")
        for db_name in databases.keys():
            console.print(f"  - {db_name}")
        return

    _connect_databases({name: db_config}, no_hosts, no_auto_setup)
