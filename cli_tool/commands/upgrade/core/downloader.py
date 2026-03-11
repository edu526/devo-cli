"""Binary download and verification."""

import sys
import tarfile
import zipfile
from pathlib import Path

import click
import requests

_MACOS_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"}


def _verify_zip(binary_path) -> bool:
    """Verify a ZIP archive contains devo.exe."""
    if not zipfile.is_zipfile(binary_path):
        click.echo("Error: Downloaded file is not a valid ZIP archive")
        return False
    with zipfile.ZipFile(binary_path, "r") as zf:
        names = [name.replace("\\", "/") for name in zf.namelist()]
        if not any("devo.exe" in name for name in names):
            click.echo("Error: ZIP does not contain devo.exe")
            return False
    return True


def _verify_targz(binary_path) -> bool:
    """Verify a tar.gz archive contains the devo executable."""
    if not tarfile.is_tarfile(binary_path):
        click.echo("Error: Downloaded file is not a valid tar.gz archive")
        return False
    with tarfile.open(binary_path, "r:gz") as tf:
        names = tf.getnames()
        if not any("devo/devo" in name or name.endswith("/devo") for name in names):
            click.echo("Error: tar.gz does not contain devo executable")
            return False
    return True


def _verify_archive(binary_path, archive_type: str) -> bool:
    """Verify an archive file (zip or tar.gz)."""
    if archive_type == "zip":
        return _verify_zip(binary_path)
    if archive_type == "tar.gz":
        return _verify_targz(binary_path)
    return True


def _verify_executable_magic(binary_path) -> bool:
    """Check the magic bytes of a native executable match the current platform."""
    file_size = binary_path.stat().st_size
    if file_size < 10 * 1024 * 1024:
        click.echo(f"Warning: Binary size is only {file_size / 1024 / 1024:.1f}MB, seems too small")
        return False

    with binary_path.open("rb") as f:
        magic = f.read(4)

    if sys.platform.startswith("linux") and magic[:4] != b"\x7fELF":
        click.echo("Error: Downloaded file is not a valid Linux ELF binary")
        return False
    if sys.platform == "darwin" and magic[:4] not in _MACOS_MAGIC:
        click.echo("Error: Downloaded file is not a valid macOS binary")
        return False
    if sys.platform == "win32" and magic[:2] != b"MZ":
        click.echo("Error: Downloaded file is not a valid Windows PE binary")
        return False

    return True


def verify_binary(binary_path, is_archive=False, archive_type=None):
    """Verify downloaded binary is valid."""
    try:
        if is_archive:
            return _verify_archive(binary_path, archive_type)
        return _verify_executable_magic(binary_path)
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

        with Path(dest_path).open("wb") as f:
            with click.progressbar(length=total_size, label="Downloading", show_percent=True, show_pos=True) as bar:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

        return True
    except Exception as e:
        click.echo(f"\nError downloading binary: {str(e)}", err=True)
        return False
