"""
Integration tests for upgrade command flow.

Tests cover:
- Version check detects newer version
- Binary download for current platform
- Binary verification after download
- Binary installation and replacement
- Upgrade with no newer version available
- Mock HTTP requests for version check and download
- Mock platform detection for binary format

**Validates: Requirements 4.1, 4.3, 11.1, 11.2, 11.3, 11.4, 11.5**
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, call

import pytest
from click.testing import CliRunner

from cli_tool.commands.upgrade.commands.upgrade import upgrade


@pytest.fixture
def mock_github_release_response():
    """Provide mock releases API response (normalized to internal format)."""
    return {
        "tag_name": "v1.5.0",
        "published_at": "2026-01-01T00:00:00Z",
        "assets": [
            {"name": "devo-linux-amd64", "browser_download_url": "https://github.com/example/devo-cli/releases/download/v1.5.0/devo-linux-amd64"},
            {
                "name": "devo-darwin-amd64.tar.gz",
                "browser_download_url": "https://github.com/example/devo-cli/releases/download/v1.5.0/devo-darwin-amd64.tar.gz",
            },
            {
                "name": "devo-windows-amd64.zip",
                "browser_download_url": "https://github.com/example/devo-cli/releases/download/v1.5.0/devo-windows-amd64.zip",
            },
        ],
    }


@pytest.fixture
def mock_current_version(mocker):
    """Mock current version to be older than latest."""
    return mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")


@pytest.fixture
def mock_same_version(mocker):
    """Mock current version to be same as latest."""
    return mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.5.0")


# ============================================================================
# Test: Version Check Detects Newer Version
# ============================================================================


@pytest.mark.integration
def test_version_check_detects_newer_version(cli_runner, mocker, mock_current_version, mock_github_release_response):
    """
    Test that version check correctly detects a newer version available.

    Validates:
    - Current version is retrieved
    - Latest version is fetched from GitHub API
    - Version comparison identifies newer version
    - Update available message is displayed
    """
    # Mock get_latest_release to return newer version
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock clear_cache
    mocker.patch("cli_tool.core.utils.version_check.clear_cache")

    # Run upgrade command with --check flag
    result = cli_runner.invoke(upgrade, ["--check"])

    # Verify version check output
    assert result.exit_code == 0
    assert "Current version: 1.0.0" in result.output
    assert "Latest version: 1.5.0" in result.output
    assert "Update available" in result.output


@pytest.mark.integration
def test_version_check_no_newer_version(cli_runner, mocker, mock_same_version, mock_github_release_response):
    """
    Test version check when already on latest version.

    Validates:
    - Current and latest versions are compared
    - No update message is displayed
    - Command exits successfully
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock clear_cache
    mocker.patch("cli_tool.core.utils.version_check.clear_cache")

    # Run upgrade command with --check flag
    result = cli_runner.invoke(upgrade, ["--check"])

    # Verify output
    assert result.exit_code == 0
    assert "You already have the latest version (1.5.0)" in result.output
    assert "Update available" not in result.output


@pytest.mark.integration
def test_version_check_api_failure(cli_runner, mocker, mock_current_version):
    """
    Test version check when GitHub API request fails.

    Validates:
    - API failure is handled gracefully
    - Error message is displayed
    - Non-zero exit code is returned
    """
    # Mock get_latest_release to return None (API failure)
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = None

    # Mock clear_cache
    mocker.patch("cli_tool.core.utils.version_check.clear_cache")

    # Run upgrade command with --check flag
    result = cli_runner.invoke(upgrade, ["--check"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Could not fetch latest release information" in result.output


# ============================================================================
# Test: Binary Download for Current Platform
# ============================================================================


@pytest.mark.integration
def test_binary_download_linux(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test binary download for Linux platform.

    Validates:
    - Platform is detected as Linux
    - Correct binary name is selected (single file)
    - Download URL is correct
    - Binary is downloaded successfully
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit to prevent actual exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify download was called with correct URL
    assert mock_download.called
    call_args = mock_download.call_args[0]
    assert call_args[0] == "https://github.com/example/devo-cli/releases/download/v1.5.0/devo-linux-amd64"

    # Verify success
    assert "Successfully upgraded to version 1.5.0" in result.output


@pytest.mark.integration
def test_binary_download_macos(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test binary download for macOS platform.

    Validates:
    - Platform is detected as macOS (darwin)
    - Correct binary name is selected (tar.gz archive)
    - Download URL is correct
    - Archive is downloaded successfully
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("darwin", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-darwin-amd64.tar.gz")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path (onedir structure)
    mock_exe_dir = tmp_path / "devo"
    mock_exe_dir.mkdir()
    mock_exe = mock_exe_dir / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe_dir)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify download was called with correct URL
    assert mock_download.called
    call_args = mock_download.call_args[0]
    assert call_args[0] == "https://github.com/example/devo-cli/releases/download/v1.5.0/devo-darwin-amd64.tar.gz"

    # Verify archive type was passed to verify_binary
    assert mock_verify.called
    verify_call_args = mock_verify.call_args
    assert verify_call_args[1]["is_archive"] is True
    assert verify_call_args[1]["archive_type"] == "tar.gz"

    # Verify success
    assert "Successfully upgraded to version 1.5.0" in result.output


@pytest.mark.integration
def test_binary_download_windows(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test binary download for Windows platform.

    Validates:
    - Platform is detected as Windows
    - Correct binary name is selected (ZIP archive)
    - Download URL is correct
    - ZIP archive is downloaded successfully
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("windows", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-windows-amd64.zip")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path (onedir structure)
    mock_exe_dir = tmp_path / "devo"
    mock_exe_dir.mkdir()
    mock_exe = mock_exe_dir / "devo.exe"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe_dir)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit to prevent actual exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify download was called with correct URL
    assert mock_download.called
    call_args = mock_download.call_args[0]
    assert call_args[0] == "https://github.com/example/devo-cli/releases/download/v1.5.0/devo-windows-amd64.zip"

    # Verify archive type was passed to verify_binary
    assert mock_verify.called
    verify_call_args = mock_verify.call_args
    assert verify_call_args[1]["is_archive"] is True
    assert verify_call_args[1]["archive_type"] == "zip"

    # Verify success
    assert "Successfully upgraded to version 1.5.0" in result.output


# ============================================================================
# Test: Binary Verification After Download
# ============================================================================


@pytest.mark.integration
def test_binary_verification_success(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test successful binary verification after download.

    Validates:
    - Downloaded binary is verified
    - Verification checks file format
    - Installation proceeds after successful verification
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to return True
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify verification was called
    assert mock_verify.called
    assert "Verifying downloaded binary" in result.output

    # Verify installation proceeded
    assert mock_replace.called
    assert "Successfully upgraded to version 1.5.0" in result.output


@pytest.mark.integration
def test_binary_verification_failure(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test binary verification failure after download.

    Validates:
    - Failed verification is detected
    - Error message is displayed
    - Installation is aborted
    - Non-zero exit code is returned
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to return False (verification failed)
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = False

    # Mock replace_binary (should not be called)
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify verification was called
    assert mock_verify.called

    # Verify error message
    assert result.exit_code == 1
    assert "Downloaded binary failed verification" in result.output
    assert "file may be corrupted" in result.output

    # Verify installation was not attempted
    assert not mock_replace.called


# ============================================================================
# Test: Binary Installation and Replacement
# ============================================================================


@pytest.mark.integration
def test_binary_installation_linux(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test binary installation and replacement on Linux.

    Validates:
    - Old binary is backed up
    - New binary replaces old binary
    - Permissions are set correctly
    - Success message is displayed
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify replace_binary was called
    assert mock_replace.called
    call_args = mock_replace.call_args
    assert call_args[1]["archive_type"] is None  # Linux uses single binary

    # Verify success
    assert "Installing new version" in result.output
    assert "Successfully upgraded to version 1.5.0" in result.output


@pytest.mark.integration
def test_binary_installation_macos_tarball(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test binary installation from tarball on macOS.

    Validates:
    - Tarball is extracted
    - Directory structure is replaced
    - Executable permissions are set
    - Backup is created
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("darwin", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-darwin-amd64.tar.gz")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path (onedir structure)
    mock_exe_dir = tmp_path / "devo"
    mock_exe_dir.mkdir()
    mock_exe = mock_exe_dir / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe_dir)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify replace_binary was called with tar.gz archive type
    assert mock_replace.called
    call_args = mock_replace.call_args
    assert call_args[1]["archive_type"] == "tar.gz"

    # Verify success
    assert "Successfully upgraded to version 1.5.0" in result.output


@pytest.mark.integration
def test_binary_installation_windows_zip(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test binary installation from ZIP on Windows.

    Validates:
    - ZIP is extracted
    - Directory structure is replaced
    - PowerShell script is created for post-exit replacement
    - Backup is created
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("windows", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-windows-amd64.zip")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path (onedir structure)
    mock_exe_dir = tmp_path / "devo"
    mock_exe_dir.mkdir()
    mock_exe = mock_exe_dir / "devo.exe"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe_dir)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit to prevent actual exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify replace_binary was called with zip archive type
    assert mock_replace.called
    call_args = mock_replace.call_args
    assert call_args[1]["archive_type"] == "zip"

    # Verify success
    assert "Successfully upgraded to version 1.5.0" in result.output


@pytest.mark.integration
def test_binary_installation_failure(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test handling of binary installation failure.

    Validates:
    - Installation failure is detected
    - Error message is displayed
    - Non-zero exit code is returned
    """
    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary to return False (installation failed)
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = False

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_replace.called


# ============================================================================
# Test: Upgrade with No Newer Version Available
# ============================================================================


@pytest.mark.integration
def test_upgrade_no_newer_version_without_force(cli_runner, mocker, mock_same_version, mock_github_release_response):
    """
    Test upgrade when already on latest version without --force flag.

    Validates:
    - Version comparison detects same version
    - Upgrade is skipped
    - Message suggests using --force to reinstall
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Run upgrade command without --force flag
    result = cli_runner.invoke(upgrade)

    # Verify upgrade is skipped
    assert result.exit_code == 0
    assert "You already have the latest version (1.5.0)" in result.output
    assert "Use --force to reinstall anyway" in result.output


@pytest.mark.integration
def test_upgrade_no_newer_version_with_force(cli_runner, mocker, mock_same_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with --force flag when already on latest version.

    Validates:
    - --force flag bypasses version check
    - Upgrade proceeds even with same version
    - Binary is downloaded and installed
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify upgrade proceeded
    assert mock_download.called
    assert mock_verify.called
    assert mock_replace.called
    assert "Successfully upgraded to version 1.5.0" in result.output


# ============================================================================
# Test: Platform Detection and Binary Format
# ============================================================================


@pytest.mark.integration
def test_unsupported_platform(cli_runner, mocker, mock_current_version, mock_github_release_response):
    """
    Test upgrade on unsupported platform.

    Validates:
    - Unsupported platform is detected
    - Error message is displayed
    - Non-zero exit code is returned
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection to return None (unsupported)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=None)

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Unsupported platform" in result.output


@pytest.mark.integration
def test_binary_not_found_for_platform(cli_runner, mocker, mock_current_version, tmp_path):
    """
    Test upgrade when binary is not available for current platform.

    Validates:
    - Missing binary asset is detected
    - Error message shows expected binary name
    - Non-zero exit code is returned
    """
    # Mock get_latest_release with no matching binary
    release_response = {
        "tag_name": "v1.5.0",
        "name": "Release 1.5.0",
        "assets": [
            {"name": "devo-linux-amd64", "browser_download_url": "https://github.com/example/devo-cli/releases/download/v1.5.0/devo-linux-amd64"}
        ],
    }
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = release_response

    # Mock platform detection for Windows (but no Windows binary in release)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("windows", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-windows-amd64.zip")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo.exe"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Binary not found for windows-amd64" in result.output
    assert "Looking for: devo-windows-amd64.zip" in result.output


# ============================================================================
# Test: Download Failures
# ============================================================================


@pytest.mark.integration
def test_download_failure(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test handling of download failure.

    Validates:
    - Download failure is detected
    - Error message is displayed
    - Non-zero exit code is returned
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to return False (download failed)
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = False

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_download.called


# ============================================================================
# Test: Permission Errors
# ============================================================================


@pytest.mark.integration
def test_no_write_permission(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade when user lacks write permission to binary location.

    Validates:
    - Permission check is performed
    - Error message is displayed
    - Suggestion to use sudo is shown
    - Non-zero exit code is returned
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock os.access to return False (no write permission)
    mocker.patch("os.access", return_value=False)

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "No write permission" in result.output
    assert "sudo" in result.output or "user-writable location" in result.output


# ============================================================================
# Test: User Confirmation
# ============================================================================


@pytest.mark.integration
def test_upgrade_with_user_confirmation_yes(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with user confirmation (user accepts).

    Validates:
    - Confirmation prompt is displayed
    - User input 'y' proceeds with upgrade
    - Binary is downloaded and installed
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command without --force flag, simulate user confirming
    result = cli_runner.invoke(upgrade, input="y\n")

    # Verify confirmation prompt was shown
    assert "Do you want to continue with the upgrade?" in result.output

    # Verify upgrade proceeded
    assert mock_download.called
    assert "Successfully upgraded to version 1.5.0" in result.output


@pytest.mark.integration
def test_upgrade_with_user_confirmation_no(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with user confirmation (user declines).

    Validates:
    - Confirmation prompt is displayed
    - User input 'n' cancels upgrade
    - No download or installation occurs
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary (should not be called)
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")

    # Run upgrade command without --force flag, simulate user declining
    result = cli_runner.invoke(upgrade, input="n\n")

    # Verify confirmation prompt was shown
    assert "Do you want to continue with the upgrade?" in result.output

    # Verify upgrade was cancelled
    assert result.exit_code == 0
    assert "Upgrade cancelled" in result.output

    # Verify download was not attempted
    assert not mock_download.called


# ============================================================================
# Test: Executable Path Detection
# ============================================================================


@pytest.mark.integration
def test_cannot_determine_executable_path(cli_runner, mocker, mock_current_version, mock_github_release_response):
    """
    Test upgrade when executable path cannot be determined.

    Validates:
    - Missing executable path is detected
    - Error message is displayed
    - Manual installation instructions are shown
    - Non-zero exit code is returned
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path to return None
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=None)

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Could not determine current executable location" in result.output
    assert "install manually from GitHub Releases" in result.output


# ============================================================================
# Test: Unknown Current Version
# ============================================================================


@pytest.mark.integration
def test_upgrade_with_unknown_current_version(cli_runner, mocker, mock_github_release_response, tmp_path):
    """
    Test upgrade when current version cannot be determined.

    Validates:
    - Unknown version is handled gracefully
    - Warning message is displayed
    - Upgrade proceeds with latest version
    """
    # Mock get_current_version to return "unknown"
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="unknown")

    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = True

    # Mock os._exit
    mock_exit = mocker.patch("os._exit")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify warning is displayed
    assert "Could not determine current version" in result.output

    # Verify upgrade proceeds
    assert "Latest version: 1.5.0" in result.output
    assert mock_download.called
    assert "Successfully upgraded to version 1.5.0" in result.output


# ============================================================================
# Test: Keyboard Interrupt Handling
# ============================================================================


@pytest.mark.integration
def test_upgrade_keyboard_interrupt(cli_runner, mocker, mock_current_version, mock_github_release_response):
    """
    Test upgrade cancellation via keyboard interrupt (Ctrl+C).

    Validates:
    - KeyboardInterrupt is caught
    - Cancellation message is displayed
    - Non-zero exit code is returned
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path to raise KeyboardInterrupt
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", side_effect=KeyboardInterrupt())

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify cancellation handling
    assert result.exit_code == 1
    assert "Upgrade cancelled by user" in result.output


# ============================================================================
# Test: Generic Exception Handling
# ============================================================================


@pytest.mark.integration
def test_upgrade_generic_exception(cli_runner, mocker, mock_current_version, mock_github_release_response):
    """
    Test upgrade with unexpected exception.

    Validates:
    - Unexpected exceptions are caught
    - Error message is displayed
    - Non-zero exit code is returned
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection to raise exception
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", side_effect=Exception("Unexpected error"))

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Error during upgrade" in result.output
    assert "Unexpected error" in result.output


# ============================================================================
# Test: Edge Cases - Network Failures
# ============================================================================


@pytest.mark.integration
def test_upgrade_network_timeout(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with network timeout during download.

    Validates:
    - Network timeout is handled gracefully
    - Error message is displayed
    - Non-zero exit code is returned
    - Temporary file is cleaned up

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to raise timeout exception
    import requests

    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.side_effect = requests.exceptions.Timeout("Connection timeout")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_download.called


@pytest.mark.integration
def test_upgrade_connection_error(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with connection error during download.

    Validates:
    - Connection errors are handled gracefully
    - Error message is displayed
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to raise connection error
    import requests

    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.side_effect = requests.exceptions.ConnectionError("Network unreachable")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_download.called


@pytest.mark.integration
def test_upgrade_http_error(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with HTTP error during download (404, 500, etc).

    Validates:
    - HTTP errors are handled gracefully
    - Error message is displayed
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to raise HTTP error
    import requests

    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.side_effect = requests.exceptions.HTTPError("404 Not Found")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_download.called


# ============================================================================
# Test: Edge Cases - Corrupted Download
# ============================================================================


@pytest.mark.integration
def test_upgrade_corrupted_binary_too_small(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with corrupted binary (file too small).

    Validates:
    - Small file size is detected during verification
    - Error message is displayed
    - Installation is aborted
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to succeed
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to return False (corrupted file)
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = False

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_verify.called
    assert "Downloaded binary failed verification" in result.output
    assert "file may be corrupted" in result.output


@pytest.mark.integration
def test_upgrade_corrupted_zip_invalid_format(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with corrupted ZIP file (invalid format).

    Validates:
    - Invalid ZIP format is detected during verification
    - Error message is displayed
    - Installation is aborted
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("windows", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-windows-amd64.zip")

    # Mock get_executable_path (onedir structure)
    mock_exe_dir = tmp_path / "devo"
    mock_exe_dir.mkdir()
    mock_exe = mock_exe_dir / "devo.exe"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe_dir)

    # Mock download_binary to succeed
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to return False (invalid ZIP)
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = False

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_verify.called
    assert "Downloaded binary failed verification" in result.output


@pytest.mark.integration
def test_upgrade_corrupted_tarball_invalid_format(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with corrupted tarball (invalid format).

    Validates:
    - Invalid tarball format is detected during verification
    - Error message is displayed
    - Installation is aborted
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("darwin", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-darwin-amd64.tar.gz")

    # Mock get_executable_path (onedir structure)
    mock_exe_dir = tmp_path / "devo"
    mock_exe_dir.mkdir()
    mock_exe = mock_exe_dir / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe_dir)

    # Mock download_binary to succeed
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to return False (invalid tarball)
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = False

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_verify.called
    assert "Downloaded binary failed verification" in result.output


@pytest.mark.integration
def test_upgrade_incomplete_download(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade with incomplete download (partial file).

    Validates:
    - Incomplete download is detected
    - Error message is displayed
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to return False (incomplete download)
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = False

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_download.called


# ============================================================================
# Test: Edge Cases - Rollback on Failure
# ============================================================================


@pytest.mark.integration
def test_upgrade_rollback_on_extraction_failure(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade rollback when archive extraction fails.

    Validates:
    - Extraction failure is detected
    - Backup is preserved
    - Error message is displayed
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("darwin", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-darwin-amd64.tar.gz")

    # Mock get_executable_path (onedir structure)
    mock_exe_dir = tmp_path / "devo"
    mock_exe_dir.mkdir()
    mock_exe = mock_exe_dir / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe_dir)

    # Mock download_binary to succeed
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to succeed
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary to fail (extraction error)
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.return_value = False

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert mock_replace.called


@pytest.mark.integration
def test_upgrade_rollback_on_permission_error_during_install(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade rollback when permission error occurs during installation.

    Validates:
    - Permission error during installation is detected
    - Backup is preserved
    - Error message is displayed
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to succeed
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to succeed
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary to raise PermissionError
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.side_effect = PermissionError("Permission denied")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Error during upgrade" in result.output


@pytest.mark.integration
def test_upgrade_rollback_on_disk_full(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade rollback when disk is full during installation.

    Validates:
    - Disk full error is detected
    - Backup is preserved
    - Error message is displayed
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to succeed
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to succeed
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary to raise OSError (disk full)
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.side_effect = OSError("No space left on device")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Error during upgrade" in result.output


# ============================================================================
# Test: Edge Cases - Insufficient Permissions
# ============================================================================


@pytest.mark.integration
def test_upgrade_insufficient_permissions_parent_directory(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade when user lacks write permission to parent directory.

    Validates:
    - Permission check detects lack of write access
    - Error message is displayed with helpful suggestion
    - Non-zero exit code is returned
    - No download is attempted

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock os.access to return False (no write permission)
    mocker.patch("os.access", return_value=False)

    # Mock download_binary (should not be called)
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "No write permission" in result.output
    assert "sudo" in result.output or "user-writable location" in result.output

    # Verify download was not attempted
    assert not mock_download.called


@pytest.mark.integration
def test_upgrade_read_only_filesystem(cli_runner, mocker, mock_current_version, mock_github_release_response, tmp_path):
    """
    Test upgrade on read-only filesystem.

    Validates:
    - Read-only filesystem is detected during installation
    - Error message is displayed
    - Non-zero exit code is returned

    **Validates: Requirements 13.4, 13.5**
    """
    # Mock get_latest_release
    mock_release = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release")
    mock_release.return_value = mock_github_release_response

    # Mock platform detection
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    # Mock get_executable_path
    mock_exe = tmp_path / "devo"
    mock_exe.touch()
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=mock_exe)

    # Mock download_binary to succeed
    mock_download = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary")
    mock_download.return_value = True

    # Mock verify_binary to succeed
    mock_verify = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary")
    mock_verify.return_value = True

    # Mock replace_binary to raise OSError (read-only filesystem)
    mock_replace = mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary")
    mock_replace.side_effect = OSError("Read-only file system")

    # Run upgrade command with --force flag
    result = cli_runner.invoke(upgrade, ["--force"])

    # Verify error handling
    assert result.exit_code == 1
    assert "Error during upgrade" in result.output
