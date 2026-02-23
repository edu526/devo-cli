import os
import platform
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import click
import requests


def get_current_version():
    """Get current installed version"""
    try:
        from cli_tool._version import __version__

        return __version__
    except ImportError:
        return "unknown"


def get_latest_release():
    """Get latest release info from GitHub"""
    try:
        from cli_tool.config import GITHUB_API_RELEASES_URL

        response = requests.get(GITHUB_API_RELEASES_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        click.echo(f"Error fetching latest release: {str(e)}", err=True)
        return None


def detect_platform():
    """Detect current platform and architecture"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Map system names
    if system == "darwin":
        system = "darwin"
    elif system == "linux":
        system = "linux"
    elif system == "windows":
        system = "windows"
    else:
        return None

    # Map architecture names
    if machine in ["x86_64", "amd64"]:
        arch = "amd64"
    elif machine in ["arm64", "aarch64"]:
        arch = "arm64"
    else:
        return None

    return system, arch


def get_binary_name(system, arch):
    """Get binary name for platform"""
    if system == "windows":
        return f"devo-{system}-{arch}.zip"
    return f"devo-{system}-{arch}"


def get_executable_path():
    """Get path of current executable"""
    # Check if running as PyInstaller bundle
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable)
        # For Windows onedir, return the parent directory
        if platform.system().lower() == "windows" and exe_path.name == "devo.exe":
            return exe_path.parent
        return exe_path

    # Running as Python script - find devo in PATH
    devo_path = shutil.which("devo")
    if devo_path:
        return Path(devo_path)

    return None


def verify_binary(binary_path, is_windows_zip=False):
    """Verify downloaded binary is valid"""
    try:
        # For Windows ZIP files, verify it's a valid ZIP
        if is_windows_zip:
            if not zipfile.is_zipfile(binary_path):
                click.echo("Error: Downloaded file is not a valid ZIP archive")
                return False
            # Check ZIP contains devo directory with devo.exe
            with zipfile.ZipFile(binary_path, "r") as zf:
                names = [name.replace("\\", "/") for name in zf.namelist()]
                if not any("devo.exe" in name for name in names):
                    click.echo("Error: ZIP does not contain devo.exe")
                    return False
            return True

        # Check file size (should be at least 10MB for PyInstaller binary)
        file_size = binary_path.stat().st_size
        if file_size < 10 * 1024 * 1024:  # 10MB
            click.echo(f"Warning: Binary size is only {file_size / 1024 / 1024:.1f}MB, seems too small")
            return False

        # Check if file is executable format (basic check)
        with open(binary_path, "rb") as f:
            magic = f.read(4)
            # ELF magic for Linux: 7f 45 4c 46
            # Mach-O magic for macOS: cf fa ed fe or fe ed fa ce (and others)
            # PE magic for Windows: 4d 5a (MZ)
            if sys.platform.startswith("linux") and magic[:4] != b"\x7fELF":
                click.echo("Error: Downloaded file is not a valid Linux ELF binary")
                return False
            elif sys.platform == "darwin" and magic[:4] not in [
                b"\xcf\xfa\xed\xfe",
                b"\xfe\xed\xfa\xce",
                b"\xce\xfa\xed\xfe",
                b"\xfe\xed\xfa\xcf",
            ]:
                click.echo("Error: Downloaded file is not a valid macOS binary")
                return False
            elif sys.platform == "win32" and magic[:2] != b"MZ":
                click.echo("Error: Downloaded file is not a valid Windows PE binary")
                return False

        return True
    except Exception as e:
        click.echo(f"Error verifying binary: {str(e)}")
        return False


def download_binary(url, dest_path):
    """Download binary from URL with progress"""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192
        downloaded = 0

        with open(dest_path, "wb") as f:
            with click.progressbar(length=total_size, label="Downloading", show_percent=True, show_pos=True) as bar:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        bar.update(len(chunk))

        return True
    except Exception as e:
        click.echo(f"\nError downloading binary: {str(e)}", err=True)
        return False


def replace_binary(new_binary_path, target_path, is_windows_zip=False):
    """Replace current binary with new one"""
    try:
        # Windows onedir: target_path is the directory, extract ZIP
        if is_windows_zip:
            # Create backup of entire directory
            backup_path = target_path.parent / f"{target_path.name}.backup"
            if backup_path.exists():
                try:
                    shutil.rmtree(backup_path)
                except OSError as e:
                    click.echo(f"Warning: Could not remove old backup: {e}", err=True)

            shutil.copytree(str(target_path), str(backup_path))
            click.echo(f"Backup created: {backup_path}")

            # Extract ZIP to temporary location
            temp_extract = target_path.parent / "devo_temp"
            if temp_extract.exists():
                try:
                    shutil.rmtree(temp_extract)
                except OSError as e:
                    click.echo(f"Warning: Could not remove old temp directory: {e}", err=True)
            temp_extract.mkdir()

            # Path for moving old installation out of the way
            old_path = target_path.parent / f"{target_path.name}.old"

            def restore_from_backup():
                """Attempt to restore the previous installation from .old or backup."""
                click.echo("Attempting to restore from backup...")
                try:
                    if temp_extract.exists():
                        shutil.rmtree(temp_extract)
                    if old_path.exists():
                        if target_path.exists():
                            shutil.rmtree(target_path)
                        shutil.move(str(old_path), str(target_path))
                        click.echo("Restored installation from .old directory.")
                    elif backup_path.exists():
                        if target_path.exists():
                            shutil.rmtree(target_path)
                        shutil.copytree(str(backup_path), str(target_path))
                        click.echo("Restored installation from backup directory.")
                    else:
                        click.echo("No .old or backup directory found to restore from.")
                except Exception as restore_exc:
                    click.echo(f"Error while restoring from backup: {restore_exc}")

            try:
                with zipfile.ZipFile(new_binary_path, "r") as zf:
                    zf.extractall(temp_extract)

                # Find the extracted devo directory (nested ZIP structure)
                extracted_dir = None
                for item in temp_extract.iterdir():
                    if item.is_dir() and item.name.startswith("devo"):
                        extracted_dir = item
                        break

                # Move old directory out of the way
                if old_path.exists():
                    shutil.rmtree(old_path)
                shutil.move(str(target_path), str(old_path))

                # Move new directory into place (handles both flat and nested ZIP)
                try:
                    if extracted_dir is not None:
                        # ZIP contains a top-level devo* directory; move it into place
                        shutil.move(str(extracted_dir), str(target_path))
                    else:
                        # ZIP contains files at the root; move all extracted items into target_path
                        target_path.mkdir()
                        for item in temp_extract.iterdir():
                            shutil.move(str(item), str(target_path / item.name))
                except PermissionError as exc:
                    click.echo(
                        "Failed to replace the installation directory. " "This can happen if the CLI is currently running from that location.",
                        err=True,
                    )
                    if platform.system() == "Windows":
                        click.echo(
                            "On Windows, please close this terminal (and any other "
                            "instances of cli_tool) and run the upgrade again from a new terminal.",
                            err=True,
                        )
                    else:
                        click.echo(
                            "Please ensure no running processes are using the cli_tool binary " "and try the upgrade again.",
                            err=True,
                        )
                    click.echo(f"Underlying error: {exc}", err=True)
                    restore_from_backup()
                    raise click.ClickException("Upgrade failed while replacing the installation directory.")

                # Clean up temp directory
                try:
                    shutil.rmtree(temp_extract)
                except OSError:
                    pass  # Ignore cleanup errors

                # Clean up old directory
                try:
                    if old_path.exists():
                        shutil.rmtree(old_path)
                except OSError:
                    pass  # Ignore cleanup errors

                click.echo("\nTo restore backup if needed:")
                if platform.system() == "Windows":
                    click.echo(f"  rmdir /s /q {target_path}")
                    click.echo(f"  move {backup_path} {target_path}")
                else:
                    click.echo(f"  rm -rf {target_path}")
                    click.echo(f"  mv {backup_path} {target_path}")

                return True

            except click.ClickException:
                raise
            except Exception as e:
                click.echo(f"Upgrade failed: {e}")
                restore_from_backup()
                return False

        # Unix single binary
        # Make new binary executable
        os.chmod(new_binary_path, 0o755)

        # Always create a backup
        backup_path = target_path.with_suffix(".backup")
        if backup_path.exists():
            backup_path.unlink()

        # Copy current binary to backup
        shutil.copy2(str(target_path), str(backup_path))
        click.echo(f"Backup created: {backup_path}")

        # Replace the file directly
        shutil.move(str(new_binary_path), str(target_path))

        click.echo("\nTo restore backup if needed:")
        click.echo(f"  mv {backup_path} {target_path}")

        return True
    except Exception as e:
        click.echo(f"Error replacing binary: {str(e)}", err=True)
        return False


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
            click.echo("\n✨ New version available!")
            click.echo("Run 'devo upgrade' to update")
            return

        # Detect platform
        platform_info = detect_platform()
        if not platform_info:
            click.echo("Error: Unsupported platform", err=True)
            sys.exit(1)

        system, arch = platform_info
        binary_name = get_binary_name(system, arch)
        is_windows_zip = system == "windows"

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
        suffix = ".zip" if is_windows_zip else ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            if not download_binary(asset_url, tmp_path):
                sys.exit(1)

            # Verify downloaded binary
            click.echo("\nVerifying downloaded binary...")
            if not verify_binary(tmp_path, is_windows_zip=is_windows_zip):
                click.echo("Error: Downloaded binary failed verification", err=True)
                click.echo("The file may be corrupted. Please try again.", err=True)
                sys.exit(1)

            # Replace binary
            click.echo("\nInstalling new version...")
            if not replace_binary(tmp_path, current_exe, is_windows_zip=is_windows_zip):
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
