"""Upgrade command implementation."""

import os
import sys
import tempfile
from pathlib import Path

import click

from cli_tool.commands.upgrade.core.downloader import download_binary, verify_binary
from cli_tool.commands.upgrade.core.installer import replace_binary
from cli_tool.commands.upgrade.core.platform import detect_platform, get_binary_name, get_executable_path
from cli_tool.commands.upgrade.core.version import get_current_version, get_latest_release


def _determine_archive_suffix(system: str) -> str:
    """Return the archive file suffix for the given platform."""
    if system == "windows":
        return ".zip"
    if system == "darwin":
        return ".tar.gz"
    return ".tmp"


def _download_and_verify(asset_url: str, archive_type) -> Path:
    """Download binary to a temp file, verify it, and return the path. Exits on failure."""
    suffix = _determine_archive_suffix("windows" if archive_type == "zip" else ("darwin" if archive_type == "tar.gz" else "linux"))

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_path = Path(tmp_file.name)

    if not download_binary(asset_url, tmp_path):
        sys.exit(1)

    click.echo("\nVerifying downloaded binary...")
    if not verify_binary(tmp_path, is_archive=bool(archive_type), archive_type=archive_type):
        click.echo("Error: Downloaded binary failed verification", err=True)
        click.echo("The file may be corrupted. Please try again.", err=True)
        sys.exit(1)

    return tmp_path


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
        click.echo("Checking for updates...")

        current_version = get_current_version()
        if current_version == "unknown":
            click.echo("Warning: Could not determine current version", err=True)

        release_info = get_latest_release()
        if not release_info:
            click.echo("Error: Could not fetch latest release information", err=True)
            sys.exit(1)

        latest_version = release_info.get("tag_name", "").lstrip("v")
        if not latest_version:
            click.echo("Error: Could not determine latest version", err=True)
            sys.exit(1)

        if current_version != "unknown" and current_version == latest_version:
            click.echo(f"✨ You already have the latest version ({current_version})")
            if not force and not check:
                click.echo("Use --force to reinstall anyway")
                return
            elif check:
                return

        click.echo(f"Current version: {current_version}")
        click.echo(f"Latest version: {latest_version}")

        if check:
            click.echo(click.style("\n→ Update available - Run 'devo upgrade' to update", dim=True))
            return

        platform_info = detect_platform()
        if not platform_info:
            click.echo("Error: Unsupported platform", err=True)
            sys.exit(1)

        system, arch = platform_info
        binary_name = get_binary_name(system, arch)

        archive_type = None
        if system == "windows":
            archive_type = "zip"
        elif system == "darwin":
            archive_type = "tar.gz"

        asset_url = None
        for asset in release_info.get("assets", []):
            if asset["name"] == binary_name:
                asset_url = asset["browser_download_url"]
                break

        if not asset_url:
            click.echo(f"Error: Binary not found for {system}-{arch}", err=True)
            click.echo(f"Looking for: {binary_name}", err=True)
            sys.exit(1)

        current_exe = get_executable_path()
        if not current_exe:
            click.echo("Error: Could not determine current executable location", err=True)
            click.echo("Please install manually from GitHub Releases", err=True)
            sys.exit(1)

        click.echo(f"Binary location: {current_exe}")

        if not os.access(current_exe.parent, os.W_OK):
            click.echo(f"Error: No write permission to {current_exe.parent}", err=True)
            click.echo("Try running with sudo or install to a user-writable location", err=True)
            sys.exit(1)

        if not force:
            if not click.confirm("Do you want to continue with the upgrade?"):
                click.echo("Upgrade cancelled")
                return

        click.echo(f"\nDownloading {binary_name}...")
        tmp_path = _download_and_verify(asset_url, archive_type)

        try:
            click.echo("\nInstalling new version...")
            if not replace_binary(tmp_path, current_exe, archive_type=archive_type):
                sys.exit(1)

            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

            click.echo(f"\n✨ Successfully upgraded to version {latest_version}!")
            click.echo("\nVerify the upgrade:")
            click.echo("  devo --version")
            click.echo("\n💡 Tip: Run 'devo completion --install' to set up shell completion")

            # os._exit is intentional here: prevents old binary process from accessing the new binary
            os._exit(0)  # noqa: S112

        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    except KeyboardInterrupt:
        click.echo("\n\nUpgrade cancelled by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nError during upgrade: {str(e)}", err=True)
        sys.exit(1)
