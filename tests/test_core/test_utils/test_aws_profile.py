"""
Unit tests for cli_tool.core.utils.aws_profile module.

Tests cover profile discovery, credential verification, profile selection, and
the ensure_aws_profile workflow. All subprocess calls and interactive prompts
are mocked.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from cli_tool.core.utils.aws_profile import (
    _handle_wrong_account,
    _pick_profile_from_list,
    _verify_and_check_account,
    ensure_aws_profile,
    get_aws_profiles,
    select_aws_profile,
    verify_aws_credentials,
)

# ============================================================================
# verify_aws_credentials
# ============================================================================


@pytest.mark.unit
def test_verify_aws_credentials_success(mocker):
    """Returns (account_id, arn) when sts get-caller-identity succeeds."""
    identity = {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/test"}
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(identity)
    mocker.patch("subprocess.run", return_value=mock_result)

    account, arn = verify_aws_credentials()

    assert account == "123456789012"
    assert "arn:aws:iam" in arn


@pytest.mark.unit
def test_verify_aws_credentials_with_profile(mocker):
    """Passes --profile to the aws sts command when profile is given."""
    identity = {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/test"}
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(identity)
    mock_run = mocker.patch("subprocess.run", return_value=mock_result)

    verify_aws_credentials(profile="my-profile")

    called_cmd = mock_run.call_args[0][0]
    assert "--profile" in called_cmd
    assert "my-profile" in called_cmd


@pytest.mark.unit
def test_verify_aws_credentials_non_zero_return_code(mocker):
    """Returns (None, None) when the command returns a non-zero exit code."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mocker.patch("subprocess.run", return_value=mock_result)

    account, arn = verify_aws_credentials()

    assert account is None
    assert arn is None


@pytest.mark.unit
def test_verify_aws_credentials_exception(mocker):
    """Returns (None, None) when subprocess.run raises an exception."""
    mocker.patch("subprocess.run", side_effect=Exception("timeout"))

    account, arn = verify_aws_credentials()

    assert account is None
    assert arn is None


@pytest.mark.unit
def test_verify_aws_credentials_malformed_json(mocker):
    """Returns (None, None) on malformed JSON output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "not-valid-json"
    mocker.patch("subprocess.run", return_value=mock_result)

    account, arn = verify_aws_credentials()

    assert account is None
    assert arn is None


# ============================================================================
# get_aws_profiles
# ============================================================================


@pytest.mark.unit
def test_get_aws_profiles_returns_list(mocker):
    """get_aws_profiles returns a list of (profile_name, source) tuples."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.get_aws_profiles",
        return_value=[("default", "sso"), ("dev", "static")],
    )
    profiles = get_aws_profiles()
    assert isinstance(profiles, list)


@pytest.mark.unit
def test_get_aws_profiles_empty_returns_empty_list(mocker):
    """get_aws_profiles returns empty list when no profiles found."""
    mocker.patch(
        "cli_tool.commands.aws_login.core.config.list_aws_profiles",
        return_value=[],
    )
    profiles = get_aws_profiles()
    assert profiles == []


# ============================================================================
# _verify_and_check_account
# ============================================================================


@pytest.mark.unit
def test_verify_and_check_account_valid_credentials_no_required_account(mocker):
    """Returns True when credentials are valid and no account requirement."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:user/u"),
    )
    result = _verify_and_check_account("my-profile", None, False)
    assert result is True


@pytest.mark.unit
def test_verify_and_check_account_matching_required_account(mocker):
    """Returns True when credentials match the required account."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:user/u"),
    )
    result = _verify_and_check_account("my-profile", "123456789012", False)
    assert result is True


@pytest.mark.unit
def test_verify_and_check_account_wrong_account(mocker):
    """Returns False when credentials belong to a different account."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=("999999999999", "arn:aws:iam::999999999999:user/u"),
    )
    result = _verify_and_check_account("my-profile", "123456789012", False)
    assert result is False


@pytest.mark.unit
def test_verify_and_check_account_invalid_credentials(mocker):
    """Returns False when credentials are invalid (None returned)."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=(None, None),
    )
    result = _verify_and_check_account("bad-profile", None, False)
    assert result is False


@pytest.mark.unit
def test_verify_and_check_account_shows_messages_on_error(mocker, capsys):
    """Prints error messages when show_messages=True and credentials fail."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=(None, None),
    )
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        _verify_and_check_account("bad-profile", None, show_messages=True)
        assert mock_click.echo.called


# ============================================================================
# _handle_wrong_account
# ============================================================================


@pytest.mark.unit
def test_handle_wrong_account_prints_messages_when_show_messages_true():
    """_handle_wrong_account prints error messages when show_messages=True."""
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        _handle_wrong_account("999999999999", "123456789012", show_messages=True)
        assert mock_click.echo.called


@pytest.mark.unit
def test_handle_wrong_account_silent_when_show_messages_false():
    """_handle_wrong_account does not print when show_messages=False."""
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        _handle_wrong_account("999999999999", "123456789012", show_messages=False)
        mock_click.echo.assert_not_called()


# ============================================================================
# _pick_profile_from_list
# ============================================================================


@pytest.mark.unit
def test_pick_profile_from_list_valid_selection(mocker):
    """Returns the selected profile name when user enters a valid number."""
    profiles = [("dev-profile", "sso"), ("prod-profile", "static")]
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:user/u"),
    )
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        mock_click.prompt.return_value = "1"
        result = _pick_profile_from_list(profiles, None, False)

    assert result == "dev-profile"


@pytest.mark.unit
def test_pick_profile_from_list_empty_input_returns_none(mocker):
    """Returns None when user presses Enter without selecting."""
    profiles = [("dev-profile", "sso")]
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        mock_click.prompt.return_value = ""
        result = _pick_profile_from_list(profiles, None, False)

    assert result is None


@pytest.mark.unit
def test_pick_profile_from_list_invalid_number_returns_none(mocker):
    """Returns None when user enters a non-numeric string."""
    profiles = [("dev-profile", "sso")]
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        mock_click.prompt.return_value = "abc"
        result = _pick_profile_from_list(profiles, None, False)

    assert result is None


@pytest.mark.unit
def test_pick_profile_from_list_out_of_range_returns_none(mocker):
    """Returns None when user enters a number out of valid range."""
    profiles = [("dev-profile", "sso")]
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        mock_click.prompt.return_value = "99"
        result = _pick_profile_from_list(profiles, None, False)

    assert result is None


@pytest.mark.unit
def test_pick_profile_from_list_invalid_credentials_returns_none(mocker):
    """Returns None when selected profile has invalid credentials."""
    profiles = [("bad-profile", "sso")]
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=(None, None),
    )
    with patch("cli_tool.core.utils.aws_profile.click") as mock_click:
        mock_click.prompt.return_value = "1"
        result = _pick_profile_from_list(profiles, None, False)

    assert result is None


# ============================================================================
# select_aws_profile
# ============================================================================


@pytest.mark.unit
def test_select_aws_profile_no_profiles(mocker):
    """Returns None when no profiles are available."""
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=[])
    with patch("cli_tool.core.utils.aws_profile.click"):
        result = select_aws_profile(show_messages=False)
    assert result is None


@pytest.mark.unit
def test_select_aws_profile_single_valid_profile(mocker):
    """Returns the single profile when only one is available and credentials are valid."""
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=[("only-profile", "sso")])
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:user/u"),
    )
    with patch("cli_tool.core.utils.aws_profile.click"):
        result = select_aws_profile(show_messages=False)
    assert result == "only-profile"


@pytest.mark.unit
def test_select_aws_profile_single_invalid_profile(mocker):
    """Returns None when single profile has invalid credentials."""
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=[("bad-profile", "sso")])
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=(None, None),
    )
    with patch("cli_tool.core.utils.aws_profile.click"):
        result = select_aws_profile(show_messages=False)
    assert result is None


@pytest.mark.unit
def test_select_aws_profile_multiple_profiles_delegates_to_pick(mocker):
    """With multiple profiles, delegates to _pick_profile_from_list."""
    profiles = [("dev", "sso"), ("prod", "sso")]
    mocker.patch("cli_tool.core.utils.aws_profile.get_aws_profiles", return_value=profiles)
    mock_pick = mocker.patch(
        "cli_tool.core.utils.aws_profile._pick_profile_from_list",
        return_value="dev",
    )
    with patch("cli_tool.core.utils.aws_profile.click"):
        result = select_aws_profile(show_messages=False)

    mock_pick.assert_called_once()
    assert result == "dev"


# ============================================================================
# ensure_aws_profile
# ============================================================================


@pytest.mark.unit
def test_ensure_aws_profile_valid_profile_no_requirement(mocker):
    """Returns (profile, account_id, arn) when profile has valid credentials."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:user/u"),
    )
    profile, account, arn = ensure_aws_profile(profile="my-profile", show_messages=False)
    assert profile == "my-profile"
    assert account == "123456789012"


@pytest.mark.unit
def test_ensure_aws_profile_matching_required_account(mocker):
    """Returns (profile, account_id, arn) when account matches requirement."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:user/u"),
    )
    profile, account, arn = ensure_aws_profile(
        profile="my-profile",
        required_account="123456789012",
        show_messages=False,
    )
    assert profile == "my-profile"
    assert account == "123456789012"


@pytest.mark.unit
def test_ensure_aws_profile_wrong_account_falls_back_to_selection(mocker):
    """Falls back to profile selection when current profile is wrong account."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        side_effect=[
            ("999999999999", "arn:aws:iam::999999999999:user/u"),  # First call — wrong account
            ("123456789012", "arn:aws:iam::123456789012:user/u"),  # Second call — correct
        ],
    )
    mocker.patch("cli_tool.core.utils.aws_profile.select_aws_profile", return_value="correct-profile")

    with patch("cli_tool.core.utils.aws_profile.click"):
        profile, account, arn = ensure_aws_profile(
            profile="wrong-profile",
            required_account="123456789012",
            show_messages=False,
        )

    assert profile == "correct-profile"
    assert account == "123456789012"


@pytest.mark.unit
def test_ensure_aws_profile_no_credentials_no_selection(mocker):
    """Returns (None, None, None) when credentials fail and no profile selected."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        return_value=(None, None),
    )
    mocker.patch("cli_tool.core.utils.aws_profile.select_aws_profile", return_value=None)

    with patch("cli_tool.core.utils.aws_profile.click"):
        profile, account, arn = ensure_aws_profile(show_messages=False)

    assert profile is None
    assert account is None
    assert arn is None


@pytest.mark.unit
def test_ensure_aws_profile_selected_profile_wrong_account(mocker):
    """Returns (None, None, None) when selected profile is also for wrong account."""
    mocker.patch(
        "cli_tool.core.utils.aws_profile.verify_aws_credentials",
        side_effect=[
            (None, None),  # First call with no profile
            ("999999999999", "arn:aws:iam::999999999999:user/u"),  # Selected profile also wrong
        ],
    )
    mocker.patch("cli_tool.core.utils.aws_profile.select_aws_profile", return_value="selected-profile")

    with patch("cli_tool.core.utils.aws_profile.click"):
        profile, account, arn = ensure_aws_profile(
            required_account="123456789012",
            show_messages=False,
        )

    assert profile is None
    assert account is None
    assert arn is None
