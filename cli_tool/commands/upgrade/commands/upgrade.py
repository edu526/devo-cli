"""Upgrade command implementation."""

import os
import sys
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from cli_tool.commands.upgrade.core.downloader import download_binary, verify_binary
from cli_tool.commands.upgrade.core.installer import replace_binary
from cli_tool.commands.upgrade.core.platform import detect_platform, get_binary_name, get_executable_path
from cli_tool.commands.upgrade.core.version import get_current_version, get_latest_release
from cli_tool.core.ui import theme
from cli_tool.core.ui.brand import spinner

_console = Console()


def _determine_archive_suffix(system: str) -> str:
    """Return the archive file suffix for the given platform."""
    if system == "windows":
        return ".zip"
    if system == "darwin":
        return ".tar.gz"
    return ".tmp"


def _download_and_verify(asset_url: str, archive_type) -> Path:
    """Download binary to a temp file, verify it, and return the path. Exits on failure."""
    if archive_type == "zip":
        platform = "windows"
    elif archive_type == "tar.gz":
        platform = "darwin"
    else:
        platform = "linux"
    suffix = _determine_archive_suffix(platform)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_path = Path(tmp_file.name)

    if not download_binary(asset_url, tmp_path):
        sys.exit(1)

    with spinner("Verifying binary..."):
        verified = verify_binary(tmp_path, is_archive=bool(archive_type), archive_type=archive_type)

    if not verified:
        _console.print("[red]Error:[/red] Downloaded binary failed verification")
        _console.print("[dim]The file may be corrupted. Please try again.[/dim]")
        sys.exit(1)

    return tmp_path


def _get_archive_type(system: str) -> str:
    """Return the archive type string for the given platform system."""
    if system == "windows":
        return "zip"
    if system == "darwin":
        return "tar.gz"
    return None


def _resolve_latest_version(release_info: dict) -> str:
    """Extract and validate the latest version tag from release_info. Exits on failure."""
    latest_version = release_info.get("tag_name", "").lstrip("v")
    if not latest_version:
        _console.print("[red]Error:[/red] Could not determine latest version")
        sys.exit(1)
    return latest_version


def _handle_up_to_date(current_version: str, latest_version: str, force: bool, check: bool) -> bool:
    """Print up-to-date message and return True if upgrade should be skipped."""
    if current_version != "unknown" and current_version == latest_version:
        _console.print(f"[green]✨[/green] Already on the latest version [cyan]v{current_version}[/cyan]")
        if check:
            return True
        if not force:
            _console.print("[dim]Use --force to reinstall anyway[/dim]")
            return True
    return False


def _resolve_asset_url(release_info: dict, binary_name: str, system: str, arch: str) -> str:
    """Find download URL for the named binary asset. Exits if not found."""
    for asset in release_info.get("assets", []):
        if asset["name"] == binary_name:
            return asset["browser_download_url"]

    _console.print(f"[red]Error:[/red] Binary not found for {system}-{arch}")
    _console.print(f"[dim]Looking for: {binary_name}[/dim]")
    sys.exit(1)


def _validate_executable_path(current_exe):
    """Validate that the current executable location is writable. Exits on failure."""
    if not current_exe:
        _console.print("[red]Error:[/red] Could not determine current executable location")
        _console.print("[dim]Please install manually from GitHub Releases[/dim]")
        sys.exit(1)

    _console.print(f"[dim]Binary location:[/dim] {current_exe}")

    if not os.access(current_exe.parent, os.W_OK):
        _console.print(f"[red]Error:[/red] No write permission to {current_exe.parent}")
        _console.print("[dim]Try running with sudo or install to a user-writable location[/dim]")
        sys.exit(1)


def _install_and_cleanup(tmp_path: Path, current_exe: Path, archive_type, latest_version: str) -> None:
    """Install the new binary, clean up the temp file, and exit the process."""
    try:
        _console.print("\n[cyan]Installing new version...[/cyan]")
        if not replace_binary(tmp_path, current_exe, archive_type=archive_type):
            sys.exit(1)

        _cleanup_tmp(tmp_path)

        _console.print(
            Panel(
                f"[bold cyan]v{latest_version}[/bold cyan] installed successfully\n\n"
                f"[dim]Verify:[/dim]  [cyan]devo --version[/cyan]\n"
                f"[dim]Tip:[/dim]     [cyan]devo autocomplete[/cyan]  to set up shell completion",
                title="[green]Upgrade complete[/green]",
                border_style=theme.BORDER_SUCCESS,
                padding=(0, 2),
            )
        )

        # os._exit is intentional here: prevents old binary process from accessing the new binary
        os._exit(0)  # noqa: S112

    finally:
        _cleanup_tmp(tmp_path)


def _cleanup_tmp(tmp_path: Path) -> None:
    """Silently remove a temporary file if it exists."""
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except Exception:
            pass


def _check_version_status(check: bool) -> tuple:
    """Fetch current and latest version info.

    Returns (current_version, release_info, latest_version) or calls sys.exit on failure.
    """
    current_version = get_current_version()
    if current_version == "unknown":
        _console.print("[yellow]Warning:[/yellow] Could not determine current version")

    release_info = get_latest_release()
    if not release_info:
        _console.print("[red]Error:[/red] Could not fetch latest release information")
        sys.exit(1)

    latest_version = _resolve_latest_version(release_info)
    return current_version, release_info, latest_version


def _perform_upgrade(release_info: dict, force: bool) -> None:
    """Resolve platform info, download and install the new binary."""
    platform_info = detect_platform()
    if not platform_info:
        _console.print("[red]Error:[/red] Unsupported platform")
        sys.exit(1)

    system, arch = platform_info
    binary_name = get_binary_name(system, arch)
    archive_type = _get_archive_type(system)

    asset_url = _resolve_asset_url(release_info, binary_name, system, arch)

    current_exe = get_executable_path()
    _validate_executable_path(current_exe)

    if not force:
        if not click.confirm("\nDo you want to continue with the upgrade?"):
            _console.print("[dim]Upgrade cancelled[/dim]")
            return

    tmp_path = _download_and_verify(asset_url, archive_type)

    latest_version = release_info.get("tag_name", "").lstrip("v")
    _install_and_cleanup(tmp_path, current_exe, archive_type, latest_version)


@click.command()
@click.option("--force", "-f", is_flag=True, help="Force upgrade without confirmation")
@click.option("--check", "-c", is_flag=True, help="Check for updates without upgrading")
def upgrade(force, check):
    """Upgrade the CLI tool to the latest version."""
    # Disable version check for upgrade command
    os.environ["DEVO_SKIP_VERSION_CHECK"] = "1"

    # Clear cache when checking to force fresh check
    if check:
        from cli_tool.core.utils.version_check import clear_cache

        clear_cache()

    try:
        with spinner("Checking for updates..."):
            current_version, release_info, latest_version = _check_version_status(check)

        if _handle_up_to_date(current_version, latest_version, force, check):
            return

        if check:
            _console.print(
                Panel(
                    f"[cyan]devo upgrade[/cyan]  →  [bold cyan]v{latest_version}[/bold cyan] available" f"  [dim](current: v{current_version})[/dim]",
                    title="[yellow]Update available[/yellow]",
                    border_style=theme.BORDER_WARNING,
                    padding=(0, 2),
                )
            )
            return

        _console.print(
            Panel(
                f"[dim]Current:[/dim]  [cyan]v{current_version}[/cyan]\n" f"[dim]Latest:[/dim]   [bold cyan]v{latest_version}[/bold cyan]",
                border_style=theme.BORDER_BRAND,
                padding=(0, 2),
            )
        )

        _perform_upgrade(release_info, force)

    except KeyboardInterrupt:
        _console.print("\n[dim]Upgrade cancelled by user[/dim]")
        sys.exit(1)
    except Exception as e:
        _console.print(f"\n[red]Error during upgrade:[/red] {str(e)}")
        sys.exit(1)
