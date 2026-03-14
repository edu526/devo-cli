"""Tests for set_default AWS profile command."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.aws_login.commands.set_default import (
    _format_source_label,
    _get_shell_config,
    _resolve_and_validate_profile,
    _update_shell_config_file,
    _write_default_credentials,
)

# ---------------------------------------------------------------------------
# _format_source_label
# ---------------------------------------------------------------------------


def test_format_source_label_known_values():
    assert "cyan" in _format_source_label("sso")
    assert "yellow" in _format_source_label("static")
    assert "green" in _format_source_label("both")


def test_format_source_label_unknown_falls_back_to_dim():
    result = _format_source_label("custom")
    assert "dim" in result
    assert "custom" in result


# ---------------------------------------------------------------------------
# _get_shell_config
# ---------------------------------------------------------------------------


def test_get_shell_config_bash():
    config_file, export_line = _get_shell_config("bash", "my-profile")
    assert config_file.name == ".bashrc"
    assert "my-profile" in export_line
    assert "AWS_PROFILE" in export_line


def test_get_shell_config_zsh():
    config_file, export_line = _get_shell_config("zsh", "dev")
    assert config_file.name == ".zshrc"
    assert "dev" in export_line


def test_get_shell_config_fish():
    config_file, export_line = _get_shell_config("fish", "prod")
    assert "config.fish" in str(config_file)
    assert "prod" in export_line
    assert "set -gx" in export_line


def test_get_shell_config_unknown_shell_falls_back_to_bash():
    config_file, export_line = _get_shell_config("tcsh", "my-profile")
    assert config_file.name == ".bashrc"
    assert "my-profile" in export_line


def test_get_shell_config_path_is_under_home():
    config_file, _ = _get_shell_config("bash", "x")
    assert str(config_file).startswith(str(Path.home()))


# ---------------------------------------------------------------------------
# _update_shell_config_file
# ---------------------------------------------------------------------------


def test_update_shell_config_file_not_exists(tmp_path):
    """Non-existent config file is skipped silently."""
    non_existent = tmp_path / ".bashrc"
    _update_shell_config_file(non_existent, "export AWS_PROFILE=foo")
    # Should not raise and not create the file
    assert not non_existent.exists()


def test_update_shell_config_file_updates_existing_export(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / ".bashrc"
    rc.write_text("export AWS_PROFILE=old-profile\n")

    _update_shell_config_file(rc, "export AWS_PROFILE=new-profile")

    content = rc.read_text()
    assert "new-profile" in content
    assert "old-profile" not in content


def test_update_shell_config_file_appends_when_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / ".bashrc"
    rc.write_text("# some config\nalias ll='ls -la'\n")

    _update_shell_config_file(rc, "export AWS_PROFILE=dev")

    content = rc.read_text()
    assert "export AWS_PROFILE=dev" in content
    assert "# some config" in content  # original content preserved


def test_update_shell_config_file_updates_fish_set_gx(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / "config.fish"
    rc.write_text("set -gx AWS_PROFILE old\n")

    _update_shell_config_file(rc, "set -gx AWS_PROFILE new")

    content = rc.read_text()
    assert "new" in content
    assert "old" not in content


def test_update_shell_config_file_rejects_path_outside_home(tmp_path, monkeypatch):
    """Path outside home directory should be caught and not written."""
    different_home = tmp_path / "other_home"
    different_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: different_home)

    # Create a file inside tmp_path (outside "home")
    rc = tmp_path / ".bashrc"
    rc.write_text("# config\n")

    # Should not raise, but the error is caught internally
    _update_shell_config_file(rc, "export AWS_PROFILE=foo")
    # File should remain unchanged
    assert rc.read_text() == "# config\n"


# ---------------------------------------------------------------------------
# _resolve_and_validate_profile
# ---------------------------------------------------------------------------

PROFILES = [("dev", "sso"), ("prod", "static"), ("staging", "both")]


def test_resolve_and_validate_returns_valid_profile():
    result = _resolve_and_validate_profile("dev", PROFILES)
    assert result == "dev"


def test_resolve_and_validate_invalid_format_exits(monkeypatch):
    monkeypatch.setattr(sys, "exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    with pytest.raises(SystemExit):
        _resolve_and_validate_profile("invalid profile!", PROFILES)


def test_resolve_and_validate_profile_not_in_list_exits(monkeypatch):
    monkeypatch.setattr(sys, "exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    with pytest.raises(SystemExit):
        _resolve_and_validate_profile("nonexistent", PROFILES)


def test_resolve_and_validate_none_calls_interactive(monkeypatch):
    mock_select = MagicMock(return_value="dev")
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default._select_profile_interactively",
        mock_select,
    )
    result = _resolve_and_validate_profile(None, PROFILES)
    assert result == "dev"
    mock_select.assert_called_once_with(PROFILES)


def test_resolve_and_validate_allows_hyphens_underscores_dots():
    profiles = [("my-profile.name_1", "sso")]
    result = _resolve_and_validate_profile("my-profile.name_1", profiles)
    assert result == "my-profile.name_1"


def test_resolve_and_validate_rejects_too_long_name(monkeypatch):
    monkeypatch.setattr(sys, "exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    long_name = "a" * 129
    with pytest.raises(SystemExit):
        _resolve_and_validate_profile(long_name, [(long_name, "sso")])


# ---------------------------------------------------------------------------
# _write_default_credentials
# ---------------------------------------------------------------------------


def test_write_default_credentials_with_expiration(monkeypatch):
    mock_write = MagicMock(return_value={"expiration": "2026-12-31T00:00:00Z"})
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.write_default_credentials",
        mock_write,
    )
    _write_default_credentials("dev")
    mock_write.assert_called_once_with("dev")


def test_write_default_credentials_without_expiration(monkeypatch):
    mock_write = MagicMock(return_value={"AccessKeyId": "AKIA..."})
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.write_default_credentials",
        mock_write,
    )
    _write_default_credentials("dev")
    mock_write.assert_called_once_with("dev")


def test_write_default_credentials_returns_none(monkeypatch):
    mock_write = MagicMock(return_value=None)
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.write_default_credentials",
        mock_write,
    )
    # Should not raise
    _write_default_credentials("dev")
    mock_write.assert_called_once_with("dev")
