"""Unit tests for cli_tool.commands.upgrade.commands.upgrade module."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from cli_tool.commands.upgrade.commands.upgrade import _determine_archive_suffix, _download_and_verify, upgrade

# ---------------------------------------------------------------------------
# _determine_archive_suffix
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_determine_archive_suffix_windows():
    """Windows returns .zip suffix."""
    assert _determine_archive_suffix("windows") == ".zip"


@pytest.mark.unit
def test_determine_archive_suffix_darwin():
    """Darwin returns .tar.gz suffix."""
    assert _determine_archive_suffix("darwin") == ".tar.gz"


@pytest.mark.unit
def test_determine_archive_suffix_linux():
    """Linux and other platforms return .tmp suffix."""
    assert _determine_archive_suffix("linux") == ".tmp"
    assert _determine_archive_suffix("other") == ".tmp"


# ---------------------------------------------------------------------------
# _download_and_verify
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_download_and_verify_exits_when_download_fails(mocker):
    """Calls sys.exit(1) when download_binary returns False."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary", return_value=False)

    with pytest.raises(SystemExit) as exc_info:
        _download_and_verify("https://example.com/binary", None)

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_download_and_verify_exits_when_verify_fails(mocker, tmp_path):
    """Calls sys.exit(1) when verify_binary returns False."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary", return_value=False)
    mocker.patch("tempfile.NamedTemporaryFile")

    # We need a real file path in the tempfile mock
    tmp_file = tmp_path / "test.tmp"
    tmp_file.write_text("content")

    mock_tmp = MagicMock()
    mock_tmp.__enter__ = MagicMock(return_value=MagicMock(name=str(tmp_file)))
    mock_tmp.__exit__ = MagicMock(return_value=False)
    mocker.patch("tempfile.NamedTemporaryFile", return_value=mock_tmp)

    with pytest.raises(SystemExit) as exc_info:
        _download_and_verify("https://example.com/binary", None)

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# upgrade command
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upgrade_check_flag_no_update_available(mocker):
    """--check flag shows 'already have the latest version' when up to date."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.5.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={"tag_name": "v1.5.0", "assets": []},
    )
    mocker.patch("cli_tool.core.utils.version_check.clear_cache")

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--check"])

    assert result.exit_code == 0
    assert "latest version" in result.output.lower() or "1.5.0" in result.output


@pytest.mark.unit
def test_upgrade_check_flag_update_available(mocker):
    """--check flag shows update available message when newer version exists."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.4.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={"tag_name": "v1.5.0", "assets": []},
    )
    mocker.patch("cli_tool.core.utils.version_check.clear_cache")

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--check"])

    assert result.exit_code == 0
    assert "1.4.0" in result.output
    assert "1.5.0" in result.output


@pytest.mark.unit
def test_upgrade_exits_when_no_release_info(mocker):
    """Exits with code 1 when latest release cannot be fetched."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_latest_release", return_value=None)

    runner = CliRunner()
    result = runner.invoke(upgrade, [])

    assert result.exit_code == 1
    assert "Could not fetch" in result.output


@pytest.mark.unit
def test_upgrade_exits_when_no_latest_version(mocker):
    """Exits with code 1 when tag_name is missing from release info."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={"tag_name": "", "assets": []},
    )

    runner = CliRunner()
    result = runner.invoke(upgrade, [])

    assert result.exit_code == 1
    assert "Could not determine latest version" in result.output


@pytest.mark.unit
def test_upgrade_already_latest_without_force(mocker):
    """Shows up-to-date message and returns when already on latest version."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.5.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={"tag_name": "v1.5.0", "assets": []},
    )

    runner = CliRunner()
    result = runner.invoke(upgrade, [])

    assert result.exit_code == 0
    assert "latest version" in result.output.lower() or "1.5.0" in result.output


@pytest.mark.unit
def test_upgrade_exits_on_unsupported_platform(mocker):
    """Exits with code 1 when platform is unsupported."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={"tag_name": "v1.5.0", "assets": []},
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=None)

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    assert result.exit_code == 1
    assert "Unsupported platform" in result.output


@pytest.mark.unit
def test_upgrade_exits_when_binary_not_found_for_platform(mocker):
    """Exits with code 1 when no asset matches the current platform binary name."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={"tag_name": "v1.5.0", "assets": [{"name": "devo-windows-amd64.zip", "browser_download_url": "https://..."}]},
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    assert result.exit_code == 1
    assert "Binary not found" in result.output or "not found" in result.output.lower()


@pytest.mark.unit
def test_upgrade_exits_when_cannot_determine_executable_path(mocker):
    """Exits with code 1 when get_executable_path returns None."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={
            "tag_name": "v1.5.0",
            "assets": [{"name": "devo-linux-amd64", "browser_download_url": "https://example.com/devo-linux-amd64"}],
        },
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=None)

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    assert result.exit_code == 1
    assert "executable location" in result.output or "install manually" in result.output.lower()


@pytest.mark.unit
def test_upgrade_exits_when_no_write_permission(mocker, tmp_path):
    """Exits with code 1 when no write permission to executable's parent dir."""
    current_exe = tmp_path / "bin" / "devo"
    current_exe.parent.mkdir()
    current_exe.write_text("binary")

    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={
            "tag_name": "v1.5.0",
            "assets": [{"name": "devo-linux-amd64", "browser_download_url": "https://example.com/devo-linux-amd64"}],
        },
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=current_exe)
    mocker.patch("os.access", return_value=False)

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    assert result.exit_code == 1
    assert "write permission" in result.output or "permission" in result.output.lower()


@pytest.mark.unit
def test_upgrade_user_cancels_confirmation(mocker, tmp_path):
    """User declining confirmation cancels the upgrade."""
    current_exe = tmp_path / "devo"
    current_exe.write_text("binary")

    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={
            "tag_name": "v1.5.0",
            "assets": [{"name": "devo-linux-amd64", "browser_download_url": "https://example.com/devo-linux-amd64"}],
        },
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=current_exe)
    mocker.patch("os.access", return_value=True)

    runner = CliRunner()
    result = runner.invoke(upgrade, [], input="n\n")  # User says no

    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()


@pytest.mark.unit
def test_upgrade_unknown_current_version_shows_warning(mocker):
    """Shows warning when current version is 'unknown'."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="unknown")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={"tag_name": "v1.5.0", "assets": []},
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=None)

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    # Should show warning about unknown version
    assert "Warning" in result.output or "version" in result.output.lower()


@pytest.mark.unit
def test_upgrade_keyboard_interrupt_handled(mocker):
    """KeyboardInterrupt is caught and exits gracefully."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", side_effect=KeyboardInterrupt())

    runner = CliRunner()
    result = runner.invoke(upgrade, [])

    assert result.exit_code == 1
    assert "cancelled" in result.output.lower()


@pytest.mark.unit
def test_upgrade_general_exception_handled(mocker):
    """General exceptions are caught and shown as error."""
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", side_effect=Exception("unexpected error"))

    runner = CliRunner()
    result = runner.invoke(upgrade, [])

    assert result.exit_code == 1
    assert "unexpected error" in result.output or "Error" in result.output


@pytest.mark.unit
def test_upgrade_successful_install_exits_0(mocker, tmp_path):
    """Full upgrade flow succeeds: download, verify, install, exit 0."""
    current_exe = tmp_path / "devo"
    current_exe.write_text("old binary")

    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={
            "tag_name": "v1.5.0",
            "assets": [{"name": "devo-linux-amd64", "browser_download_url": "https://example.com/devo-linux-amd64"}],
        },
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=current_exe)
    mocker.patch("os.access", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary", return_value=True)
    # os._exit raises SystemExit so Click runner can catch it
    mocker.patch("os._exit", side_effect=SystemExit(0))

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    assert result.exit_code == 0


@pytest.mark.unit
def test_upgrade_replace_binary_fails_exits_1(mocker, tmp_path):
    """Exits with code 1 when replace_binary returns False."""
    current_exe = tmp_path / "devo"
    current_exe.write_text("binary")

    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.0.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={
            "tag_name": "v1.5.0",
            "assets": [{"name": "devo-linux-amd64", "browser_download_url": "https://example.com/devo-linux-amd64"}],
        },
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=current_exe)
    mocker.patch("os.access", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary", return_value=False)

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    assert result.exit_code == 1


@pytest.mark.unit
def test_determine_archive_suffix_other_platform():
    """Any platform other than windows/darwin returns .tmp."""
    assert _determine_archive_suffix("freebsd") == ".tmp"
    assert _determine_archive_suffix("") == ".tmp"


@pytest.mark.unit
def test_download_and_verify_success_returns_path(mocker, tmp_path):
    """Returns a Path when download and verification both succeed."""
    tmp_file = tmp_path / "binary.tmp"
    tmp_file.write_text("content")

    mock_ntf = MagicMock()
    mock_ntf.__enter__ = MagicMock(return_value=MagicMock(name=str(tmp_file)))
    mock_ntf.__exit__ = MagicMock(return_value=False)
    mocker.patch("tempfile.NamedTemporaryFile", return_value=mock_ntf)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary", return_value=True)

    result = _download_and_verify("https://example.com/binary", None)

    assert result is not None
    assert isinstance(result, Path)


@pytest.mark.unit
def test_upgrade_force_flag_reinstalls_same_version(mocker, tmp_path):
    """--force reinstalls even when already on latest version."""
    current_exe = tmp_path / "devo"
    current_exe.write_text("binary")

    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_current_version", return_value="1.5.0")
    mocker.patch(
        "cli_tool.commands.upgrade.commands.upgrade.get_latest_release",
        return_value={
            "tag_name": "v1.5.0",
            "assets": [{"name": "devo-linux-amd64", "browser_download_url": "https://example.com/devo-linux-amd64"}],
        },
    )
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.detect_platform", return_value=("linux", "amd64"))
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_binary_name", return_value="devo-linux-amd64")
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.get_executable_path", return_value=current_exe)
    mocker.patch("os.access", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.download_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.verify_binary", return_value=True)
    mocker.patch("cli_tool.commands.upgrade.commands.upgrade.replace_binary", return_value=True)
    mocker.patch("os._exit", side_effect=SystemExit(0))

    runner = CliRunner()
    result = runner.invoke(upgrade, ["--force"])

    # Should attempt install even though already latest
    assert result.exit_code == 0
