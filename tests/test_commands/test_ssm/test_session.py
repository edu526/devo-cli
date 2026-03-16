"""
Unit tests for cli_tool.commands.ssm.core.session module.

Tests cover SSMSession static methods with all subprocess calls mocked.
"""

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from cli_tool.commands.ssm.core.session import SSMSession

# ============================================================================
# _check_session_manager_plugin
# ============================================================================


@pytest.mark.unit
def test_check_session_manager_plugin_installed(mocker):
    """Returns True when session-manager-plugin command succeeds."""
    mocker.patch("subprocess.run")
    result = SSMSession._check_session_manager_plugin()
    assert result is True


@pytest.mark.unit
def test_check_session_manager_plugin_not_installed_file_not_found(mocker):
    """Returns False when session-manager-plugin raises FileNotFoundError."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)
    result = SSMSession._check_session_manager_plugin()
    assert result is False


@pytest.mark.unit
def test_check_session_manager_plugin_not_installed_timeout(mocker):
    """Returns False when session-manager-plugin times out."""
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("session-manager-plugin", 2))
    result = SSMSession._check_session_manager_plugin()
    assert result is False


# ============================================================================
# _show_plugin_installation_guide
# ============================================================================


@pytest.mark.unit
def test_show_plugin_installation_guide_linux(mocker):
    """Prints Linux installation URL when on Linux."""
    mocker.patch("platform.system", return_value="Linux")
    with patch("cli_tool.commands.ssm.core.session.console") as mock_console:
        SSMSession._show_plugin_installation_guide()
    call_texts = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "Linux" in call_texts or "linux" in call_texts.lower()


@pytest.mark.unit
def test_show_plugin_installation_guide_macos(mocker):
    """Prints macOS installation URL when on Darwin."""
    mocker.patch("platform.system", return_value="Darwin")
    with patch("cli_tool.commands.ssm.core.session.console") as mock_console:
        SSMSession._show_plugin_installation_guide()
    call_texts = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "macOS" in call_texts or "macos" in call_texts.lower()


@pytest.mark.unit
def test_show_plugin_installation_guide_windows(mocker):
    """Prints Windows installation URL when on Windows."""
    mocker.patch("platform.system", return_value="Windows")
    with patch("cli_tool.commands.ssm.core.session.console") as mock_console:
        SSMSession._show_plugin_installation_guide()
    call_texts = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "Windows" in call_texts or "windows" in call_texts.lower()


# ============================================================================
# start_port_forwarding_to_remote
# ============================================================================


@pytest.mark.unit
def test_start_port_forwarding_plugin_not_installed(mocker):
    """Returns 1 and shows guide when plugin is not installed."""
    mocker.patch.object(SSMSession, "_check_session_manager_plugin", return_value=False)
    mock_guide = mocker.patch.object(SSMSession, "_show_plugin_installation_guide")

    result = SSMSession.start_port_forwarding_to_remote(
        bastion="i-abc123",
        host="db.example.com",
        port=5432,
        local_port=15432,
    )

    assert result == 1
    mock_guide.assert_called_once()


@pytest.mark.unit
def test_start_port_forwarding_success(mocker):
    """Returns 0 when AWS SSM session completes successfully."""
    mocker.patch.object(SSMSession, "_check_session_manager_plugin", return_value=True)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession.start_port_forwarding_to_remote(
        bastion="i-abc123",
        host="db.example.com",
        port=5432,
        local_port=15432,
        region="us-east-1",
    )

    assert result == 0


@pytest.mark.unit
def test_start_port_forwarding_with_profile(mocker):
    """Includes --profile in the command when profile is provided."""
    mocker.patch.object(SSMSession, "_check_session_manager_plugin", return_value=True)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    SSMSession.start_port_forwarding_to_remote(
        bastion="i-abc123",
        host="db.example.com",
        port=5432,
        local_port=15432,
        profile="my-profile",
    )

    cmd = mock_run.call_args[0][0]
    assert "--profile" in cmd
    assert "my-profile" in cmd


@pytest.mark.unit
def test_start_port_forwarding_plugin_missing_error_in_stderr(mocker):
    """Returns 1 when stderr indicates session-manager-plugin is missing."""
    mocker.patch.object(SSMSession, "_check_session_manager_plugin", return_value=True)
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "SessionManagerPlugin is not found"
    mock_guide = mocker.patch.object(SSMSession, "_show_plugin_installation_guide")
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession.start_port_forwarding_to_remote(
        bastion="i-abc123",
        host="db.example.com",
        port=5432,
        local_port=15432,
    )

    assert result == 1
    mock_guide.assert_called_once()


@pytest.mark.unit
def test_start_port_forwarding_non_zero_exit_code_prints_stderr(mocker):
    """Prints stderr and returns non-zero code on failure."""
    mocker.patch.object(SSMSession, "_check_session_manager_plugin", return_value=True)
    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stderr = "Some AWS error"
    mocker.patch("subprocess.run", return_value=mock_result)

    with patch("cli_tool.commands.ssm.core.session.console") as mock_console:
        result = SSMSession.start_port_forwarding_to_remote(
            bastion="i-abc123",
            host="db.example.com",
            port=5432,
            local_port=15432,
        )

    assert result == 2
    mock_console.print.assert_called()


@pytest.mark.unit
def test_start_port_forwarding_no_profile_no_profile_flag(mocker):
    """Does not include --profile when profile is None."""
    mocker.patch.object(SSMSession, "_check_session_manager_plugin", return_value=True)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    SSMSession.start_port_forwarding_to_remote(
        bastion="i-abc123",
        host="db.example.com",
        port=5432,
        local_port=15432,
        profile=None,
    )

    cmd = mock_run.call_args[0][0]
    assert "--profile" not in cmd


# ============================================================================
# start_session
# ============================================================================


@pytest.mark.unit
def test_start_session_success(mocker):
    """Returns the subprocess return code for a successful session."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession.start_session("i-abc123", region="us-east-1")

    assert result == 0


@pytest.mark.unit
def test_start_session_with_profile(mocker):
    """Includes --profile in the command when profile is specified."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    SSMSession.start_session("i-abc123", region="us-east-1", profile="dev")

    cmd = mock_run.call_args[0][0]
    assert "--profile" in cmd
    assert "dev" in cmd


@pytest.mark.unit
def test_start_session_without_profile(mocker):
    """Does not include --profile when profile is None."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    SSMSession.start_session("i-abc123")

    cmd = mock_run.call_args[0][0]
    assert "--profile" not in cmd


# ============================================================================
# _is_token_expired
# ============================================================================


@pytest.mark.unit
def test_is_token_expired_returns_false_when_sts_succeeds(mocker):
    """Returns False when get-caller-identity succeeds (tokens valid)."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession._is_token_expired()

    assert result is False


@pytest.mark.unit
def test_is_token_expired_returns_true_on_expired_token_exception(mocker):
    """Returns True when stderr contains ExpiredTokenException."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "An error occurred (ExpiredTokenException) when calling the GetCallerIdentity operation"
    mock_result.stdout = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession._is_token_expired()

    assert result is True


@pytest.mark.unit
def test_is_token_expired_returns_true_on_token_has_expired(mocker):
    """Returns True when error message says 'token has expired'."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "The security token included in the request is expired"
    mock_result.stdout = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession._is_token_expired()

    assert result is True


@pytest.mark.unit
def test_is_token_expired_returns_false_on_unrelated_error(mocker):
    """Returns False when the STS error is not related to token expiry."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Could not connect to the endpoint URL"
    mock_result.stdout = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession._is_token_expired()

    assert result is False


@pytest.mark.unit
def test_is_token_expired_returns_false_on_exception(mocker):
    """Returns False when subprocess raises an exception (e.g. aws not found)."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    result = SSMSession._is_token_expired()

    assert result is False


@pytest.mark.unit
def test_is_token_expired_includes_profile_in_command(mocker):
    """Includes --profile in the sts command when profile is provided."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    SSMSession._is_token_expired(region="eu-west-1", profile="my-profile")

    cmd = mock_run.call_args[0][0]
    assert "--profile" in cmd
    assert "my-profile" in cmd


# ============================================================================
# start_port_forwarding (instance-level forwarding)
# ============================================================================


@pytest.mark.unit
def test_start_port_forwarding_instance_success(mocker):
    """Returns 0 for successful instance-level port forwarding."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mocker.patch("subprocess.run", return_value=mock_result)

    result = SSMSession.start_port_forwarding(
        instance_id="i-abc123",
        remote_port=8080,
        local_port=18080,
        region="us-east-1",
    )

    assert result == 0


@pytest.mark.unit
def test_start_port_forwarding_instance_with_profile(mocker):
    """Includes --profile in instance-level port forwarding command."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    SSMSession.start_port_forwarding(
        instance_id="i-abc123",
        remote_port=8080,
        local_port=18080,
        profile="prod",
    )

    cmd = mock_run.call_args[0][0]
    assert "--profile" in cmd
    assert "prod" in cmd


@pytest.mark.unit
def test_start_port_forwarding_instance_uses_document_name(mocker):
    """Uses AWS-StartPortForwardingSession document name."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    SSMSession.start_port_forwarding("i-abc123", 8080, 18080)

    cmd = mock_run.call_args[0][0]
    assert "AWS-StartPortForwardingSession" in cmd
