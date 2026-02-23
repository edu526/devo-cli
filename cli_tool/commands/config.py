"""Configuration management command."""

import json
import os
import subprocess
import sys

import click
from rich.console import Console
from rich.table import Table

from cli_tool.utils.config_manager import (
    get_config_path,
    get_config_value,
    load_config,
    reset_config,
    save_config,
    set_config_value,
)

console = Console()


@click.group()
def config():
    """Manage Devo CLI configuration."""
    pass


@config.command()
def show():
    """Show current configuration."""
    config_data = load_config()

    console.print("\n[bold green]Current Configuration[/bold green]")
    console.print(f"[dim]Location: {get_config_path()}[/dim]\n")

    # Bedrock Configuration
    table = Table(title="Bedrock Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="white")

    table.add_row("Model ID", config_data["bedrock"]["model_id"])
    table.add_row("Fallback Model ID", config_data["bedrock"]["fallback_model_id"])
    table.add_row("Region", config_data["bedrock"]["region"])

    console.print(table)
    console.print()

    # GitHub Configuration
    table = Table(title="GitHub Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="white")

    table.add_row("Repository Owner", config_data["github"]["repo_owner"])
    table.add_row("Repository Name", config_data["github"]["repo_name"])

    console.print(table)
    console.print()

    # CodeArtifact Configuration
    table = Table(title="CodeArtifact Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="white")

    table.add_row("Region", config_data["codeartifact"]["region"])
    table.add_row("Account ID", config_data["codeartifact"]["account_id"])
    table.add_row("SSO URL", config_data["codeartifact"]["sso_url"])
    table.add_row("Required Role", config_data["codeartifact"]["required_role"])

    console.print(table)
    console.print()

    # CodeArtifact Domains
    table = Table(title="CodeArtifact Domains", show_header=True, header_style="bold cyan")
    table.add_column("Domain", style="yellow")
    table.add_column("Repository", style="white")
    table.add_column("Namespace", style="cyan")

    for domain in config_data["codeartifact"]["domains"]:
        table.add_row(domain["domain"], domain["repository"], domain["namespace"])

    console.print(table)
    console.print()

    # Version Check
    table = Table(title="Version Check", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="white")

    enabled = "Enabled" if config_data["version_check"]["enabled"] else "Disabled"
    table.add_row("Status", enabled)

    console.print(table)
    console.print()


@config.command()
@click.argument("key")
@click.argument("value")
def set(key, value):
    """Set a configuration value.

    Examples:
      devo config set aws.region us-west-2
      devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
      devo config set version_check.enabled false
    """
    # Convert string booleans
    if value.lower() in ["true", "false"]:
        value = value.lower() == "true"

    try:
        set_config_value(key, value)
        console.print(f"[green]✓[/green] Set {key} = {value}")
        console.print(f"[dim]Configuration saved to: {get_config_path()}[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="red")
        sys.exit(1)


@config.command()
@click.argument("key")
def get(key):
    """Get a configuration value.

    Examples:
      devo config get aws.region
      devo config get bedrock.model_id
    """
    value = get_config_value(key)
    if value is None:
        console.print(f"[yellow]Key not found:[/yellow] {key}", style="red")
        sys.exit(1)

    console.print(value)


@config.command()
@click.confirmation_option(prompt="Are you sure you want to reset configuration to defaults?")
def reset():
    """Reset configuration to defaults."""
    try:
        reset_config()
        console.print("[green]✓[/green] Configuration reset to defaults")
        console.print(f"[dim]Configuration file: {get_config_path()}[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}", style="red")
        sys.exit(1)


@config.command()
def edit():
    """Open configuration file in default editor."""
    import platform
    import shutil

    config_path = get_config_path()

    # Ensure config file exists
    load_config()

    # Try to open with default editor
    editor = None

    # Try environment variables
    for env_var in ["VISUAL", "EDITOR"]:
        editor = os.environ.get(env_var)
        if editor:
            break

    # Fallback to platform-specific editors
    if not editor:
        system = platform.system().lower()

        if system == "windows":
            # Windows editors
            for cmd in ["notepad.exe", "notepad++.exe", "code.cmd", "code"]:
                if shutil.which(cmd):
                    editor = cmd
                    break
        elif system == "darwin":
            # macOS editors
            for cmd in ["nano", "vim", "vi", "code", "open -e"]:
                if cmd == "open -e" or shutil.which(cmd.split()[0]):
                    editor = cmd
                    break
        else:
            # Linux editors
            for cmd in ["nano", "vim", "vi", "code", "gedit", "kate"]:
                if shutil.which(cmd):
                    editor = cmd
                    break

    if not editor:
        console.print(f"[yellow]No editor found. Edit manually:[/yellow] {config_path}")
        sys.exit(1)

    try:
        # Handle editors with arguments (like 'open -e')
        if " " in editor:
            subprocess.run(editor.split() + [config_path])
        else:
            subprocess.run([editor, config_path])
    except Exception as e:
        console.print(f"[red]Error opening editor:[/red] {str(e)}", style="red")
        console.print(f"[yellow]Edit manually:[/yellow] {config_path}")
        sys.exit(1)


@config.command()
def path():
    """Show configuration file path."""
    console.print(get_config_path())


@config.command()
@click.argument("output_file", type=click.Path())
def export(output_file):
    """Export configuration to a file.

    Example:
      devo config export my-config.json
      devo config export ~/backup/devo-config.json
    """
    try:
        config_data = load_config()

        from pathlib import Path

        output_path = Path(output_file)

        # Create parent directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        console.print(f"[green]✓[/green] Configuration exported to: {output_path}")
    except Exception as e:
        console.print(f"[red]Error exporting configuration:[/red] {str(e)}", style="red")
        sys.exit(1)


@config.command("import")
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--merge",
    is_flag=True,
    help="Merge with existing configuration instead of replacing",
)
def import_config(input_file, merge):
    """Import configuration from a file.

    By default, replaces the entire configuration.
    Use --merge to merge with existing configuration.

    Examples:
      devo config import my-config.json
      devo config import ~/backup/devo-config.json --merge
    """
    try:
        from pathlib import Path

        input_path = Path(input_file)

        # Load the input configuration
        with open(input_path, "r", encoding="utf-8") as f:
            imported_config = json.load(f)

        if merge:
            # Merge with existing configuration
            existing_config = load_config()
            from cli_tool.utils.config_manager import _deep_merge

            merged_config = _deep_merge(existing_config, imported_config)
            save_config(merged_config)
            console.print(f"[green]✓[/green] Configuration merged from: {input_path}")
        else:
            # Replace entire configuration
            save_config(imported_config)
            console.print(f"[green]✓[/green] Configuration imported from: {input_path}")

        console.print(f"[dim]Configuration saved to: {get_config_path()}[/dim]")
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON file[/red] - {str(e)}", style="red")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error importing configuration:[/red] {str(e)}", style="red")
        sys.exit(1)


@config.command()
def validate():
    """Validate configuration file."""
    try:
        load_config()  # Just validate it loads correctly
        console.print("[green]✓[/green] Configuration is valid")

        # Check for required keys
        required_keys = [
            "bedrock.model_id",
            "bedrock.region",
            "github.repo_owner",
            "github.repo_name",
            "codeartifact.region",
            "codeartifact.account_id",
            "codeartifact.sso_url",
            "codeartifact.required_role",
            "version_check.enabled",
        ]

        missing_keys = []
        for key in required_keys:
            if get_config_value(key) is None:
                missing_keys.append(key)

        if missing_keys:
            console.print("\n[yellow]Warning: Missing keys:[/yellow]")
            for key in missing_keys:
                console.print(f"  - {key}")
            console.print("\n[dim]Run 'devo config reset' to restore defaults[/dim]")
        else:
            console.print("[dim]All required keys present[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Configuration is invalid:[/red] {str(e)}", style="red")
        console.print("\n[dim]Run 'devo config reset' to restore defaults[/dim]")
        sys.exit(1)


@config.group()
def registry():
    """Manage CodeArtifact registries."""
    pass


@registry.command("list")
def registry_list():
    """List all CodeArtifact registries."""
    config_data = load_config()
    domains = config_data.get("codeartifact", {}).get("domains", [])

    if not domains:
        console.print("[yellow]No registries configured[/yellow]")
        return

    table = Table(title="CodeArtifact Registries", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim")
    table.add_column("Domain", style="yellow")
    table.add_column("Repository", style="white")
    table.add_column("Namespace", style="cyan")

    for idx, domain in enumerate(domains, 1):
        table.add_row(str(idx), domain["domain"], domain["repository"], domain["namespace"])

    console.print(table)


@registry.command("add")
@click.option("--domain", required=True, help="Domain name")
@click.option("--repository", required=True, help="Repository name")
@click.option("--namespace", required=True, help="NPM namespace (e.g., @myorg)")
def registry_add(domain, repository, namespace):
    """Add a new CodeArtifact registry.

    Example:
      devo config registry add --domain my-domain --repository my-repo --namespace @myorg
    """
    config_data = load_config()

    # Ensure codeartifact.domains exists
    if "codeartifact" not in config_data:
        config_data["codeartifact"] = {}
    if "domains" not in config_data["codeartifact"]:
        config_data["codeartifact"]["domains"] = []

    # Check if registry already exists
    for existing in config_data["codeartifact"]["domains"]:
        if existing["domain"] == domain and existing["repository"] == repository:
            console.print(f"[yellow]Registry '{domain}/{repository}' already exists[/yellow]")
            sys.exit(1)

    # Add new registry
    new_domain = {"domain": domain, "repository": repository, "namespace": namespace}
    config_data["codeartifact"]["domains"].append(new_domain)

    save_config(config_data)
    console.print(f"[green]✓[/green] Added registry: {domain}/{repository} ({namespace})")


@registry.command("remove")
@click.argument("index", type=int)
def registry_remove(index):
    """Remove a CodeArtifact registry by index.

    Use 'devo config registry list' to see registry indices.

    Example:
      devo config registry remove 2
    """
    config_data = load_config()
    domains = config_data.get("codeartifact", {}).get("domains", [])

    if not domains:
        console.print("[yellow]No registries configured[/yellow]")
        sys.exit(1)

    if index < 1 or index > len(domains):
        console.print(f"[red]Invalid index. Must be between 1 and {len(domains)}[/red]")
        sys.exit(1)

    removed = domains.pop(index - 1)
    save_config(config_data)

    console.print(f"[green]✓[/green] Removed registry: {removed['domain']}/{removed['repository']} ({removed['namespace']})")


if __name__ == "__main__":
    config()
