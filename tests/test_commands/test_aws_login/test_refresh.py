"""Unit tests for cli_tool.commands.aws_login.commands.refresh module."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call

import pytest

from cli_tool.commands.aws_login.commands.refresh import _refresh_session, refresh_all_profiles

# ---------------------------------------------------------------------------
# _refresh_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_refresh_session_success_all_verified(mocker):
    """Successful session refresh verifies all profiles."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mock_get_config = mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config")
    mock_get_config.return_value = {"sso_session": "my-session"}

    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials")
    mock_verify.return_value = {"account": "123456789012", "arn": "arn:aws:iam::123456789012:role/Dev"}

    ok, verified, failed = _refresh_session("my-session", ["dev", "staging"])

    assert ok is True
    assert verified == 2
    assert failed == 0


@pytest.mark.unit
def test_refresh_session_uses_sso_session_login_cmd(mocker):
    """When profile has sso_session, login command uses --sso-session flag."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value={"sso_session": "my-sso"})
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", return_value=True)

    _refresh_session("my-sso", ["dev"])

    call_args = mock_run.call_args[0][0]
    assert "--sso-session" in call_args
    assert "my-sso" in call_args


@pytest.mark.unit
def test_refresh_session_uses_profile_login_cmd_when_no_sso_session(mocker):
    """When profile has no sso_session, login command uses --profile flag."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value={"sso_start_url": "https://example.com/start"})
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", return_value=True)

    _refresh_session("some-key", ["dev"])

    call_args = mock_run.call_args[0][0]
    assert "--profile" in call_args
    assert "dev" in call_args


@pytest.mark.unit
def test_refresh_session_uses_profile_login_cmd_when_config_is_none(mocker):
    """When get_profile_config returns None, login command uses --profile flag."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", return_value=True)

    _refresh_session("some-key", ["dev"])

    call_args = mock_run.call_args[0][0]
    assert "--profile" in call_args


@pytest.mark.unit
def test_refresh_session_returns_false_on_nonzero_returncode(mocker):
    """Non-zero return code from aws sso login returns failure tuple."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=1)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)

    ok, verified, failed = _refresh_session("key", ["dev", "staging"])

    assert ok is False
    assert verified == 0
    assert failed == 2


@pytest.mark.unit
def test_refresh_session_timeout_returns_false(mocker):
    """subprocess.TimeoutExpired results in failure tuple."""
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("aws", 120))
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)

    ok, verified, failed = _refresh_session("key", ["dev"])

    assert ok is False
    assert verified == 0
    assert failed == 1


@pytest.mark.unit
def test_refresh_session_keyboard_interrupt_exits(mocker):
    """KeyboardInterrupt causes sys.exit(1)."""
    mocker.patch("subprocess.run", side_effect=KeyboardInterrupt())
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)

    with pytest.raises(SystemExit) as exc_info:
        _refresh_session("key", ["dev"])

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_refresh_session_partial_verification_failure(mocker):
    """Some profiles verified, some fail — counts are correct."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value={"sso_session": "s"})

    verify_results = [True, None, True]  # None counts as failed (falsy)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", side_effect=verify_results)

    ok, verified, failed = _refresh_session("s", ["dev", "staging", "prod"])

    assert ok is True
    assert verified == 2
    assert failed == 1


# ---------------------------------------------------------------------------
# refresh_all_profiles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_refresh_all_profiles_no_profiles_exits_0(mocker):
    """When no AWS profiles exist, sys.exit(0) is called."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=[])

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_all_valid_exits_0(mocker):
    """When all profiles are valid, sys.exit(0) is called."""
    profiles = [("dev", "sso"), ("prod", "sso")]
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=profiles)

    future = datetime.now(timezone.utc) + timedelta(hours=8)
    # needs_refresh=False, expiration=future, reason="Valid"
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(False, future, "Valid"),
    )

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_all_valid_no_expiration_exits_0(mocker):
    """When all profiles are valid but have no expiration, sys.exit(0) is called."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=[("dev", "static")])
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(False, None, "Not an SSO profile"),
    )

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_user_cancels(mocker):
    """When user declines confirmation, sys.exit(0) is called."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=[("dev", "sso")])
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=False)

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_refreshes_grouped_sessions(mocker):
    """Profiles sharing a session key are grouped and refreshed together."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso"), ("staging", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_session": "shared-session"},
    )

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 2, 0))

    refresh_all_profiles()

    # Both profiles should be grouped under same session key
    mock_refresh.assert_called_once()
    args = mock_refresh.call_args
    assert args[0][0] == "shared-session"
    assert set(args[0][1]) == {"dev", "staging"}


@pytest.mark.unit
def test_refresh_all_profiles_profile_with_no_sso_key_skipped(mocker):
    """Profiles without sso_session or sso_start_url are not grouped for refresh."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "static")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"region": "us-east-1"},  # No sso_session or sso_start_url
    )

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session")

    refresh_all_profiles()

    mock_refresh.assert_not_called()


@pytest.mark.unit
def test_refresh_all_profiles_profile_config_none_skipped(mocker):
    """Profiles where get_profile_config returns None are skipped."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session")

    refresh_all_profiles()

    mock_refresh.assert_not_called()


@pytest.mark.unit
def test_refresh_all_profiles_uses_sso_start_url_as_key(mocker):
    """When profile has sso_start_url but no sso_session, uses URL as group key."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_start_url": "https://example.awsapps.com/start"},
    )

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 1, 0))

    refresh_all_profiles()

    mock_refresh.assert_called_once()
    assert mock_refresh.call_args[0][0] == "https://example.awsapps.com/start"


@pytest.mark.unit
def test_refresh_all_profiles_multiple_sessions_multiple_calls(mocker):
    """Different session keys result in multiple _refresh_session calls."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso"), ("prod", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)

    # Different sessions for each profile
    def mock_get_config(profile_name):
        if profile_name == "dev":
            return {"sso_session": "dev-session"}
        return {"sso_session": "prod-session"}

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", side_effect=mock_get_config)
    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 1, 0))

    refresh_all_profiles()

    assert mock_refresh.call_count == 2


@pytest.mark.unit
def test_refresh_all_profiles_summary_shows_failures(mocker, capsys):
    """Summary shows failure count when some profiles fail."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_session": "s"},
    )
    # Returns 0 verified, 1 failed
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(False, 0, 1))

    # Should not raise
    refresh_all_profiles()
