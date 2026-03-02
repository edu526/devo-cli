"""Database connect command."""

import threading
import time

import click
from rich.console import Console

from cli_tool.ssm.core import PortForwarder, SSMConfigManager, SSMSession
from cli_tool.ssm.utils import HostsManager

console = Console()


def _connect_all_databases(config_manager, databases, no_hosts):
  """Helper function to connect to all databases"""
  console.print("[cyan]Starting all connections...[/cyan]\n")

  hosts_manager = HostsManager()
  managed_entries = hosts_manager.get_managed_entries()
  managed_hosts = {host for _, host in managed_entries}

  port_forwarder = PortForwarder()
  threads = []

  used_local_ports = set()
  next_available_port = 15432

  def get_unique_local_port(preferred_port):
    nonlocal next_available_port
    if preferred_port not in used_local_ports:
      used_local_ports.add(preferred_port)
      return preferred_port
    while next_available_port in used_local_ports:
      next_available_port += 1
    used_local_ports.add(next_available_port)
    result = next_available_port
    next_available_port += 1
    return result

  def start_connection(name, db_config, actual_local_port):
    try:
      SSMSession.start_port_forwarding_to_remote(
        bastion=db_config["bastion"],
        host=db_config["host"],
        port=db_config["port"],
        local_port=actual_local_port,
        region=db_config["region"],
        profile=db_config.get("profile"),
      )
    except Exception as e:
      console.print(f"[red]✗[/red] {name}: {e}")

  for name, db_config in databases.items():
    local_address = db_config.get("local_address", "127.0.0.1")
    use_hostname_forwarding = (local_address != "127.0.0.1") and not no_hosts

    if use_hostname_forwarding and db_config["host"] not in managed_hosts:
      console.print(f"[yellow]⚠[/yellow] {name}: Not in /etc/hosts (run 'devo ssm hosts setup')")
      continue

    if use_hostname_forwarding:
      preferred_local_port = db_config.get("local_port", db_config["port"])
      actual_local_port = get_unique_local_port(preferred_local_port)

      profile_text = db_config.get("profile", "default")
      port_info = f"{local_address}:{db_config['port']}"
      if actual_local_port != preferred_local_port:
        port_info += f" [dim](local: {actual_local_port})[/dim]"

      console.print(f"[green]✓[/green] {name}: {db_config['host']} ({port_info}) [dim](profile: {profile_text})[/dim]")

      try:
        port_forwarder.start_forward(local_address=local_address, local_port=db_config["port"], target_port=actual_local_port)
        thread = threading.Thread(target=start_connection, args=(name, db_config, actual_local_port), daemon=True)
        thread.start()
        threads.append((name, thread))
        time.sleep(0.5)
      except Exception as e:
        console.print(f"[red]✗[/red] {name}: {e}")
    else:
      console.print(f"[yellow]⚠[/yellow] {name}: Hostname forwarding not configured (skipping)")

  if not threads:
    console.print("\n[yellow]No databases to connect[/yellow]")
    console.print("Run: devo ssm hosts setup")
    return

  console.print("\n[green]All connections started![/green]")
  console.print("[yellow]Press Ctrl+C to stop all connections[/yellow]\n")

  try:
    while any(thread.is_alive() for _, thread in threads):
      time.sleep(1)
  except KeyboardInterrupt:
    console.print("\n[cyan]Stopping all connections...[/cyan]")
    port_forwarder.stop_all()
    console.print("[green]All connections closed[/green]")


@click.command()
@click.argument("name", required=False)
@click.option("--no-hosts", is_flag=True, help="Disable hostname forwarding (use localhost)")
def connect_database(name, no_hosts):
  """Connect to a configured database (uses hostname forwarding by default)"""
  config_manager = SSMConfigManager()
  databases = config_manager.list_databases()

  if not databases:
    console.print("[red]No databases configured[/red]")
    console.print("\nAdd a database with: devo ssm database add")
    return

  if not name:
    console.print("[cyan]Select database to connect:[/cyan]\n")
    db_list = list(databases.keys())

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
        return

      if choice == len(db_list) + 1:
        _connect_all_databases(config_manager, databases, no_hosts)
        return

      name = db_list[choice - 1]

    except (KeyboardInterrupt, click.Abort):
      console.print("\n[yellow]Cancelled[/yellow]")
      return

  db_config = config_manager.get_database(name)

  if not db_config:
    console.print(f"[red]Database '{name}' not found in config[/red]")
    console.print("\nAvailable databases:")
    for db_name in databases.keys():
      console.print(f"  - {db_name}")
    return

  local_address = db_config.get("local_address", "127.0.0.1")
  use_hostname_forwarding = (local_address != "127.0.0.1") and not no_hosts

  if use_hostname_forwarding:
    hosts_manager = HostsManager()
    managed_entries = hosts_manager.get_managed_entries()
    hostname_in_hosts = any(host == db_config["host"] for _, host in managed_entries)

    if not hostname_in_hosts:
      console.print(f"[yellow]Warning: {db_config['host']} not found in /etc/hosts[/yellow]")
      console.print("[dim]Run 'devo ssm hosts setup' to configure hostname forwarding[/dim]\n")

      if click.confirm("Continue with localhost forwarding instead?", default=True):
        use_hostname_forwarding = False
      else:
        console.print("[yellow]Cancelled[/yellow]")
        return

  if use_hostname_forwarding:
    profile_text = db_config.get("profile", "default")
    console.print(f"[cyan]Connecting to {name}...[/cyan]")
    console.print(f"[dim]Hostname: {db_config['host']}[/dim]")
    console.print(f"[dim]Profile: {profile_text}[/dim]")
    console.print(f"[dim]Forwarding: {local_address}:{db_config['port']} -> 127.0.0.1:{db_config['local_port']}[/dim]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

    port_forwarder = PortForwarder()

    try:
      port_forwarder.start_forward(local_address=local_address, local_port=db_config["port"], target_port=db_config["local_port"])

      exit_code = SSMSession.start_port_forwarding_to_remote(
        bastion=db_config["bastion"],
        host=db_config["host"],
        port=db_config["port"],
        local_port=db_config["local_port"],
        region=db_config["region"],
        profile=db_config.get("profile"),
      )

      if exit_code != 0:
        console.print("[red]SSM session failed[/red]")

    except KeyboardInterrupt:
      console.print("\n[cyan]Stopping...[/cyan]")
    except Exception as e:
      console.print(f"\n[red]Error: {e}[/red]")
      return
    finally:
      port_forwarder.stop_all()
      console.print("[green]Connection closed[/green]")
  else:
    profile_text = db_config.get("profile", "default")

    if local_address != "127.0.0.1" and no_hosts:
      console.print("[yellow]Hostname forwarding disabled (using localhost)[/yellow]")
    elif local_address == "127.0.0.1":
      console.print("[yellow]Hostname forwarding not configured (using localhost)[/yellow]")
      console.print("[dim]Run 'devo ssm hosts setup' to enable hostname forwarding[/dim]\n")

    console.print(f"[cyan]Connecting to {name}...[/cyan]")
    console.print(f"[dim]{db_config['host']}:{db_config['port']} -> localhost:{db_config['local_port']}[/dim]")
    console.print(f"[dim]Profile: {profile_text}[/dim]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

    try:
      exit_code = SSMSession.start_port_forwarding_to_remote(
        bastion=db_config["bastion"],
        host=db_config["host"],
        port=db_config["port"],
        local_port=db_config["local_port"],
        region=db_config["region"],
        profile=db_config.get("profile"),
      )
      if exit_code != 0:
        console.print("[red]Connection failed[/red]")
    except KeyboardInterrupt:
      console.print("\n[green]Connection closed[/green]")
