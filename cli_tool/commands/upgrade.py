import os
import platform
import shutil
import sys
import tarfile
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
    elif system == "darwin":
        # macOS uses tarball (onedir mode)
        return f"devo-{system}-{arch}.tar.gz"
    else:
        # Linux uses single binary (onefile mode)
        return f"devo-{system}-{arch}"


def get_executable_path():
    """Get path of current executable"""
    # Check if running as PyInstaller bundle
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable)
        system = platform.system().lower()
        
        # Windows/macOS onedir: return the parent directory
        if system in ["windows", "darwin"] and exe_path.name in ["devo.exe", "devo"]:
            return exe_path.parent
        # Linux onefile: return the executable itself
        return exe_path

    # Running as Python script - find devo in PATH
    devo_path = shutil.which("devo")
    if devo_path:
        return Path(devo_path)

    return None


def verify_binary(binary_path, is_archive=False, archive_type=None):
    """Verify downloaded binary is valid"""
    try:
        # For archive files (ZIP/tarball), verify format
        if is_archive:
            if archive_type == "zip":
                if not zipfile.is_zipfile(binary_path):
                    click.echo("Error: Downloaded file is not a valid ZIP archive")
                    return False
                # Check ZIP contains devo directory with devo.exe
                with zipfile.ZipFile(binary_path, "r") as zf:
                    names = [name.replace("\\", "/") for name in zf.namelist()]
                    if not any("devo.exe" in name for name in names):
                        click.echo("Error: ZIP does not contain devo.exe")
                        return False
            elif archive_type == "tar.gz":
                import tarfile
                if not tarfile.is_tarfile(binary_path):
                    click.echo("Error: Downloaded file is not a valid tar.gz archive")
                    return False
                # Check tarball contains devo directory with devo executable
                with tarfile.open(binary_path, "r:gz") as tf:
                    names = tf.getnames()
                    if not any("devo/devo" in name or name.endswith("/devo") for name in names):
                        click.echo("Error: tar.gz does not contain devo executable")
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


def replace_binary(new_binary_path, target_path, archive_type=None):
    """Replace current binary with new one"""
    try:
        system = platform.system().lower()
        
        # Handle archive extraction (Windows ZIP or macOS tarball)
        if archive_type:
            # Create backup of entire directory
            backup_path = target_path.parent / f"{target_path.name}.backup"
            if backup_path.exists():
                try:
                    shutil.rmtree(backup_path)
                except OSError as e:
                    click.echo(f"Warning: Could not remove old backup: {e}", err=True)

            shutil.copytree(str(target_path), str(backup_path))
            click.echo(f"Backup created: {backup_path}")

            # Extract archive to temporary location
            temp_extract = target_path.parent / "devo_new"
            if temp_extract.exists():
                try:
                    shutil.rmtree(temp_extract)
                except OSError as e:
                    click.echo(f"Warning: Could not remove old temp directory: {e}", err=True)
            temp_extract.mkdir()

            try:
                # Extract based on archive type
                if archive_type == "zip":
                    with zipfile.ZipFile(new_binary_path, "r") as zf:
                        zf.extractall(temp_extract)
                elif archive_type == "tar.gz":
                    with tarfile.open(new_binary_path, "r:gz") as tf:
                        tf.extractall(temp_extract)

                # Find the extracted devo directory
                extracted_dir = None
                for item in temp_extract.iterdir():
                    if item.is_dir() and item.name.startswith("devo"):
                        extracted_dir = item
                        break

                if extracted_dir is None:
                    # Archive contains files at the root
                    extracted_dir = temp_extract

                if system == "windows":
                    # Windows: Use PowerShell script for replacement after exit
                    script_path = target_path.parent / "upgrade_devo.ps1"
                    script_content = f"""
# Wait for current process to exit
$processId = {os.getpid()}
Write-Host "Waiting for process $processId to exit..."
Wait-Process -Id $processId -ErrorAction SilentlyContinue

# Give it a moment
Start-Sleep -Seconds 2

# Remove old installation
Write-Host "Removing old installation..."
if (Test-Path "{target_path}") {{
    Remove-Item -Path "{target_path}" -Recurse -Force -ErrorAction Stop
}}

# Move new installation into place
Write-Host "Installing new version..."
Move-Item -Path "{extracted_dir}" -Destination "{target_path}" -Force -ErrorAction Stop

# Clean up
Write-Host "Cleaning up..."
if (Test-Path "{temp_extract}") {{
    Remove-Item -Path "{temp_extract}" -Recurse -Force -ErrorAction SilentlyContinue
}}
Remove-Item -Path "{script_path}" -Force -ErrorAction SilentlyContinue

Write-Host "Upgrade complete!"
Write-Host "You can now run: devo --version"
"""

                    with open(script_path, "w", encoding="utf-8") as f:
                        f.write(script_content)

                    click.echo("\n✨ Upgrade prepared successfully!")
                    click.echo("\nThe upgrade will complete after this process exits.")
                    click.echo("Starting upgrade script...")

                    # Start the PowerShell script in a new window
                    import subprocess

                    subprocess.Popen(
                        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", str(script_path)],
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                    )

                    return True
                else:
                    # macOS: Direct replacement (can replace while running)
                    # Remove old directory
                    shutil.rmtree(target_path)
                    
                    # Move new directory into place
                    shutil.move(str(extracted_dir), str(target_path))
                    
                    # Make executable
                    exe_file = target_path / "devo"
                    os.chmod(exe_file, 0o755)
                    
                    # Clean up temp directory
                    if temp_extract.exists():
                        try:
                            shutil.rmtree(temp_extract)
                        except OSError:
                            pass
                    
                    click.echo(f"\nBackup location: {backup_path}")
                    click.echo("\nTo restore backup if needed:")
                    click.echo(f"  rm -rf {target_path}")
                    click.echo(f"  mv {backup_path} {target_path}")
                    
                    return True

            except Exception as e:
                click.echo(f"Error preparing upgrade: {e}", err=True)
                # Clean up temp directory
                if temp_extract.exists():
                    try:
                        shutil.rmtree(temp_extract)
                    except OSError:
                        pass
                return False

        # Linux: single binary replacement (onefile mode)
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
