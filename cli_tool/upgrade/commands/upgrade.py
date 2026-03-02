"""Upgrade command implementation."""

import os
import sys
import tempfile
from pathlib import Path

import click

from cli_tool.upgrade.core.downloader import download_binary, verify_binary
from cli_tool.upgrade.core.installer import replace_binary
from cli_tool.upgrade.core.platform import detect_platform, get_binary_name, get_executable_path
from cli_tool.upgrade.core.version import get_current_version, get_latest_release


@click.command()
@click.option("--force", "-f", is_flag=True, help="Force upgrade without confirmation")
@click.option("--check", "-c", is_flag=True, help="Check for updates without upgrading")
def upgrade(force, check):
    """Upgrade the CLI tool to the latest version from GitHub Releases"""
    # Disable version check for upgrade command
    os.environ["DEVO_SKIP_VERSION_CHECK"] = "1"

    # Clear cache when checking to force fresh check
    if check:
        from cli_tool.utils.version_check import clear_cache

        clear_cache()

    try:
        click.echo("Checking for updates...")

        # Get current version
        current_version = get_current_version()
        if current_version == "unknown":
            click.echo("Warning: Could not determine current version", err=True)

        # Get latest release
        release_info = get_latest_release()
        if not release_info:
            click.echo("Error: Could not fetch latest release information", err=True)
            sys.exit(1)

        latest_version = release_info.get("tag_name", "").lstrip("v")
        if not latest_version:
            click.echo("Error: Could not determine latest version", err=True)
            sys.exit(1)

        # Compare versions
        if current_version != "unknown" and current_version == latest_version:
            click.echo(f"✨ You already have the latest version ({current_version})")
            if not force and not check:
                click.echo("Use --force to reinstall anyway")
                return
            elif check:
                return

        click.echo(f"Current version: {current_version}")
        click.echo(f"Latest version: {latest_version}")

        # If only checking, stop here
        if check:
            click.echo(click.style("\n→ Update available - Run 'devo upgrade' to update", dim=True))
            return

        # Detect platform
        platform_info = detect_platform()
        if not platform_info:
            click.echo("Error: Unsupported platform", err=True)
            sys.exit(1)

        system, arch = platform_info
        binary_name = get_binary_name(system, arch)

        # Determine archive type
        archive_type = None
        if system == "windows":
            archive_type = "zip"
        elif system == "darwin":
            archive_type = "tar.gz"
        # Linux uses single binary (no archive)

        # Find binary in release assets
        asset_url = None
        for asset in release_info.get("assets", []):
            if asset["name"] == binary_name:
                asset_url = asset["browser_download_url"]
                break

        if not asset_url:
            click.echo(f"Error: Binary not found for {system}-{arch}", err=True)
            click.echo(f"Looking for: {binary_name}", err=True)
            sys.exit(1)

        # Get current executable path
        current_exe = get_executable_path()
        if not current_exe:
            click.echo("Error: Could not determine current executable location", err=True)
            click.echo("Please install manually from GitHub Releases", err=True)
            sys.exit(1)

        click.echo(f"Binary location: {current_exe}")

        # Check write permissions
        check_path = current_exe.parent
        if not os.access(check_path, os.W_OK):
            click.echo(f"Error: No write permission to {check_path}", err=True)
            click.echo("Try running with sudo or install to a user-writable location", err=True)
            sys.exit(1)

        if not force:
            if not click.confirm("Do you want to continue with the upgrade?"):
                click.echo("Upgrade cancelled")
                return

        # Download new binary to temporary file
        click.echo(f"\nDownloading {binary_name}...")
        if archive_type == "zip":
            suffix = ".zip"
        elif archive_type == "tar.gz":
            suffix = ".tar.gz"
        else:
            suffix = ".tmp"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            if not download_binary(asset_url, tmp_path):
                sys.exit(1)

            # Verify downloaded binary
            click.echo("\nVerifying downloaded binary...")
            if not verify_binary(tmp_path, is_archive=bool(archive_type), archive_type=archive_type):
                click.echo("Error: Downloaded binary failed verification", err=True)
                click.echo("The file may be corrupted. Please try again.", err=True)
                sys.exit(1)

            # Replace binary
            click.echo("\nInstalling new version...")
            if not replace_binary(tmp_path, current_exe, archive_type=archive_type):
                sys.exit(1)

            # Clean up temp file immediately after successful replacement
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass  # Ignore cleanup errors

            click.echo(f"\n✨ Successfully upgraded to version {latest_version}!")
            click.echo("\nVerify the upgrade:")
            click.echo("  devo --version")
            click.echo("\n💡 Tip: Run 'devo completion --install' to set up shell completion")

            # Use os._exit to terminate immediately without cleanup handlers
            # This prevents the old binary process from trying to access the new binary
            os._exit(0)

        finally:
            # Cleanup for error cases only
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
