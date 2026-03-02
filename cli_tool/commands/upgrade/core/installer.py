"""Binary installation and replacement."""

import os
import platform
import shutil
import subprocess
import tarfile
import zipfile

import click


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
                        tf.extractall(temp_extract, filter="data")

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
