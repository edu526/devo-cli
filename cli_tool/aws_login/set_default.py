"""Set default AWS profile."""

import os
import sys
from pathlib import Path

import click
from rich.console import Console

from cli_tool.aws_login.config import list_aws_profiles

console = Console()


def set_default_profile(profile_name=None):
    """Set default AWS profile by exporting AWS_PROFILE environment variable.

    Args:
      profile_name: Name of the profile to set as default
    """
    # Get available profiles
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found[/yellow]")
        sys.exit(1)

    # If no profile specified, show selection
    if not profile_name:
        console.print("[blue]Available profiles:[/blue]")
        for i, prof in enumerate(profiles, 1):
            console.print(f"  {i}. {prof}")

        choice = click.prompt("\nSelect profile number", type=int)
        if 1 <= choice <= len(profiles):
            profile_name = profiles[choice - 1]
        else:
            console.print("[red]Invalid selection[/red]")
            sys.exit(1)

    # Verify profile exists
    if profile_name not in profiles:
        console.print(f"[red]Profile '{profile_name}' not found[/red]")
        console.print("\nAvailable profiles:")
        for prof in profiles:
            console.print(f"  - {prof}")
        sys.exit(1)

    # Detect user's shell
    shell = os.environ.get("SHELL", "")
    shell_name = Path(shell).name if shell else "bash"

    # Determine config file and export line based on shell
    home = Path.home()
    if "zsh" in shell_name:
        config_file = home / ".zshrc"
        export_line = f"export AWS_PROFILE={profile_name}"
    elif "fish" in shell_name:
        config_file = home / ".config" / "fish" / "config.fish"
        export_line = f"set -gx AWS_PROFILE {profile_name}"
    else:
        config_file = home / ".bashrc"
        export_line = f"export AWS_PROFILE={profile_name}"

    # Update or add AWS_PROFILE in config file
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                lines = f.readlines()

            # Find and update existing AWS_PROFILE line
            new_lines = []
            found = False
            for line in lines:
                if "AWS_PROFILE" in line and ("export" in line or "set -gx" in line):
                    # Replace the line
                    new_lines.append(f"{export_line}\n")
                    found = True
                else:
                    new_lines.append(line)

            if found:
                # Write updated content
                with open(config_file, "w") as f:
                    f.writelines(new_lines)
                console.print(f"\n[green]✓ Updated AWS_PROFILE in {config_file}[/green]")
            else:
                # Add new line
                with open(config_file, "a") as f:
                    f.write("\n# AWS default profile (added by devo-cli)\n")
                    f.write(f"{export_line}\n")
                console.print(f"\n[green]✓ Added to {config_file}[/green]")

        except Exception as e:
            console.print(f"\n[yellow]Could not update {config_file}: {e}[/yellow]")
    else:
        console.print(f"\n[yellow]Config file {config_file} does not exist[/yellow]")

    # Set in current process (won't affect parent shell, but shows intent)
    os.environ["AWS_PROFILE"] = profile_name

    console.print(f"\n[green]✓ Set '{profile_name}' as default profile[/green]")
    console.print("\n[yellow]To apply in your current terminal, run:[/yellow]")
    console.print(f"  source {config_file}")
    console.print("\n[yellow]Or open a new terminal[/yellow]")
    console.print("\n[cyan]You can now use AWS CLI without --profile:[/cyan]")
    console.print("  aws s3 ls")
    console.print("  aws sts get-caller-identity")
