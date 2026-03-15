"""Unit tests for cli_tool.commands.upgrade.core.downloader module."""

import sys
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.upgrade.core.downloader import (
    _verify_archive,
    _verify_executable_magic,
    _verify_targz,
    _verify_zip,
    download_binary,
    verify_binary,
)

# ---------------------------------------------------------------------------
# _verify_zip
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_zip_valid_archive_with_devo_exe(tmp_path):
    """Returns True for a valid ZIP containing devo.exe."""
    zip_path = tmp_path / "binary.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("devo/devo.exe", "fake exe content")

    result = _verify_zip(zip_path)

    assert result is True


@pytest.mark.unit
def test_verify_zip_valid_archive_without_devo_exe(tmp_path):
    """Returns False when ZIP does not contain devo.exe."""
    zip_path = tmp_path / "binary.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("readme.txt", "no executable here")

    result = _verify_zip(zip_path)

    assert result is False


@pytest.mark.unit
def test_verify_zip_not_a_zip_file(tmp_path):
    """Returns False when file is not a valid ZIP archive."""
    fake_zip = tmp_path / "notazip.zip"
    fake_zip.write_bytes(b"this is not a zip")

    result = _verify_zip(fake_zip)

    assert result is False


@pytest.mark.unit
def test_verify_zip_devo_exe_nested_path(tmp_path):
    """Returns True when devo.exe appears in a nested path within the ZIP."""
    zip_path = tmp_path / "binary.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("devo-windows-amd64/devo.exe", "exe")

    result = _verify_zip(zip_path)

    assert result is True


# ---------------------------------------------------------------------------
# _verify_targz
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_targz_valid_archive_with_devo_binary(tmp_path):
    """Returns True for a tar.gz containing the devo executable."""
    exe = tmp_path / "devo"
    exe.write_text("binary")
    tar_path = tmp_path / "binary.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(exe, arcname="devo/devo")

    result = _verify_targz(tar_path)

    assert result is True


@pytest.mark.unit
def test_verify_targz_without_devo_binary(tmp_path):
    """Returns False when tar.gz does not contain the devo binary."""
    other = tmp_path / "other"
    other.write_text("not devo")
    tar_path = tmp_path / "binary.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(other, arcname="readme.txt")

    result = _verify_targz(tar_path)

    assert result is False


@pytest.mark.unit
def test_verify_targz_not_a_tar_file(tmp_path):
    """Returns False when file is not a valid tar archive."""
    fake_tar = tmp_path / "fake.tar.gz"
    fake_tar.write_bytes(b"not a tar file at all")

    result = _verify_targz(fake_tar)

    assert result is False


# ---------------------------------------------------------------------------
# _verify_archive
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_archive_delegates_zip(tmp_path, mocker):
    """Calls _verify_zip for archive_type 'zip'."""
    mock_verify_zip = mocker.patch("cli_tool.commands.upgrade.core.downloader._verify_zip", return_value=True)
    path = tmp_path / "f.zip"
    path.write_text("")

    result = _verify_archive(path, "zip")

    assert result is True
    mock_verify_zip.assert_called_once_with(path)


@pytest.mark.unit
def test_verify_archive_delegates_targz(tmp_path, mocker):
    """Calls _verify_targz for archive_type 'tar.gz'."""
    mock_verify_targz = mocker.patch("cli_tool.commands.upgrade.core.downloader._verify_targz", return_value=True)
    path = tmp_path / "f.tar.gz"
    path.write_text("")

    result = _verify_archive(path, "tar.gz")

    assert result is True
    mock_verify_targz.assert_called_once_with(path)


@pytest.mark.unit
def test_verify_archive_unknown_type_returns_true(tmp_path):
    """Returns True (skip verification) for unknown archive types."""
    path = tmp_path / "file.bin"
    path.write_text("")

    result = _verify_archive(path, "unknown")

    assert result is True


# ---------------------------------------------------------------------------
# _verify_executable_magic
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_executable_magic_valid_linux_elf(tmp_path, monkeypatch):
    """Returns True for a large Linux ELF binary."""
    exe = tmp_path / "devo"
    # Write ELF magic + padding to exceed 10 MB
    exe.write_bytes(b"\x7fELF" + b"\x00" * (10 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "platform", "linux")

    result = _verify_executable_magic(exe)

    assert result is True


@pytest.mark.unit
def test_verify_executable_magic_linux_wrong_magic(tmp_path, monkeypatch):
    """Returns False when Linux binary has wrong magic bytes."""
    exe = tmp_path / "devo"
    exe.write_bytes(b"\x00\x00\x00\x00" + b"\x00" * (10 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "platform", "linux")

    result = _verify_executable_magic(exe)

    assert result is False


@pytest.mark.unit
def test_verify_executable_magic_file_too_small(tmp_path, monkeypatch):
    """Returns False when binary size is below 10 MB threshold."""
    exe = tmp_path / "devo"
    exe.write_bytes(b"\x7fELF" + b"\x00" * 100)
    monkeypatch.setattr(sys, "platform", "linux")

    result = _verify_executable_magic(exe)

    assert result is False


@pytest.mark.unit
def test_verify_executable_magic_valid_macos(tmp_path, monkeypatch):
    """Returns True for a large macOS binary with valid magic bytes."""
    exe = tmp_path / "devo"
    # Mach-O magic: \xcf\xfa\xed\xfe
    exe.write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * (10 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "platform", "darwin")

    result = _verify_executable_magic(exe)

    assert result is True


@pytest.mark.unit
def test_verify_executable_magic_macos_wrong_magic(tmp_path, monkeypatch):
    """Returns False when macOS binary has wrong magic bytes."""
    exe = tmp_path / "devo"
    exe.write_bytes(b"\x00\x00\x00\x00" + b"\x00" * (10 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "platform", "darwin")

    result = _verify_executable_magic(exe)

    assert result is False


@pytest.mark.unit
def test_verify_executable_magic_valid_windows(tmp_path, monkeypatch):
    """Returns True for a large Windows PE binary with MZ header."""
    exe = tmp_path / "devo.exe"
    exe.write_bytes(b"MZ" + b"\x00" * (10 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "platform", "win32")

    result = _verify_executable_magic(exe)

    assert result is True


@pytest.mark.unit
def test_verify_executable_magic_windows_wrong_magic(tmp_path, monkeypatch):
    """Returns False when Windows binary has wrong magic bytes."""
    exe = tmp_path / "devo.exe"
    exe.write_bytes(b"\x00\x00" + b"\x00" * (10 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "platform", "win32")

    result = _verify_executable_magic(exe)

    assert result is False


@pytest.mark.unit
def test_verify_executable_magic_other_platform_large_file(tmp_path, monkeypatch):
    """Returns True for an unrecognized platform with a large file (no magic check)."""
    exe = tmp_path / "devo"
    exe.write_bytes(b"\xde\xad\xbe\xef" + b"\x00" * (10 * 1024 * 1024 + 1))
    monkeypatch.setattr(sys, "platform", "freebsd12")

    result = _verify_executable_magic(exe)

    assert result is True


# ---------------------------------------------------------------------------
# verify_binary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_binary_archive_delegates_to_verify_archive(mocker, tmp_path):
    """verify_binary calls _verify_archive when is_archive=True."""
    mock_arch = mocker.patch("cli_tool.commands.upgrade.core.downloader._verify_archive", return_value=True)
    path = tmp_path / "f.zip"
    path.write_text("")

    result = verify_binary(path, is_archive=True, archive_type="zip")

    assert result is True
    mock_arch.assert_called_once_with(path, "zip")


@pytest.mark.unit
def test_verify_binary_non_archive_delegates_to_magic_check(mocker, tmp_path):
    """verify_binary calls _verify_executable_magic when is_archive=False."""
    mock_magic = mocker.patch("cli_tool.commands.upgrade.core.downloader._verify_executable_magic", return_value=True)
    path = tmp_path / "devo"
    path.write_text("")

    result = verify_binary(path, is_archive=False)

    assert result is True
    mock_magic.assert_called_once_with(path)


@pytest.mark.unit
def test_verify_binary_returns_false_on_exception(mocker, tmp_path):
    """Returns False when an exception is raised during verification."""
    mocker.patch("cli_tool.commands.upgrade.core.downloader._verify_executable_magic", side_effect=Exception("oops"))
    path = tmp_path / "devo"
    path.write_text("")

    result = verify_binary(path, is_archive=False)

    assert result is False


# ---------------------------------------------------------------------------
# download_binary
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_download_binary_success(tmp_path, mocker):
    """Returns True when download completes successfully."""
    dest = tmp_path / "devo"

    mock_response = MagicMock()
    mock_response.headers = {"content-length": "1024"}
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
    mocker.patch("requests.get", return_value=mock_response)

    result = download_binary("https://example.com/devo", dest)

    assert result is True
    assert dest.exists()


@pytest.mark.unit
def test_download_binary_raises_on_http_error(tmp_path, mocker):
    """Returns False when the HTTP request raises an exception."""
    import requests

    dest = tmp_path / "devo"
    mocker.patch("requests.get", side_effect=requests.exceptions.ConnectionError("no network"))

    result = download_binary("https://example.com/devo", dest)

    assert result is False


@pytest.mark.unit
def test_download_binary_returns_false_on_exception(tmp_path, mocker):
    """Returns False on any unexpected exception."""
    dest = tmp_path / "devo"
    mocker.patch("requests.get", side_effect=Exception("unexpected"))

    result = download_binary("https://example.com/devo", dest)

    assert result is False


@pytest.mark.unit
def test_download_binary_zero_content_length(tmp_path, mocker):
    """Handles missing/zero content-length header without error."""
    dest = tmp_path / "devo"

    mock_response = MagicMock()
    mock_response.headers = {}  # No content-length
    mock_response.iter_content.return_value = [b"data"]
    mocker.patch("requests.get", return_value=mock_response)

    result = download_binary("https://example.com/devo", dest)

    assert result is True
