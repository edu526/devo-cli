"""Binary installation and replacement."""

import os
import platform
import shutil
import subprocess
import tarfile
import zipfile

import click


def _extract_archive(new_binary_path, archive_type: str, temp_extract):
    """Extract archive to temp_extract directory."""
    if archive_type == "zip":
        with zipfile.ZipFile(new_binary_path, "r") as zf:
            zf.extractall(temp_extract)
    elif archive_type == "tar.gz":
        with tarfile.open(new_binary_path, "r:gz") as tf:
            tf.extractall(temp_extract, filter="data")


def _find_extracted_dir(temp_extract):
    """Return the extracted devo directory, or temp_extract itself if no subdir found."""
    for item in temp_extract.iterdir():
        if item.is_dir() and item.name.startswith("devo"):
            return item
    return temp_extract


def _replace_windows_archive(extracted_dir, target_path, temp_extract, os_pid: int) -> bool:
    """Schedule Windows replacement via a PowerShell script after process exit."""
    script_path = target_path.parent / "upgrade_devo.ps1"
    script_content = f"""
# Wait for current process to exit
$processId = {os_pid}
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

    subprocess.Popen(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", str(script_path)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    return True


def _replace_unix_archive(extracted_dir, target_path, backup_path, temp_extract) -> bool:
    """Replace macOS/Linux directory-based binary in-place."""
    shutil.rmtree(target_path)
    shutil.move(str(extracted_dir), str(target_path))

    exe_file = target_path / "devo"
    os.chmod(exe_file, 0o755)

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


def _prepare_archive_backup(target_path) -> tuple:
    """Create a backup of the target directory and return (backup_path,).

    Removes any existing backup before copying.
    """
    backup_path = target_path.parent / f"{target_path.name}.backup"
    if backup_path.exists():
        try:
            shutil.rmtree(backup_path)
        except OSError as e:
            click.echo(f"Warning: Could not remove old backup: {e}", err=True)

    shutil.copytree(str(target_path), str(backup_path))
    click.echo(f"Backup created: {backup_path}")
    return backup_path


def _prepare_temp_extract_dir(target_path):
    """Create (or recreate) the temporary extraction directory. Returns the path."""
    temp_extract = target_path.parent / "devo_new"
    if temp_extract.exists():
        try:
            shutil.rmtree(temp_extract)
        except OSError as e:
            click.echo(f"Warning: Could not remove old temp directory: {e}", err=True)
    temp_extract.mkdir()
    return temp_extract


def _cleanup_temp_extract(temp_extract) -> None:
    """Remove the temporary extraction directory if it exists."""
    if temp_extract.exists():
        try:
            shutil.rmtree(temp_extract)
        except OSError:
            pass


def _replace_archive_binary(new_binary_path, target_path, archive_type: str, system: str) -> bool:
    """Handle the archive-based binary replacement (macOS / Windows)."""
    backup_path = _prepare_archive_backup(target_path)
    temp_extract = _prepare_temp_extract_dir(target_path)

    try:
        _extract_archive(new_binary_path, archive_type, temp_extract)
        extracted_dir = _find_extracted_dir(temp_extract)

        if system == "windows":
            return _replace_windows_archive(extracted_dir, target_path, temp_extract, os.getpid())
        return _replace_unix_archive(extracted_dir, target_path, backup_path, temp_extract)

    except Exception as e:
        click.echo(f"Error preparing upgrade: {e}", err=True)
        _cleanup_temp_extract(temp_extract)
        return False


def _replace_linux_binary(new_binary_path, target_path) -> bool:
    """Handle Linux single-file binary replacement (onefile mode)."""
    os.chmod(new_binary_path, 0o755)

    backup_path = target_path.with_suffix(".backup")
    if backup_path.exists():
        backup_path.unlink()

    shutil.copy2(str(target_path), str(backup_path))
    click.echo(f"Backup created: {backup_path}")

    shutil.move(str(new_binary_path), str(target_path))

    click.echo("\nTo restore backup if needed:")
    click.echo(f"  mv {backup_path} {target_path}")
    return True


def replace_binary(new_binary_path, target_path, archive_type=None):
    """Replace current binary with new one"""
    try:
        system = platform.system().lower()

        if archive_type:
            return _replace_archive_binary(new_binary_path, target_path, archive_type, system)

        return _replace_linux_binary(new_binary_path, target_path)
    except Exception as e:
        click.echo(f"Error replacing binary: {str(e)}", err=True)
        return False
