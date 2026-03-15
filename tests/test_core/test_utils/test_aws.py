"""Unit tests for cli_tool.core.utils.aws module."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.core.utils.aws import (
    _get_credentials_from_cli,
    check_aws_cli,
    create_aws_client,
    create_aws_session,
    select_profile,
)

# ---------------------------------------------------------------------------
# check_aws_cli
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_check_aws_cli_returns_true_when_installed(mocker):
    """Returns True when AWS CLI is installed and version command succeeds."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="aws-cli/2.0.0 Python/3.9")

    result = check_aws_cli()

    assert result is True
    mock_run.assert_called_once_with(["aws", "--version"], capture_output=True, text=True, timeout=5)


@pytest.mark.unit
def test_check_aws_cli_returns_false_when_not_installed(mocker):
    """Returns False when AWS CLI binary not found."""
    mocker.patch("subprocess.run", side_effect=FileNotFoundError())

    result = check_aws_cli()

    assert result is False


@pytest.mark.unit
def test_check_aws_cli_returns_false_when_version_fails(mocker):
    """Returns False when aws --version returns nonzero exit code."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1))

    result = check_aws_cli()

    assert result is False


@pytest.mark.unit
def test_check_aws_cli_returns_false_on_general_exception(mocker):
    """Returns False on unexpected exceptions."""
    mocker.patch("subprocess.run", side_effect=Exception("unexpected"))

    result = check_aws_cli()

    assert result is False


# ---------------------------------------------------------------------------
# _get_credentials_from_cli
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_credentials_from_cli_returns_credentials(mocker):
    """Returns credential dict when AWS CLI export-credentials succeeds."""
    creds_payload = {
        "AccessKeyId": "AKIATEST",
        "SecretAccessKey": "SECRET",
        "SessionToken": "TOKEN",
        "Expiration": "2099-01-01T00:00:00+00:00",
    }
    mock_result = MagicMock(returncode=0, stdout=json.dumps(creds_payload))
    mocker.patch("subprocess.run", return_value=mock_result)

    result = _get_credentials_from_cli("my-profile")

    assert result is not None
    assert result["access_key"] == "AKIATEST"
    assert result["secret_key"] == "SECRET"
    assert result["token"] == "TOKEN"
    assert result["expiry_time"] == "2099-01-01T00:00:00+00:00"


@pytest.mark.unit
def test_get_credentials_from_cli_without_profile(mocker):
    """When no profile given, command does not include --profile flag."""
    creds_payload = {"AccessKeyId": "AK", "SecretAccessKey": "SK", "SessionToken": None, "Expiration": None}
    mock_run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds_payload)))

    _get_credentials_from_cli()

    call_args = mock_run.call_args[0][0]
    assert "--profile" not in call_args


@pytest.mark.unit
def test_get_credentials_from_cli_with_profile(mocker):
    """When profile given, command includes --profile flag."""
    creds_payload = {"AccessKeyId": "AK", "SecretAccessKey": "SK", "SessionToken": None, "Expiration": None}
    mock_run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(creds_payload)))

    _get_credentials_from_cli("dev-profile")

    call_args = mock_run.call_args[0][0]
    assert "--profile" in call_args
    assert "dev-profile" in call_args


@pytest.mark.unit
def test_get_credentials_from_cli_returns_none_on_failure(mocker):
    """Returns None when AWS CLI command fails (nonzero exit code)."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1))

    result = _get_credentials_from_cli("my-profile")

    assert result is None


@pytest.mark.unit
def test_get_credentials_from_cli_returns_none_on_exception(mocker):
    """Returns None when subprocess raises an exception."""
    mocker.patch("subprocess.run", side_effect=Exception("connection refused"))

    result = _get_credentials_from_cli("my-profile")

    assert result is None


@pytest.mark.unit
def test_get_credentials_from_cli_returns_none_on_json_error(mocker):
    """Returns None when CLI output is not valid JSON."""
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="not json"))

    result = _get_credentials_from_cli("my-profile")

    assert result is None


# ---------------------------------------------------------------------------
# create_aws_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_aws_session_uses_cli_credentials(mocker):
    """Uses explicit credentials from CLI when available."""
    creds = {"access_key": "AKIATEST", "secret_key": "SECRET", "token": "TOKEN", "expiry_time": "..."}
    mocker.patch("cli_tool.core.utils.aws._get_credentials_from_cli", return_value=creds)

    mock_session_class = mocker.patch("boto3.Session")
    mock_session_class.return_value = MagicMock()

    create_aws_session("my-profile", "us-east-1")

    mock_session_class.assert_called_once_with(
        aws_access_key_id="AKIATEST",
        aws_secret_access_key="SECRET",
        aws_session_token="TOKEN",
        region_name="us-east-1",
    )


@pytest.mark.unit
def test_create_aws_session_fallback_when_no_cli_credentials(mocker):
    """Falls back to boto3 default session when CLI credentials unavailable."""
    mocker.patch("cli_tool.core.utils.aws._get_credentials_from_cli", return_value=None)

    mock_session_class = mocker.patch("boto3.Session")
    mock_session_class.return_value = MagicMock()

    create_aws_session("my-profile", "us-east-1")

    mock_session_class.assert_called_once_with(profile_name="my-profile", region_name="us-east-1")


@pytest.mark.unit
def test_create_aws_session_fallback_when_no_access_key(mocker):
    """Falls back when credentials dict has no access_key."""
    mocker.patch(
        "cli_tool.core.utils.aws._get_credentials_from_cli", return_value={"access_key": None, "secret_key": "SK", "token": None, "expiry_time": None}
    )

    mock_session_class = mocker.patch("boto3.Session")
    mock_session_class.return_value = MagicMock()

    create_aws_session("my-profile")

    mock_session_class.assert_called_once_with(profile_name="my-profile", region_name=None)


@pytest.mark.unit
def test_create_aws_session_no_profile_no_region(mocker):
    """Works with no profile and no region."""
    mocker.patch("cli_tool.core.utils.aws._get_credentials_from_cli", return_value=None)

    mock_session_class = mocker.patch("boto3.Session")
    mock_session_class.return_value = MagicMock()

    create_aws_session()

    mock_session_class.assert_called_once_with(profile_name=None, region_name=None)


# ---------------------------------------------------------------------------
# create_aws_client
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_aws_client_returns_client_for_service(mocker):
    """Returns boto3 client for the specified service."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    result = create_aws_client("dynamodb", "my-profile", "us-east-1")

    assert result is mock_client
    mock_session.client.assert_called_once()
    call_kwargs = mock_session.client.call_args
    assert call_kwargs[0][0] == "dynamodb"


@pytest.mark.unit
def test_create_aws_client_passes_kwargs(mocker):
    """Additional kwargs are forwarded to session.client()."""
    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    create_aws_client("s3", endpoint_url="http://localhost:4566")

    call_kwargs = mock_session.client.call_args[1]
    assert call_kwargs.get("endpoint_url") == "http://localhost:4566"


@pytest.mark.unit
def test_create_aws_client_uses_retry_config(mocker):
    """Client config includes retry settings."""
    from botocore.config import Config

    mock_session = MagicMock()
    mocker.patch("cli_tool.core.utils.aws.create_aws_session", return_value=mock_session)

    create_aws_client("sts")

    call_kwargs = mock_session.client.call_args[1]
    config = call_kwargs.get("config")
    assert config is not None
    assert isinstance(config, Config)


# ---------------------------------------------------------------------------
# select_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_profile_returns_provided_profile():
    """When current_profile is already set, returns it without prompting."""
    result = select_profile(current_profile="dev")

    assert result == "dev"


@pytest.mark.unit
def test_select_profile_auto_selects_single_profile(mocker):
    """Auto-selects when only one profile exists."""
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=[("dev", "sso")])

    result = select_profile()

    assert result == "dev"


@pytest.mark.unit
def test_select_profile_returns_none_when_no_profiles_and_allow_none(mocker):
    """Returns None when no profiles and allow_none=True."""
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=[])

    result = select_profile(allow_none=True)

    assert result is None


@pytest.mark.unit
def test_select_profile_raises_abort_when_no_profiles(mocker):
    """Raises click.Abort when no profiles and allow_none=False."""
    import click

    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=[])

    with pytest.raises(click.Abort):
        select_profile(allow_none=False)


@pytest.mark.unit
def test_select_profile_prompts_when_multiple_profiles(mocker):
    """Prompts user when multiple profiles exist."""
    profiles = [("dev", "sso"), ("prod", "sso"), ("staging", "both")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    mocker.patch("click.prompt", return_value="1")

    result = select_profile()

    assert result == "dev"


@pytest.mark.unit
def test_select_profile_selects_default_profile_by_default(mocker):
    """When 'default' profile exists, it is the default choice."""
    profiles = [("dev", "sso"), ("default", "static"), ("prod", "sso")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    # Return empty string to trigger default selection
    mocker.patch("click.prompt", return_value="")

    result = select_profile()

    # Default profile is at index 1 (0-based), so default_choice=2
    # Empty string triggers default_choice selection
    # "default" is the result
    assert result == "default"


@pytest.mark.unit
def test_select_profile_invalid_then_valid_choice(mocker):
    """Loops on invalid input, then accepts valid input."""
    profiles = [("dev", "sso"), ("prod", "sso")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    # First call returns out-of-range, second returns valid
    mocker.patch("click.prompt", side_effect=["99", "2"])

    result = select_profile()

    assert result == "prod"


@pytest.mark.unit
def test_select_profile_source_label_both(mocker):
    """Profile with source='both' displays [sso+static] label (line 57)."""
    profiles = [("myprofile", "both"), ("other", "sso")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    # Choose the first profile
    mocker.patch("click.prompt", return_value="1")
    mock_echo = mocker.patch("click.echo")

    result = select_profile()

    assert result == "myprofile"
    # Verify the [sso+static] label was printed somewhere in the echo calls
    echo_texts = " ".join(str(call) for call in mock_echo.call_args_list)
    assert "sso+static" in echo_texts


@pytest.mark.unit
def test_select_profile_value_error_then_valid_input(mocker):
    """Loops with error message when ValueError is raised, then accepts valid input (lines 89-90)."""
    profiles = [("dev", "sso"), ("prod", "sso")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    # First call raises ValueError (non-numeric after stripping), second call succeeds
    mocker.patch("click.prompt", side_effect=[ValueError("bad input"), "1"])
    mock_echo = mocker.patch("click.echo")

    result = select_profile()

    assert result == "dev"
    echo_texts = " ".join(str(call) for call in mock_echo.call_args_list)
    assert "Invalid input" in echo_texts


@pytest.mark.unit
def test_select_profile_keyboard_interrupt_then_valid_input(mocker):
    """Loops with error message when KeyboardInterrupt is raised, then accepts valid input (lines 89-90)."""
    profiles = [("dev", "sso"), ("prod", "sso")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    mocker.patch("click.prompt", side_effect=[KeyboardInterrupt(), "2"])
    mock_echo = mocker.patch("click.echo")

    result = select_profile()

    assert result == "prod"
    echo_texts = " ".join(str(call) for call in mock_echo.call_args_list)
    assert "Invalid input" in echo_texts


@pytest.mark.unit
def test_select_profile_unknown_source_shows_config_label(mocker):
    """Profile with unknown source shows [config] label (line 57).

    Needs 2+ profiles to bypass the auto-select single-profile shortcut.
    """
    profiles = [("dev", "sso"), ("myprofile", "unknown_type")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    mocker.patch("click.prompt", return_value="2")
    mock_echo = mocker.patch("click.echo")

    result = select_profile()

    assert result == "myprofile"
    echo_texts = " ".join(str(call) for call in mock_echo.call_args_list)
    assert "config" in echo_texts


@pytest.mark.unit
def test_select_profile_reraises_click_abort(mocker):
    """select_profile re-raises click.Abort (lines 91-92)."""
    import click

    profiles = [("dev", "sso"), ("prod", "sso")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    mocker.patch("click.prompt", side_effect=click.Abort())

    with pytest.raises(click.Abort):
        select_profile()
