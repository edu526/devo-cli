"""AWS Systems Manager Session Manager commands"""

import multiprocessing
import sys
import time

import click
from rich.console import Console
from rich.table import Table

from cli_tool.ssm.config import SSMConfigManager
from cli_tool.ssm.hosts_manager import HostsManager
from cli_tool.ssm.port_forwarder import PortForwarder
from cli_tool.ssm.session import SSMSession

# Set multiprocessing start method for Windows compatibility
if sys.platform == "win32":
    multiprocessing.set_start_method("spawn", force=True)

# Backward compatibility alias
SocatManager = PortForwarder

console = Console()


@click.group()
def ssm():
    """AWS Systems Manager Session Manager commands"""
    pass


# ============================================================================
# Database Connection Commands
# ============================================================================


@ssm.command("connect")
@click.argument("name", required=False)
@click.option("--no-hosts", is_flag=True, help="Disable hostname forwarding (use localhost)")
@click.option("--profile", help="Override AWS profile for this connection")
@click.option("--config-path", help="Custom config file path")
def connect_database(name, no_hosts, profile, config_path):
    """Connect to a configured database (uses hostname forwarding by default)"""
    config_manager = SSMConfigManager(config_path)
    databases = config_manager.list_databases()

    if not databases:
        console.print("[red]No databases configured[/red]")
        console.print("\nAdd a database with: devo ssm add-db")
        return

    # If no name provided, show interactive menu
    if not name:
        console.print("[cyan]Select database to connect:[/cyan]\n")

        db_list = list(databases.keys())

        # Show options
        for i, db_name in enumerate(db_list, 1):
            db = databases[db_name]
            profile_text = profile or db.get("profile", "default")
            console.print(f"  {i}. {db_name} ({db['host']}) [dim](profile: {profile_text})[/dim]")

        console.print(f"  {len(db_list) + 1}. Connect to all databases")
        console.print()

        # Get user choice
        try:
            choice = click.prompt("Enter number", type=int, default=1)

            if choice < 1 or choice > len(db_list) + 1:
                console.print("[red]Invalid selection[/red]")
                return

            # Connect to all
            if choice == len(db_list) + 1:
                _connect_all_databases(config_manager, databases, no_hosts, profile)
                return

            # Connect to selected database
            name = db_list[choice - 1]

        except (KeyboardInterrupt, click.Abort):
            console.print("\n[yellow]Cancelled[/yellow]")
            return

    # Single database connection
    db_config = config_manager.get_database(name)

    if not db_config:
        console.print(f"[red]Database '{name}' not found in config[/red]")
        console.print("\nAvailable databases:")
        for db_name in databases.keys():
            console.print(f"  - {db_name}")
        return

    # Check if hostname forwarding is configured
    local_address = db_config.get("local_address", "127.0.0.1")
    use_hostname_forwarding = (local_address != "127.0.0.1") and not no_hosts

    if use_hostname_forwarding:
        # Validate that hostname is in /etc/hosts
        hosts_manager = HostsManager()
        managed_entries = hosts_manager.get_managed_entries()
        hostname_in_hosts = any(host == db_config["host"] for _, host in managed_entries)

        if not hostname_in_hosts:
            console.print(f"[yellow]Warning: {db_config['host']} not found in /etc/hosts[/yellow]")
            console.print("[dim]Run 'devo ssm hosts setup' to configure hostname forwarding[/dim]\n")

            # Ask if user wants to continue with localhost
            if click.confirm("Continue with localhost forwarding instead?", default=True):
                use_hostname_forwarding = False
            else:
                console.print("[yellow]Cancelled[/yellow]")
                return

    if use_hostname_forwarding:
        # Use hostname forwarding
        profile_text = profile or db_config.get("profile", "default")
        console.print(f"[cyan]Connecting to {name}...[/cyan]")
        console.print(f"[dim]Hostname: {db_config['host']}[/dim]")
        console.print(f"[dim]Profile: {profile_text}[/dim]")
        console.print(f"[dim]Forwarding: {local_address}:{db_config['port']} -> 127.0.0.1:{db_config['local_port']}[/dim]")
        console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

        port_forwarder = PortForwarder()

        try:
            # Start port forwarding
            port_forwarder.start_forward(local_address=local_address, local_port=db_config["port"], target_port=db_config["local_port"])

            # Start SSM session
            SSMSession.start_port_forwarding_to_remote(
                bastion=db_config["bastion"],
                host=db_config["host"],
                port=db_config["port"],
                local_port=db_config["local_port"],
                region=db_config["region"],
                profile=profile or db_config.get("profile"),  # Override profile if provided
            )
        except KeyboardInterrupt:
            console.print("\n[cyan]Stopping...[/cyan]")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
        finally:
            port_forwarder.stop_all()
            console.print("[green]Connection closed[/green]")
    else:
        # Use localhost forwarding (simple mode)
        profile_text = profile or db_config.get("profile", "default")

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
                profile=profile or db_config.get("profile"),  # Override profile if provided
            )
            if exit_code != 0:
                console.print("[red]Connection failed[/red]")
        except KeyboardInterrupt:
            console.print("\n[green]Connection closed[/green]")


def _connect_all_databases(config_manager, databases, no_hosts, profile_override=None):
    """Helper function to connect to all databases"""
    console.print("[cyan]Starting all connections...[/cyan]\n")

    # Validate hosts setup
    hosts_manager = HostsManager()
    managed_entries = hosts_manager.get_managed_entries()
    managed_hosts = {host for _, host in managed_entries}

    port_forwarder = PortForwarder()
    processes = []

    for name, db_config in databases.items():
        local_address = db_config.get("local_address", "127.0.0.1")
        use_hostname_forwarding = (local_address != "127.0.0.1") and not no_hosts

        # Check if hostname is in /etc/hosts
        if use_hostname_forwarding and db_config["host"] not in managed_hosts:
            console.print(f"[yellow]⚠[/yellow] {name}: Not in /etc/hosts (run 'devo ssm hosts setup')")
            continue

        if use_hostname_forwarding:
            profile_text = profile_override or db_config.get("profile", "default")
            console.print(f"[green]✓[/green] {name}: {db_config['host']} ({local_address}:{db_config['port']}) [dim](profile: {profile_text})[/dim]")

            try:
                # Start port forwarding
                port_forwarder.start_forward(local_address=local_address, local_port=db_config["port"], target_port=db_config["local_port"])

                # Start SSM session in separate process
                p = multiprocessing.Process(
                    target=SSMSession.start_port_forwarding_to_remote,
                    args=(
                        db_config["bastion"],
                        db_config["host"],
                        db_config["port"],
                        db_config["local_port"],
                        db_config["region"],
                        profile_override or db_config.get("profile"),  # Override profile if provided
                    ),
                )
                p.start()
                processes.append((name, p))

                # Small delay to avoid overwhelming the system
                time.sleep(0.5)

            except Exception as e:
                console.print(f"[red]✗[/red] {name}: {e}")
        else:
            console.print(f"[yellow]⚠[/yellow] {name}: Hostname forwarding not configured (skipping)")

    if not processes:
        console.print("\n[yellow]No databases to connect[/yellow]")
        console.print("Run: devo ssm hosts setup")
        return

    console.print("\n[green]All connections started![/green]")
    console.print("[yellow]Press Ctrl+C to stop all connections[/yellow]\n")

    try:
        for name, p in processes:
            p.join()
    except KeyboardInterrupt:
        console.print("\n[cyan]Stopping all connections...[/cyan]")
        for name, p in processes:
            p.terminate()
        port_forwarder.stop_all()
        console.print("[green]All connections closed[/green]")


@ssm.command("list")
@click.option("--config-path", help="Custom config file path")
def list_databases(config_path):
    """List configured databases"""
    config_manager = SSMConfigManager(config_path)
    databases = config_manager.list_databases()

    if not databases:
        console.print("[yellow]No databases configured[/yellow]")
        console.print("\nAdd a database with: devo ssm add-db")
        return

    table = Table(title="Configured Databases")
    table.add_column("Name", style="cyan")
    table.add_column("Host", style="white")
    table.add_column("Port", style="green")
    table.add_column("Profile", style="yellow")

    for name, db in databases.items():
        table.add_row(name, db["host"], str(db["port"]), db.get("profile", "-"))

    console.print(table)


@ssm.command("add-db")
@click.option("--name", required=True, help="Database configuration name")
@click.option("--bastion", required=True, help="Bastion instance ID")
@click.option("--host", required=True, help="Database host/endpoint")
@click.option("--port", required=True, type=int, help="Database port")
@click.option("--local-port", type=int, help="Local port (default: same as remote)")
@click.option("--region", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile")
@click.option("--config-path", help="Custom config file path")
def add_database(name, bastion, host, port, local_port, region, profile, config_path):
    """Add a database configuration"""
    config_manager = SSMConfigManager(config_path)

    config_manager.add_database(name=name, bastion=bastion, host=host, port=port, region=region, profile=profile, local_port=local_port)

    console.print(f"[green]Database '{name}' added successfully[/green]")
    console.print(f"\nConnect with: devo ssm connect {name}")


@ssm.command("remove-db")
@click.argument("name")
@click.option("--config-path", help="Custom config file path")
def remove_database(name, config_path):
    """Remove a database configuration"""
    config_manager = SSMConfigManager(config_path)

    if config_manager.remove_database(name):
        console.print(f"[green]Database '{name}' removed[/green]")
    else:
        console.print(f"[red]Database '{name}' not found[/red]")


# ============================================================================
# Instance Connection Commands
# ============================================================================


@ssm.command("shell")
@click.argument("name")
@click.option("--config-path", help="Custom config file path")
def connect_instance(name, config_path):
    """Connect to a configured instance via interactive shell"""
    config_manager = SSMConfigManager(config_path)
    instance_config = config_manager.get_instance(name)

    if not instance_config:
        console.print(f"[red]Instance '{name}' not found in config[/red]")
        console.print("\nAvailable instances:")
        for inst_name in config_manager.list_instances().keys():
            console.print(f"  - {inst_name}")
        return

    console.print(f"[cyan]Connecting to {name} ({instance_config['instance_id']})...[/cyan]")
    console.print("[yellow]Type 'exit' to close the session[/yellow]\n")

    try:
        SSMSession.start_session(instance_id=instance_config["instance_id"], region=instance_config["region"], profile=instance_config.get("profile"))
    except KeyboardInterrupt:
        console.print("\n[green]Session closed[/green]")


@ssm.command("list-instances")
@click.option("--config-path", help="Custom config file path")
def list_instances(config_path):
    """List configured instances"""
    config_manager = SSMConfigManager(config_path)
    instances = config_manager.list_instances()

    if not instances:
        console.print("[yellow]No instances configured[/yellow]")
        console.print("\nAdd an instance with: devo ssm add-instance")
        return

    table = Table(title="Configured Instances")
    table.add_column("Name", style="cyan")
    table.add_column("Instance ID", style="white")
    table.add_column("Region", style="green")
    table.add_column("Profile", style="yellow")

    for name, inst in instances.items():
        table.add_row(name, inst["instance_id"], inst["region"], inst.get("profile", "-"))

    console.print(table)


@ssm.command("add-instance")
@click.option("--name", required=True, help="Instance configuration name")
@click.option("--instance-id", required=True, help="EC2 instance ID")
@click.option("--region", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile")
@click.option("--config-path", help="Custom config file path")
def add_instance(name, instance_id, region, profile, config_path):
    """Add an instance configuration"""
    config_manager = SSMConfigManager(config_path)

    config_manager.add_instance(name=name, instance_id=instance_id, region=region, profile=profile)

    console.print(f"[green]Instance '{name}' added successfully[/green]")
    console.print(f"\nConnect with: devo ssm shell {name}")


@ssm.command("remove-instance")
@click.argument("name")
@click.option("--config-path", help="Custom config file path")
def remove_instance(name, config_path):
    """Remove an instance configuration"""
    config_manager = SSMConfigManager(config_path)

    if config_manager.remove_instance(name):
        console.print(f"[green]Instance '{name}' removed[/green]")
    else:
        console.print(f"[red]Instance '{name}' not found[/red]")


# ============================================================================
# Config Management Commands
# ============================================================================


@ssm.command("export")
@click.argument("output_path")
@click.option("--config-path", help="Custom config file path")
def export_config(output_path, config_path):
    """Export SSM configuration to a file"""
    config_manager = SSMConfigManager(config_path)

    try:
        config_manager.export_config(output_path)
        console.print(f"[green]Configuration exported to {output_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error exporting config: {e}[/red]")


@ssm.command("import")
@click.argument("input_path")
@click.option("--merge", is_flag=True, help="Merge with existing config instead of replacing")
@click.option("--config-path", help="Custom config file path")
def import_config(input_path, merge, config_path):
    """Import SSM configuration from a file"""
    config_manager = SSMConfigManager(config_path)

    try:
        config_manager.import_config(input_path, merge=merge)
        action = "merged" if merge else "imported"
        console.print(f"[green]Configuration {action} from {input_path}[/green]")
    except FileNotFoundError:
        console.print(f"[red]Config file not found: {input_path}[/red]")
    except Exception as e:
        console.print(f"[red]Error importing config: {e}[/red]")


@ssm.command("show-config")
@click.option("--config-path", help="Custom config file path")
def show_config(config_path):
    """Show the path to the SSM config file"""
    config_manager = SSMConfigManager(config_path)
    console.print(f"[cyan]Config file location:[/cyan] {config_manager.config_path}")

    if config_manager.config_path.exists():
        console.print("[green]File exists[/green]")
    else:
        console.print("[yellow]File does not exist yet (will be created on first use)[/yellow]")


# ============================================================================
# Manual Connection Commands (without config)
# ============================================================================


@ssm.command("forward")
@click.option("--bastion", required=True, help="Bastion instance ID")
@click.option("--host", required=True, help="Database/service endpoint")
@click.option("--port", default=5432, type=int, help="Remote port")
@click.option("--local-port", type=int, help="Local port (default: same as remote)")
@click.option("--region", default="us-east-1", help="AWS region")
@click.option("--profile", help="AWS profile")
def forward_manual(bastion, host, port, local_port, region, profile):
    """Manual port forwarding (without using config)"""
    if not local_port:
        local_port = port

    console.print(f"[cyan]Forwarding {host}:{port} -> localhost:{local_port}[/cyan]")
    console.print(f"[dim]Via bastion: {bastion}[/dim]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

    try:
        SSMSession.start_port_forwarding_to_remote(bastion=bastion, host=host, port=port, local_port=local_port, region=region, profile=profile)
    except KeyboardInterrupt:
        console.print("\n[green]Connection closed[/green]")


# ============================================================================
# /etc/hosts Management Commands (subgroup)
# ============================================================================


@ssm.group("hosts")
def hosts():
    """Manage /etc/hosts entries for hostname forwarding"""
    pass


@hosts.command("setup")
@click.option("--config-path", help="Custom config file path")
def hosts_setup(config_path):
    """Setup /etc/hosts entries for all configured databases"""
    config_manager = SSMConfigManager(config_path)
    hosts_manager = HostsManager()
    databases = config_manager.list_databases()

    if not databases:
        console.print("[yellow]No databases configured[/yellow]")
        return

    console.print("[cyan]Setting up /etc/hosts entries...[/cyan]\n")

    success_count = 0
    error_count = 0

    for name, db_config in databases.items():
        # Get or assign loopback IP
        if "local_address" not in db_config or db_config["local_address"] == "127.0.0.1":
            # Assign new loopback IP
            local_address = hosts_manager.get_next_loopback_ip()

            # Update config
            config = config_manager.load()
            config["databases"][name]["local_address"] = local_address
            config_manager.save(config)
        else:
            local_address = db_config["local_address"]

        # Add to /etc/hosts
        try:
            hosts_manager.add_entry(local_address, db_config["host"])
            console.print(f"[green]✓[/green] {name}: {db_config['host']} -> {local_address}")
            success_count += 1
        except Exception as e:
            console.print(f"[red]✗[/red] {name}: {e}")
            error_count += 1

    # Show appropriate completion message
    if error_count > 0 and success_count == 0:
        console.print("\n[red]Setup failed![/red]")
        console.print("[yellow]All entries failed. Please run your terminal as Administrator.[/yellow]")
    elif error_count > 0:
        console.print("\n[yellow]Setup partially complete[/yellow]")
        console.print(f"[dim]{success_count} succeeded, {error_count} failed[/dim]")
    else:
        console.print("\n[green]Setup complete![/green]")
        console.print("\n[dim]Your microservices can now use the real hostnames in their configuration.[/dim]")


@hosts.command("list")
def hosts_list():
    """List all /etc/hosts entries managed by Devo CLI"""
    hosts_manager = HostsManager()
    entries = hosts_manager.get_managed_entries()

    if not entries:
        console.print("[yellow]No managed entries in /etc/hosts[/yellow]")
        console.print("\nRun: devo ssm hosts setup")
        return

    table = Table(title="Managed /etc/hosts Entries")
    table.add_column("IP", style="cyan")
    table.add_column("Hostname", style="white")

    for ip, hostname in entries:
        table.add_row(ip, hostname)

    console.print(table)


@hosts.command("clear")
@click.confirmation_option(prompt="Remove all Devo CLI entries from /etc/hosts?")
def hosts_clear():
    """Remove all Devo CLI managed entries from /etc/hosts"""
    hosts_manager = HostsManager()

    try:
        hosts_manager.clear_all()
        console.print("[green]All managed entries removed from /etc/hosts[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@hosts.command("add")
@click.argument("name")
@click.option("--config-path", help="Custom config file path")
def hosts_add_single(name, config_path):
    """Add a single database hostname to /etc/hosts"""
    config_manager = SSMConfigManager(config_path)
    hosts_manager = HostsManager()

    db_config = config_manager.get_database(name)

    if not db_config:
        console.print(f"[red]Database '{name}' not found[/red]")
        return

    # Get or assign loopback IP
    if "local_address" not in db_config or db_config["local_address"] == "127.0.0.1":
        local_address = hosts_manager.get_next_loopback_ip()

        # Update config
        config = config_manager.load()
        config["databases"][name]["local_address"] = local_address
        config_manager.save(config)
    else:
        local_address = db_config["local_address"]

    try:
        hosts_manager.add_entry(local_address, db_config["host"])
        console.print(f"[green]Added {db_config['host']} -> {local_address}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@hosts.command("remove")
@click.argument("name")
@click.option("--config-path", help="Custom config file path")
def hosts_remove_single(name, config_path):
    """Remove a database hostname from /etc/hosts"""
    config_manager = SSMConfigManager(config_path)
    hosts_manager = HostsManager()

    db_config = config_manager.get_database(name)

    if not db_config:
        console.print(f"[red]Database '{name}' not found[/red]")
        return

    try:
        hosts_manager.remove_entry(db_config["host"])
        console.print(f"[green]Removed {db_config['host']} from /etc/hosts[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
