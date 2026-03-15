"""Unit tests for cli_tool.commands.upgrade.core.installer module."""

import os
import platform
import subprocess
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from cli_tool.commands.upgrade.core.installer import (
    _extract_archive,
    _find_extracted_dir,
    _replace_unix_archive,
    _replace_windows_archive,
    replace_binary,
)

# ---------------------------------------------------------------------------
# _extract_archive
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_extract_archive_zip(tmp_path):
    """Extracts zip archive to temp directory."""
    zip_path = tmp_path / "binary.zip"
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    # Create a simple zip
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("devo/devo", "binary content")

    _extract_archive(zip_path, "zip", extract_dir)

    assert (extract_dir / "devo" / "devo").exists()


@pytest.mark.unit
def test_extract_archive_tar_gz(tmp_path):
    """Extracts tar.gz archive to temp directory."""
    # Create a file to add to the tar
    binary_file = tmp_path / "devo"
    binary_file.write_text("binary content")

    tar_path = tmp_path / "binary.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(binary_file, arcname="devo/devo")

    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    _extract_archive(tar_path, "tar.gz", extract_dir)

    assert (extract_dir / "devo" / "devo").exists()


# ---------------------------------------------------------------------------
# _find_extracted_dir
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_find_extracted_dir_returns_devo_subdir(tmp_path):
    """Returns directory that starts with 'devo' when found."""
    (tmp_path / "devo-linux-amd64").mkdir()
    (tmp_path / "other").mkdir()

    result = _find_extracted_dir(tmp_path)

    assert result.name == "devo-linux-amd64"


@pytest.mark.unit
def test_find_extracted_dir_returns_base_when_no_devo_dir(tmp_path):
    """Returns tmp_path itself when no devo-prefixed subdirectory found."""
    (tmp_path / "other_dir").mkdir()

    result = _find_extracted_dir(tmp_path)

    assert result == tmp_path


@pytest.mark.unit
def test_find_extracted_dir_returns_base_when_empty(tmp_path):
    """Returns tmp_path itself when directory is empty."""
    result = _find_extracted_dir(tmp_path)

    assert result == tmp_path


# ---------------------------------------------------------------------------
# _replace_unix_archive
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_replace_unix_archive_replaces_target(tmp_path):
    """Replaces target directory with extracted dir and sets permissions."""
    # Create a "current installation"
    target = tmp_path / "devo"
    target.mkdir()
    (target / "old_devo").write_text("old binary")

    # Create the new extracted dir
    extracted = tmp_path / "new_devo"
    extracted.mkdir()
    new_exe = extracted / "devo"
    new_exe.write_text("new binary")

    backup = tmp_path / "devo.backup"
    temp_extract = tmp_path / "devo_new"
    temp_extract.mkdir()

    _replace_unix_archive(extracted, target, backup, temp_extract)

    # Target should now contain the new binary
    assert (target / "devo").exists()
    assert (target / "devo").read_text() == "new binary"
    # Old content should be gone
    assert not (target / "old_devo").exists()
    # Temp extract dir should be cleaned up
    assert not temp_extract.exists()


@pytest.mark.unit
def test_replace_unix_archive_sets_executable_permissions(tmp_path):
    """Sets 0o755 on the devo executable after replacement."""
    target = tmp_path / "devo"
    target.mkdir()
    (target / "devo").write_text("old")

    extracted = tmp_path / "new"
    extracted.mkdir()
    new_exe = extracted / "devo"
    new_exe.write_text("new")

    backup = tmp_path / "devo.backup"
    temp_extract = tmp_path / "devo_new"
    temp_extract.mkdir()

    _replace_unix_archive(extracted, target, backup, temp_extract)

    mode = oct(os.stat(target / "devo").st_mode)
    assert "755" in mode


# ---------------------------------------------------------------------------
# _replace_windows_archive
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_replace_windows_archive_creates_powershell_script(tmp_path, mocker):
    """Creates a PowerShell upgrade script and returns True."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    target_path = tmp_path / "devo"
    target_path.mkdir()
    temp_extract = tmp_path / "devo_new"
    temp_extract.mkdir()

    mocker.patch("subprocess.Popen")
    mocker.patch.object(subprocess, "CREATE_NEW_CONSOLE", 16, create=True)

    result = _replace_windows_archive(extracted_dir, target_path, temp_extract, 12345)

    assert result is True
    script = target_path.parent / "upgrade_devo.ps1"
    assert script.exists()
    content = script.read_text()
    assert "12345" in content
    assert "powershell" in content.lower() or "Wait-Process" in content


@pytest.mark.unit
def test_replace_windows_archive_launches_powershell(tmp_path, mocker):
    """Launches PowerShell process with the generated script."""
    extracted_dir = tmp_path / "extracted"
    extracted_dir.mkdir()
    target_path = tmp_path / "devo"
    target_path.mkdir()
    temp_extract = tmp_path / "devo_new"
    temp_extract.mkdir()

    mock_popen = mocker.patch("subprocess.Popen")
    mocker.patch.object(subprocess, "CREATE_NEW_CONSOLE", 16, create=True)

    _replace_windows_archive(extracted_dir, target_path, temp_extract, 9999)

    mock_popen.assert_called_once()
    call_args = mock_popen.call_args[0][0]
    assert "powershell.exe" in call_args


# ---------------------------------------------------------------------------
# replace_binary (Linux single-file path)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_replace_binary_linux_single_file(tmp_path, mocker):
    """Linux single-file replacement: backup created, binary moved."""
    mocker.patch("platform.system", return_value="Linux")

    current_exe = tmp_path / "devo"
    current_exe.write_text("old binary")

    new_binary = tmp_path / "devo.new"
    new_binary.write_text("new binary")

    result = replace_binary(new_binary, current_exe, archive_type=None)

    assert result is True
    # Backup should exist
    backup = current_exe.with_suffix(".backup")
    assert backup.exists()
    assert backup.read_text() == "old binary"
    # New binary should be in place
    assert current_exe.read_text() == "new binary"


@pytest.mark.unit
def test_replace_binary_returns_false_on_exception(tmp_path, mocker):
    """Returns False when an exception occurs during replacement."""
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch("shutil.copy2", side_effect=OSError("disk full"))

    current_exe = tmp_path / "devo"
    current_exe.write_text("binary")
    new_binary = tmp_path / "devo.new"
    new_binary.write_text("new")

    result = replace_binary(new_binary, current_exe, archive_type=None)

    assert result is False


@pytest.mark.unit
def test_replace_binary_archive_type_mac(tmp_path, mocker):
    """macOS tar.gz archive path calls _replace_unix_archive."""
    mocker.patch("platform.system", return_value="Darwin")

    # Create fake archive
    binary_file = tmp_path / "devo_bin"
    binary_file.write_text("content")
    tar_path = tmp_path / "binary.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(binary_file, arcname="devo/devo")

    # Create fake target (an existing "installation")
    target = tmp_path / "devo"
    target.mkdir()
    (target / "devo").write_text("old")

    mock_replace_unix = mocker.patch("cli_tool.commands.upgrade.core.installer._replace_unix_archive", return_value=True)

    result = replace_binary(tar_path, target, archive_type="tar.gz")

    assert result is True
    mock_replace_unix.assert_called_once()


@pytest.mark.unit
def test_replace_binary_archive_type_windows(tmp_path, mocker):
    """Windows zip archive path calls _replace_windows_archive."""
    mocker.patch("platform.system", return_value="Windows")

    # Create fake zip
    zip_path = tmp_path / "binary.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("devo/devo.exe", "new exe")

    target = tmp_path / "devo"
    target.mkdir()
    (target / "devo.exe").write_text("old")

    mock_replace_windows = mocker.patch("cli_tool.commands.upgrade.core.installer._replace_windows_archive", return_value=True)

    result = replace_binary(zip_path, target, archive_type="zip")

    assert result is True
    mock_replace_windows.assert_called_once()


@pytest.mark.unit
def test_replace_binary_cleans_up_temp_on_extract_error(tmp_path, mocker):
    """Temp directory is removed when extraction fails."""
    mocker.patch("platform.system", return_value="Darwin")
    mocker.patch("cli_tool.commands.upgrade.core.installer._extract_archive", side_effect=Exception("bad archive"))

    target = tmp_path / "devo"
    target.mkdir()
    (target / "devo").write_text("old")

    # Create the new "archive" (invalid)
    new_binary = tmp_path / "bad.tar.gz"
    new_binary.write_text("not a real archive")

    result = replace_binary(new_binary, target, archive_type="tar.gz")

    assert result is False
    # Temp dir should not be left behind
    temp_extract = target.parent / "devo_new"
    assert not temp_extract.exists()


@pytest.mark.unit
def test_replace_binary_removes_old_backup_if_exists(tmp_path, mocker):
    """Old backup directory is removed before creating new one."""
    mocker.patch("platform.system", return_value="Darwin")

    target = tmp_path / "devo"
    target.mkdir()
    (target / "devo").write_text("old binary")

    # Pre-existing backup
    backup = target.parent / "devo.backup"
    backup.mkdir()
    (backup / "stale").write_text("stale")

    # Create a real tar.gz to extract
    binary_file = tmp_path / "devo_bin"
    binary_file.write_text("new content")
    tar_path = tmp_path / "binary.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(binary_file, arcname="devo/devo")

    mock_replace_unix = mocker.patch("cli_tool.commands.upgrade.core.installer._replace_unix_archive", return_value=True)

    replace_binary(tar_path, target, archive_type="tar.gz")

    # Old backup should have been removed
    assert not (backup / "stale").exists()
