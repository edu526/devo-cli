"""Unit tests for cli_tool/commands/aws_login/command.py.

Covers the following previously-missing lines:
- _warn_expiry: lines 33-36 (warn when expiring within 30 min)
- _check_credentials_via_cli: lines 54-56 (warn when CLI fails and in_default=True)
- _check_default_credentials_expiry: line 63 (early return when credentials file missing)
- _check_default_credentials_expiry: lines 77-78 (exception swallowed)
- aws_login group: line 110 (perform_login(None) when no subcommand)
- configure_cmd: lines 150-155 (configure_sso_profile success path)
- configure_cmd: sys.exit(1) when configure_sso_profile returns None
- refresh_cmd: line 166
- set_default_cmd: line 182
"""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from cli_tool.commands.aws_login.command import (
    _check_credentials_via_cli,
    _check_default_credentials_expiry,
    _set_default_hint,
    _warn_expiry,
    aws_login,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_iso(minutes: int) -> str:
    """Return an ISO-8601 UTC string that is *minutes* from now."""
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _past_iso(minutes: int) -> str:
    """Return an ISO-8601 UTC string that was *minutes* ago."""
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


# ---------------------------------------------------------------------------
# _warn_expiry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWarnExpiry:
    def test_warn_expiry_soon_prints_warning(self, mocker):
        """Covers lines 33-36: prints warning when expiry is < 30 minutes away."""
        mock_print = mocker.patch("cli_tool.commands.aws_login.command.console")
        expiry_str = _future_iso(10)  # 10 minutes in the future

        _warn_expiry(expiry_str)

        assert mock_print.print.called
        call_args = [str(call) for call in mock_print.print.call_args_list]
        combined = " ".join(call_args)
        assert "expire" in combined.lower() or "min" in combined.lower()

    def test_warn_expiry_far_future_no_warning(self, mocker):
        """No warning printed when expiry is far in the future (> 30 min)."""
        mock_print = mocker.patch("cli_tool.commands.aws_login.command.console")
        expiry_str = _future_iso(120)  # 2 hours away

        _warn_expiry(expiry_str)

        # console.print should NOT have been called for an expiry warning
        assert not mock_print.print.called

    def test_warn_expiry_already_expired(self, mocker):
        """Expired credentials trigger a different message path (lines 30-32)."""
        mock_print = mocker.patch("cli_tool.commands.aws_login.command.console")
        expiry_str = _past_iso(5)  # 5 minutes ago

        _warn_expiry(expiry_str)

        assert mock_print.print.called


# ---------------------------------------------------------------------------
# _check_credentials_via_cli
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCheckCredentialsViaCli:
    def test_returncode_nonzero_in_default_true_prints_warning(self, mocker):
        """Covers lines 54-56: warn when CLI fails and in_default=True."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mock_console = mocker.patch("cli_tool.commands.aws_login.command.console")

        _check_credentials_via_cli(in_default=True)

        mock_run.assert_called_once()
        assert mock_console.print.called
        call_args = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "expired" in call_args.lower() or "may be expired" in call_args.lower()

    def test_returncode_nonzero_in_default_false_no_warning(self, mocker):
        """When CLI fails but in_default=False, no warning is printed."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mock_console = mocker.patch("cli_tool.commands.aws_login.command.console")

        _check_credentials_via_cli(in_default=False)

        mock_run.assert_called_once()
        assert not mock_console.print.called

    def test_returncode_zero_with_expiry_calls_warn_expiry(self, mocker):
        """When CLI succeeds and Expiration is present, _warn_expiry is invoked."""
        import json

        expiry_str = _future_iso(10)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"Expiration": expiry_str}),
        )
        mock_warn = mocker.patch("cli_tool.commands.aws_login.command._warn_expiry")

        _check_credentials_via_cli(in_default=False)

        mock_warn.assert_called_once_with(expiry_str)


# ---------------------------------------------------------------------------
# _check_default_credentials_expiry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCheckDefaultCredentialsExpiry:
    def test_returns_early_when_credentials_file_missing(self, mocker, tmp_path):
        """Covers line 63: early return when ~/.aws/credentials does not exist."""
        # Point Path.home() to a directory that has no .aws/credentials
        mocker.patch("cli_tool.commands.aws_login.command.Path").home.return_value = tmp_path
        mock_cli = mocker.patch("cli_tool.commands.aws_login.command._check_credentials_via_cli")

        _check_default_credentials_expiry()

        mock_cli.assert_not_called()

    def test_exception_is_swallowed(self, mocker, tmp_path):
        """Covers lines 77-78: exceptions during file reading are silently ignored."""
        # Create the credentials file so the early-return guard is bypassed
        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir()
        creds_file = aws_dir / "credentials"
        creds_file.write_text("[default]\naws_access_key_id = FAKE\n")

        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        # Make open() raise to exercise the except block
        mocker.patch("builtins.open", side_effect=OSError("permission denied"))

        # Should not raise
        _check_default_credentials_expiry()


# ---------------------------------------------------------------------------
# aws_login group (CLI)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAwsLoginGroup:
    def _setup_mocks(self, mocker):
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=True)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")

    def test_no_subcommand_calls_perform_login_none(self, mocker):
        """Covers line 110: perform_login(None) is called when no subcommand given."""
        self._setup_mocks(mocker)
        mock_login = mocker.patch("cli_tool.commands.aws_login.command.perform_login")

        runner = CliRunner()
        result = runner.invoke(aws_login, [])

        assert result.exit_code == 0
        mock_login.assert_called_once_with(None)

    def test_subcommand_does_not_call_perform_login(self, mocker):
        """When a subcommand is given, the group itself does not call perform_login."""
        self._setup_mocks(mocker)
        mock_login = mocker.patch("cli_tool.commands.aws_login.command.perform_login")
        mock_refresh = mocker.patch("cli_tool.commands.aws_login.command.refresh_all_profiles")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["refresh"])

        assert result.exit_code == 0
        mock_refresh.assert_called_once()
        # perform_login must not have been called by the group itself
        mock_login.assert_not_called()

    def test_check_aws_cli_false_exits(self, mocker):
        """When check_aws_cli returns False the command exits with code 1."""
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=False)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")

        runner = CliRunner()
        result = runner.invoke(aws_login, [])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# configure_cmd
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConfigureCmd:
    def _base_mocks(self, mocker):
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=True)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")

    def test_configure_success_calls_perform_login(self, mocker):
        """Covers lines 150-155: successful configure triggers perform_login."""
        self._base_mocks(mocker)
        mocker.patch(
            "cli_tool.commands.aws_login.command.configure_sso_profile",
            return_value="my-profile",
        )
        mock_login = mocker.patch("cli_tool.commands.aws_login.command.perform_login")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["configure"])

        assert result.exit_code == 0
        mock_login.assert_called_once_with("my-profile")

    def test_configure_returns_none_exits_with_1(self, mocker):
        """When configure_sso_profile returns None the command sys.exit(1)."""
        self._base_mocks(mocker)
        mocker.patch(
            "cli_tool.commands.aws_login.command.configure_sso_profile",
            return_value=None,
        )
        mock_login = mocker.patch("cli_tool.commands.aws_login.command.perform_login")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["configure"])

        assert result.exit_code == 1
        mock_login.assert_not_called()


# ---------------------------------------------------------------------------
# refresh_cmd
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRefreshCmd:
    def test_refresh_calls_refresh_all_profiles(self, mocker):
        """Covers line 166: refresh subcommand delegates to refresh_all_profiles."""
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=True)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")
        mock_refresh = mocker.patch("cli_tool.commands.aws_login.command.refresh_all_profiles")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["refresh"])

        assert result.exit_code == 0
        mock_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# set_default_cmd
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSetDefaultCmd:
    def test_set_default_calls_set_default_profile(self, mocker):
        """set-default subcommand delegates to set_default_profile with set_env=None (no flag)."""
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=True)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")
        mock_set_default = mocker.patch("cli_tool.commands.aws_login.command.set_default_profile")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["set-default", "production"])

        assert result.exit_code == 0
        mock_set_default.assert_called_once_with("production", set_env=None)

    def test_set_default_without_profile_passes_none(self, mocker):
        """set-default with no argument passes None profile and set_env=None."""
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=True)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")
        mock_set_default = mocker.patch("cli_tool.commands.aws_login.command.set_default_profile")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["set-default"])

        assert result.exit_code == 0
        mock_set_default.assert_called_once_with(None, set_env=None)

    def test_set_default_with_set_env_flag(self, mocker):
        """--set-env flag passes set_env=True to set_default_profile."""
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=True)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")
        mock_set_default = mocker.patch("cli_tool.commands.aws_login.command.set_default_profile")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["set-default", "production", "--set-env"])

        assert result.exit_code == 0
        mock_set_default.assert_called_once_with("production", set_env=True)


# ---------------------------------------------------------------------------
# _check_default_credentials_expiry — loop body (lines 70-74)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCheckDefaultCredentialsExpiryLoopBody:
    def test_reads_default_section_and_breaks_at_next_section(self, mocker, tmp_path):
        """Lines 70-74: loop reads [default] section, then breaks at the next section."""
        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir()
        creds_file = aws_dir / "credentials"
        creds_file.write_text("[default]\naws_access_key_id = FAKEKEY\n[other]\nkey = val\n")

        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        mock_check = mocker.patch("cli_tool.commands.aws_login.command._check_credentials_via_cli")

        _check_default_credentials_expiry()

        # in_default should have been True when [other] was seen → break
        mock_check.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# list_cmd — list_profiles() call (line 135)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListCmd:
    def test_list_cmd_calls_list_profiles(self, mocker):
        """Line 135: list_cmd invokes list_profiles()."""
        mocker.patch("cli_tool.commands.aws_login.command.check_aws_cli", return_value=True)
        mocker.patch("cli_tool.commands.aws_login.command._check_default_credentials_expiry")
        mock_list = mocker.patch("cli_tool.commands.aws_login.command.list_profiles")

        runner = CliRunner()
        result = runner.invoke(aws_login, ["list"])

        assert result.exit_code == 0
        mock_list.assert_called_once()


# ---------------------------------------------------------------------------
# _set_default_hint
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSetDefaultHint:
    def test_hint_without_configured_profile(self, mocker):
        """Returns generic command when no default profile is in config."""
        mocker.patch("cli_tool.commands.aws_login.command.get_config_value", return_value=None)

        hint = _set_default_hint()

        assert "devo aws-login set-default" in hint
        # Should not contain a specific profile name suffix
        assert hint.count("set-default") == 1
        assert "set-default " not in hint  # no profile appended

    def test_hint_with_configured_profile(self, mocker):
        """Returns command with specific profile name when default is configured."""
        mocker.patch("cli_tool.commands.aws_login.command.get_config_value", return_value="production")

        hint = _set_default_hint()

        assert "devo aws-login set-default production" in hint

    def test_hint_is_used_in_warn_expiry(self, mocker):
        """_warn_expiry uses the dynamic hint when credentials are expiring."""
        mocker.patch("cli_tool.commands.aws_login.command.get_config_value", return_value="prod")
        mock_console = mocker.patch("cli_tool.commands.aws_login.command.console")
        expiry_str = _future_iso(5)

        _warn_expiry(expiry_str)

        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "prod" in printed
