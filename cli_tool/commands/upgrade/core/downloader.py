"""Binary download and verification."""

import sys
import tarfile
import zipfile

import click
import requests


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
