"""Tests for set_default AWS profile command."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.aws_login.commands.set_default import (
    _format_source_label,
    _get_shell_config,
    _resolve_and_validate_profile,
    _set_unix_profile,
    _set_windows_profile,
    _update_shell_config_file,
    _write_default_credentials,
    set_default_profile,
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


# ---------------------------------------------------------------------------
# _set_windows_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_set_windows_profile_success(monkeypatch, mocker):
    """setx succeeds — prints confirmation message."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    _set_windows_profile("dev")

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "setx" in call_args
    assert "AWS_PROFILE" in call_args
    assert "dev" in call_args


@pytest.mark.unit
def test_set_windows_profile_failure(mocker):
    """setx fails — prints fallback message."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="Access denied"))

    # Should not raise
    _set_windows_profile("dev")


@pytest.mark.unit
def test_set_windows_profile_exception(mocker):
    """setx raises exception — caught gracefully."""
    mocker.patch("subprocess.run", side_effect=Exception("setx not found"))

    # Should not raise
    _set_windows_profile("dev")


# ---------------------------------------------------------------------------
# _set_unix_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_set_unix_profile_uses_shell_env(tmp_path, monkeypatch, mocker):
    """_set_unix_profile reads $SHELL to pick config file."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    rc = tmp_path / ".zshrc"
    rc.write_text("# zsh config\n")

    mock_update = mocker.patch("cli_tool.commands.aws_login.commands.set_default._update_shell_config_file")

    _set_unix_profile("dev")

    mock_update.assert_called_once()
    config_file_arg = mock_update.call_args[0][0]
    assert ".zshrc" in str(config_file_arg)


@pytest.mark.unit
def test_set_unix_profile_defaults_to_bash_when_no_shell(tmp_path, monkeypatch, mocker):
    """Falls back to .bashrc when SHELL env var is not set."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("SHELL", raising=False)

    mock_update = mocker.patch("cli_tool.commands.aws_login.commands.set_default._update_shell_config_file")

    _set_unix_profile("dev")

    mock_update.assert_called_once()
    config_file_arg = mock_update.call_args[0][0]
    assert ".bashrc" in str(config_file_arg)


@pytest.mark.unit
def test_set_unix_profile_uses_fish_config(tmp_path, monkeypatch, mocker):
    """Uses fish config.fish when $SHELL is fish."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SHELL", "/usr/bin/fish")

    mock_update = mocker.patch("cli_tool.commands.aws_login.commands.set_default._update_shell_config_file")

    _set_unix_profile("dev")

    mock_update.assert_called_once()
    export_line_arg = mock_update.call_args[0][1]
    assert "set -gx" in export_line_arg
    assert "dev" in export_line_arg


# ---------------------------------------------------------------------------
# set_default_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_set_default_profile_exits_when_no_profiles(monkeypatch):
    """Exits with code 1 when no AWS profiles found."""
    monkeypatch.setattr("cli_tool.commands.aws_login.commands.set_default.list_aws_profiles", lambda: [])

    with pytest.raises(SystemExit) as exc_info:
        set_default_profile()

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_set_default_profile_exits_when_credentials_unavailable(monkeypatch):
    """Exits with code 1 when credentials are not available."""
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.list_aws_profiles",
        lambda: [("dev", "sso")],
    )
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.check_profile_credentials_available",
        lambda profile: (False, "Token expired"),
    )

    with pytest.raises(SystemExit) as exc_info:
        set_default_profile("dev")

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_set_default_profile_sets_env_variable(monkeypatch, mocker):
    """Sets AWS_PROFILE environment variable when set_env=True."""
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.list_aws_profiles",
        lambda: [("dev", "sso")],
    )
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.check_profile_credentials_available",
        lambda profile: (True, None),
    )
    monkeypatch.setattr("os.name", "posix")
    mocker.patch("cli_tool.commands.aws_login.commands.set_default._set_unix_profile")
    mocker.patch("cli_tool.commands.aws_login.commands.set_default._write_default_credentials")

    set_default_profile("dev", set_env=True)

    assert os.environ.get("AWS_PROFILE") == "dev"


@pytest.mark.unit
def test_set_default_profile_does_not_set_env_variable_by_default(monkeypatch, mocker):
    """Does not set AWS_PROFILE env var or call shell-config functions by default."""
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.list_aws_profiles",
        lambda: [("dev", "sso")],
    )
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.check_profile_credentials_available",
        lambda profile: (True, None),
    )
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.get_config_value",
        lambda key, default=None: False,
    )
    mock_unix = mocker.patch("cli_tool.commands.aws_login.commands.set_default._set_unix_profile")
    mock_windows = mocker.patch("cli_tool.commands.aws_login.commands.set_default._set_windows_profile")
    mocker.patch("cli_tool.commands.aws_login.commands.set_default._write_default_credentials")

    set_default_profile("dev")

    mock_unix.assert_not_called()
    mock_windows.assert_not_called()


@pytest.mark.unit
def test_set_default_profile_calls_windows_on_nt(monkeypatch, mocker):
    """Calls _set_windows_profile on Windows (os.name == 'nt') when set_env=True."""
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.list_aws_profiles",
        lambda: [("dev", "sso")],
    )
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.check_profile_credentials_available",
        lambda profile: (True, None),
    )
    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setenv("SHELL", "")  # Not git bash

    mock_windows = mocker.patch("cli_tool.commands.aws_login.commands.set_default._set_windows_profile")
    mocker.patch("cli_tool.commands.aws_login.commands.set_default._write_default_credentials")

    set_default_profile("dev", set_env=True)

    mock_windows.assert_called_once_with("dev")


@pytest.mark.unit
def test_set_default_profile_calls_unix_on_posix(monkeypatch, mocker):
    """Calls _set_unix_profile on Unix/Linux/macOS when set_env=True."""
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.list_aws_profiles",
        lambda: [("dev", "sso")],
    )
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.check_profile_credentials_available",
        lambda profile: (True, None),
    )
    monkeypatch.setattr("os.name", "posix")

    mock_unix = mocker.patch("cli_tool.commands.aws_login.commands.set_default._set_unix_profile")
    mocker.patch("cli_tool.commands.aws_login.commands.set_default._write_default_credentials")

    set_default_profile("dev", set_env=True)

    mock_unix.assert_called_once_with("dev")


# ---------------------------------------------------------------------------
# _select_profile_interactively
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_profile_interactively_valid_choice(mocker):
    """Returns profile name for a valid numeric selection."""
    from cli_tool.commands.aws_login.commands.set_default import _select_profile_interactively

    profiles = [("dev", "sso"), ("prod", "static")]
    mocker.patch("click.prompt", return_value=2)

    result = _select_profile_interactively(profiles)

    assert result == "prod"


@pytest.mark.unit
def test_select_profile_interactively_invalid_choice_exits(mocker):
    """Calls sys.exit(1) on an out-of-range selection."""
    from cli_tool.commands.aws_login.commands.set_default import _select_profile_interactively

    profiles = [("dev", "sso")]
    mocker.patch("click.prompt", return_value=99)

    with pytest.raises(SystemExit) as exc_info:
        _select_profile_interactively(profiles)

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_select_profile_interactively_zero_choice_exits(mocker):
    """Calls sys.exit(1) when user enters 0."""
    from cli_tool.commands.aws_login.commands.set_default import _select_profile_interactively

    profiles = [("dev", "sso")]
    mocker.patch("click.prompt", return_value=0)

    with pytest.raises(SystemExit) as exc_info:
        _select_profile_interactively(profiles)

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_select_profile_interactively_first_profile(mocker):
    """Returns the first profile when user selects 1."""
    from cli_tool.commands.aws_login.commands.set_default import _select_profile_interactively

    profiles = [("alpha", "sso"), ("beta", "both")]
    mocker.patch("click.prompt", return_value=1)

    result = _select_profile_interactively(profiles)

    assert result == "alpha"


# ---------------------------------------------------------------------------
# set_default_profile — git-bash branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_set_default_profile_git_bash_calls_unix_profile(monkeypatch, mocker):
    """On Windows with Git Bash ($SHELL ends with 'bash'), calls _set_unix_profile when set_env=True."""
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.list_aws_profiles",
        lambda: [("dev", "sso")],
    )
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.check_profile_credentials_available",
        lambda profile: (True, None),
    )
    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setenv("SHELL", "/usr/bin/bash")  # Git Bash

    mock_unix = mocker.patch("cli_tool.commands.aws_login.commands.set_default._set_unix_profile")
    mocker.patch("cli_tool.commands.aws_login.commands.set_default._write_default_credentials")

    set_default_profile("dev", set_env=True)

    mock_unix.assert_called_once_with("dev")


# ---------------------------------------------------------------------------
# _write_default_credentials — additional branches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_default_credentials_no_expiration_in_result(monkeypatch):
    """Does not print expiration line when result has no expiration."""
    mock_write = MagicMock(return_value={"expiration": None})
    monkeypatch.setattr(
        "cli_tool.commands.aws_login.commands.set_default.write_default_credentials",
        mock_write,
    )
    # Should not raise
    _write_default_credentials("dev")
    mock_write.assert_called_once_with("dev")


# ---------------------------------------------------------------------------
# Additional _format_source_label unit marker tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_format_source_label_sso():
    """sso maps to cyan label."""
    assert "cyan" in _format_source_label("sso")


@pytest.mark.unit
def test_format_source_label_static():
    """static maps to yellow label."""
    assert "yellow" in _format_source_label("static")


@pytest.mark.unit
def test_format_source_label_both():
    """both maps to green label."""
    assert "green" in _format_source_label("both")


@pytest.mark.unit
def test_format_source_label_unknown():
    """Unknown source maps to dim label containing the source text."""
    result = _format_source_label("custom-type")
    assert "dim" in result
    assert "custom-type" in result


# ---------------------------------------------------------------------------
# _update_shell_config_file — error path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_update_shell_config_file_handles_read_error(tmp_path, monkeypatch, mocker):
    """Catches and handles exception when file read fails after exists check."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    rc = tmp_path / ".bashrc"
    rc.write_text("# config\n")

    mocker.patch("pathlib.Path.read_text", side_effect=OSError("read error"))

    # Should not raise — error is caught internally
    _update_shell_config_file(rc, "export AWS_PROFILE=dev")
