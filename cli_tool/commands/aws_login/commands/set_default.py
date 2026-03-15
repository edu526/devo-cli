"""Set default AWS profile."""

import os
import re
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

from cli_tool.commands.aws_login.core.config import list_aws_profiles
from cli_tool.commands.aws_login.core.credentials import check_profile_credentials_available, write_default_credentials

console = Console()

# AWS profile names: alphanumeric, hyphens, underscores, dots only
_SAFE_PROFILE_RE = re.compile(r"^[a-zA-Z0-9._-]{1,128}$")


def _format_source_label(source: str) -> str:
    """Format profile source with Rich color markup."""
    labels = {
        "sso": "[cyan]sso[/cyan]",
        "static": "[yellow]static[/yellow]",
        "both": "[green]both[/green]",
    }
    return labels.get(source, f"[dim]{source}[/dim]")


def _select_profile_interactively(profiles: list) -> str:
    """Display profile list and prompt user to select one. Returns profile name."""
    console.print("[blue]Available profiles:[/blue]")
    for i, (prof_name, source) in enumerate(profiles, 1):
        console.print(f"  {i}. {prof_name} [{_format_source_label(source)}]")

    choice = click.prompt("\nSelect profile number", type=int)
    if 1 <= choice <= len(profiles):
        return profiles[choice - 1][0]
    console.print("[red]Invalid selection[/red]")
    sys.exit(1)


def _get_shell_config(shell_name: str, profile_name: str) -> tuple:
    """Return (config_file_path, export_line) for the given shell.

    Path components are hardcoded literals — never derived from shell_name —
    so that static analysis can confirm there is no path injection.
    """
    home = Path.home()
    if shell_name == "fish":
        config_file = home / ".config" / "fish" / "config.fish"
        export_line = f"set -gx AWS_PROFILE {profile_name}"
    elif shell_name == "zsh":
        config_file = home / ".zshrc"
        export_line = f"export AWS_PROFILE={profile_name}"
    else:
        config_file = home / ".bashrc"
        export_line = f"export AWS_PROFILE={profile_name}"
    return config_file, export_line


def _update_shell_config_file(config_file: Path, export_line: str):
    """Update or append AWS_PROFILE export in a shell config file."""
    if not config_file.exists():
        console.print(f"\n[yellow]Config file {config_file} does not exist[/yellow]")
        return

    try:
        resolved = config_file.resolve()
        if not str(resolved).startswith(str(Path.home().resolve())):
            raise ValueError(f"Refusing to write outside home directory: {resolved}")

        lines = resolved.read_text().splitlines(keepends=True)
        new_lines = []
        found = False
        for line in lines:
            if "AWS_PROFILE" in line and ("export" in line or "set -gx" in line):
                new_lines.append(f"{export_line}\n")
                found = True
            else:
                new_lines.append(line)

        if found:
            resolved.write_text("".join(new_lines))  # NOSONAR: path validated to be within home directory above
            console.print(f"\n[green]✓ Updated AWS_PROFILE in {resolved}[/green]")
        else:
            with open(resolved, "a") as f:  # NOSONAR: path validated to be within home directory above
                f.write("\n# AWS default profile (added by devo-cli)\n")
                f.write(f"{export_line}\n")
            console.print(f"\n[green]✓ Added to {resolved}[/green]")
    except Exception as e:
        console.print(f"\n[yellow]Could not update {config_file}: {e}[/yellow]")


def _set_windows_profile(profile_name: str):
    """Set AWS_PROFILE persistently on Windows via setx."""
    try:
        result = subprocess.run(["setx", "AWS_PROFILE", profile_name], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            console.print(f"\n[green]✓ Set '{profile_name}' as default profile[/green]")
            console.print("\n[yellow]To apply in your current terminal:[/yellow]")
            console.print("  1. Close and reopen your terminal")
            console.print("  2. Or run in PowerShell:")
            console.print(f"     $env:AWS_PROFILE='{profile_name}'")
            console.print("  3. Or run in CMD:")
            console.print(f"     set AWS_PROFILE={profile_name}")
        else:
            console.print(f"\n[red]Failed to set environment variable: {result.stderr}[/red]")
            console.print("\n[yellow]You can set it manually:[/yellow]")
            console.print(f"  PowerShell: $env:AWS_PROFILE='{profile_name}'")
            console.print(f"  CMD: set AWS_PROFILE={profile_name}")
    except Exception as e:
        console.print(f"\n[yellow]Could not set environment variable: {e}[/yellow]")
        console.print(f"\n[yellow]Set manually — PowerShell: $env:AWS_PROFILE='{profile_name}'[/yellow]")


def _set_unix_profile(profile_name: str):
    """Update shell config file with AWS_PROFILE on Linux/macOS."""
    home = Path.home().resolve()
    # All paths are hardcoded literals; shell_name is used only as a dict key
    _shell_configs = {
        "fish": (home / ".config" / "fish" / "config.fish", f"set -gx AWS_PROFILE {profile_name}"),
        "zsh": (home / ".zshrc", f"export AWS_PROFILE={profile_name}"),
    }
    _default_config = (home / ".bashrc", f"export AWS_PROFILE={profile_name}")

    shell = os.environ.get("SHELL", "")
    shell_name = Path(shell).name if shell else "bash"
    config_file, export_line = _shell_configs.get(shell_name, _default_config)
    _update_shell_config_file(config_file, export_line)
    console.print(f"\n[green]✓ Set '{profile_name}' as default profile[/green]")
    console.print("\n[yellow]To apply in your current terminal, run:[/yellow]")
    console.print(f"  source {config_file}")
    console.print("\n[yellow]Or open a new terminal[/yellow]")


def _resolve_and_validate_profile(profile_name: str | None, profiles: list) -> str:
    """Resolve profile name interactively if needed, then validate format and existence.

    Args:
      profile_name: Profile name provided by the caller, or None to prompt.
      profiles: List of (name, source) tuples from list_aws_profiles().

    Returns:
      Validated profile name.
    """
    if not profile_name:
        profile_name = _select_profile_interactively(profiles)

    # Validate format to prevent OS command injection
    if not _SAFE_PROFILE_RE.match(profile_name):
        console.print(f"[red]Invalid profile name: '{profile_name}'[/red]")
        console.print("[dim]Profile names may only contain letters, digits, hyphens, underscores, and dots (max 128 chars).[/dim]")
        sys.exit(1)

    # Verify profile exists
    profile_names = [p[0] for p in profiles]
    if profile_name not in profile_names:
        console.print(f"[red]Profile '{profile_name}' not found[/red]")
        console.print("\nAvailable profiles:")
        for prof_name, source in profiles:
            console.print(f"  - {prof_name} [{source}]")
        sys.exit(1)

    return profile_name


def _write_default_credentials(profile_name: str) -> None:
    """Write temporary credentials for profile_name as [default] and print result."""
    console.print(f"\n[blue]Writing temporary credentials for '{profile_name}' as [default]...[/blue]")
    result = write_default_credentials(profile_name)
    if result:
        console.print("[green]✓ Credentials written to ~/.aws/credentials as [default][/green]")
        if result.get("expiration"):
            console.print(f"[dim]  Expires: {result['expiration']}[/dim]")
    else:
        console.print("[yellow]⚠ Could not write credentials to ~/.aws/credentials — AWS_PROFILE is still set[/yellow]")


def set_default_profile(profile_name=None):
    """Set default AWS profile by exporting AWS_PROFILE environment variable.

    Args:
      profile_name: Name of the profile to set as default
    """
    profiles = list_aws_profiles()
    if not profiles:
        console.print("[yellow]No AWS profiles found[/yellow]")
        sys.exit(1)

    profile_name = _resolve_and_validate_profile(profile_name, profiles)

    # Validate that the selected profile has valid, non-expired credentials before proceeding
    available, err_msg = check_profile_credentials_available(profile_name)
    if not available:
        console.print(f"[red]✗ Credentials for '{profile_name}' are not available or have expired.[/red]")
        if err_msg:
            console.print(f"[dim]  {err_msg}[/dim]")
        console.print("[dim]  Run 'devo aws-login' to refresh them first.[/dim]")
        sys.exit(1)

    # Set in current process (won't affect parent shell, but shows intent)
    os.environ["AWS_PROFILE"] = profile_name

    # Detect if running in Git Bash on Windows
    is_git_bash = os.name == "nt" and os.environ.get("SHELL", "").endswith("bash")

    if os.name == "nt" and not is_git_bash:
        _set_windows_profile(profile_name)
    else:
        _set_unix_profile(profile_name)

    # Common instructions for all platforms
    console.print("\n[cyan]You can now use AWS CLI without --profile:[/cyan]")
    console.print("  aws s3 ls")
    console.print("  aws sts get-caller-identity")

    _write_default_credentials(profile_name)
