"""
Tests for the `devo aws-login list` command.

This module tests the profile listing functionality including:
- Empty profile lists
- Static credential profiles
- SSO profiles with various credential states
- Mixed profile types
- Expiration time display and formatting
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cli_tool.commands.aws_login.commands.list import list_profiles


@pytest.fixture
def mock_aws_config_dir(tmp_path, monkeypatch):
    """Create temporary AWS config directory."""
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()

    # Mock the home directory to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    return aws_dir


@pytest.mark.integration
def test_list_profiles_no_profiles(cli_runner, mocker, mock_aws_config_dir):
    """Test listing profiles when no profiles are configured."""
    # Mock list_aws_profiles to return empty list
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[])

    # Mock sys.exit to prevent actual exit
    mock_exit = mocker.patch("sys.exit")

    # Invoke the command
    list_profiles()

    # Verify output contains "No AWS profiles found"
    # Note: We can't easily capture Rich console output in tests,
    # but we can verify sys.exit was called with 0
    mock_exit.assert_called_once_with(0)


@pytest.mark.integration
def test_list_profiles_static_credentials(cli_runner, mocker, mock_aws_config_dir):
    """Test listing profiles with static credentials."""
    # Mock list_aws_profiles to return static profile
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-static-profile", "static")])

    # Invoke the command
    list_profiles()

    # Verify no errors occurred (function completes successfully)
    # Static profiles should show "Static" status and "N/A" for expiration


@pytest.mark.integration
def test_list_profiles_sso_valid_credentials(cli_runner, mocker, mock_aws_config_dir):
    """Test listing SSO profiles with valid credentials."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-sso-profile", "sso")])

    # Mock get_profile_config to return SSO config
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={
            "sso_start_url": "https://my-sso.awsapps.com/start",
            "sso_region": "us-east-1",
            "sso_account_id": "123456789012",
            "sso_role_name": "Developer",
            "region": "us-east-1",
        },
    )

    # Mock get_profile_credentials_expiration to return valid expiration (2 hours from now)
    expiration = datetime.now(timezone.utc) + timedelta(hours=2)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "Valid" status in green with expiration time


@pytest.mark.integration
def test_list_profiles_sso_expiring_soon(cli_runner, mocker, mock_aws_config_dir):
    """Test listing SSO profiles with credentials expiring soon (< 10 minutes)."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-sso-profile", "sso")])

    # Mock get_profile_config
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={
            "sso_start_url": "https://my-sso.awsapps.com/start",
            "sso_region": "us-east-1",
            "sso_account_id": "123456789012",
            "sso_role_name": "Developer",
        },
    )

    # Mock get_profile_credentials_expiration to return expiration in 5 minutes
    expiration = datetime.now(timezone.utc) + timedelta(minutes=5)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "Expiring Soon" status in yellow with minutes remaining


@pytest.mark.integration
def test_list_profiles_sso_expired(cli_runner, mocker, mock_aws_config_dir):
    """Test listing SSO profiles with expired credentials."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-sso-profile", "sso")])

    # Mock get_profile_config
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={
            "sso_start_url": "https://my-sso.awsapps.com/start",
            "sso_region": "us-east-1",
            "sso_account_id": "123456789012",
            "sso_role_name": "Developer",
        },
    )

    # Mock get_profile_credentials_expiration to return expired time (1 hour ago)
    expiration = datetime.now(timezone.utc) - timedelta(hours=1)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "Expired" status in red


@pytest.mark.integration
def test_list_profiles_sso_no_credentials(cli_runner, mocker, mock_aws_config_dir):
    """Test listing SSO profiles with no credentials cached."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-sso-profile", "sso")])

    # Mock get_profile_config
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={
            "sso_start_url": "https://my-sso.awsapps.com/start",
            "sso_region": "us-east-1",
            "sso_account_id": "123456789012",
            "sso_role_name": "Developer",
        },
    )

    # Mock get_profile_credentials_expiration to return None (no credentials)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=None)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "No Credentials" status in red


@pytest.mark.integration
def test_list_profiles_non_sso(cli_runner, mocker, mock_aws_config_dir):
    """Test listing non-SSO profiles from config file."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-config-profile", "config")])

    # Mock get_profile_config to return config without SSO
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_config", return_value={"region": "us-west-2", "output": "json"})

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "Not SSO" status


@pytest.mark.integration
def test_list_profiles_no_config(cli_runner, mocker, mock_aws_config_dir):
    """Test listing profiles when profile config cannot be found."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("unknown-profile", "config")])

    # Mock get_profile_config to return None
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_config", return_value=None)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "No Config" status in yellow


@pytest.mark.integration
def test_list_profiles_mixed_states(cli_runner, mocker, mock_aws_config_dir):
    """Test listing multiple profiles with different states."""
    # Mock list_aws_profiles with multiple profiles
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.list_aws_profiles",
        return_value=[
            ("static-profile", "static"),
            ("sso-valid", "sso"),
            ("sso-expiring", "sso"),
            ("sso-expired", "sso"),
            ("sso-no-creds", "sso"),
            ("non-sso", "config"),
        ],
    )

    # Mock get_profile_config to return appropriate configs
    def mock_get_profile_config(profile_name):
        if profile_name == "static-profile":
            return None
        elif profile_name.startswith("sso-"):
            return {
                "sso_start_url": "https://my-sso.awsapps.com/start",
                "sso_region": "us-east-1",
                "sso_account_id": "123456789012",
                "sso_role_name": "Developer",
            }
        elif profile_name == "non-sso":
            return {"region": "us-west-2", "output": "json"}
        return None

    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_config", side_effect=mock_get_profile_config)

    # Mock get_profile_credentials_expiration with different states
    def mock_get_expiration(profile_name):
        if profile_name == "sso-valid":
            return datetime.now(timezone.utc) + timedelta(hours=2)
        elif profile_name == "sso-expiring":
            return datetime.now(timezone.utc) + timedelta(minutes=5)
        elif profile_name == "sso-expired":
            return datetime.now(timezone.utc) - timedelta(hours=1)
        elif profile_name == "sso-no-creds":
            return None
        return None

    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", side_effect=mock_get_expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show all profiles with appropriate statuses


@pytest.mark.integration
def test_list_profiles_sso_session_format(cli_runner, mocker, mock_aws_config_dir):
    """Test listing SSO profiles using sso_session format."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-sso-profile", "sso")])

    # Mock get_profile_config to return SSO config with sso_session
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={
            "sso_session": "my-session",
            "sso_start_url": "https://my-sso.awsapps.com/start",
            "sso_region": "us-east-1",
            "sso_account_id": "123456789012",
            "sso_role_name": "Developer",
        },
    )

    # Mock get_profile_credentials_expiration
    expiration = datetime.now(timezone.utc) + timedelta(hours=2)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should recognize sso_session as SSO profile


@pytest.mark.integration
def test_list_profiles_expiration_boundary_10_minutes(cli_runner, mocker, mock_aws_config_dir):
    """Test listing profiles with expiration exactly at 10 minute boundary."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-sso-profile", "sso")])

    # Mock get_profile_config
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={"sso_start_url": "https://my-sso.awsapps.com/start", "sso_region": "us-east-1"},
    )

    # Mock get_profile_credentials_expiration to return exactly 10 minutes
    expiration = datetime.now(timezone.utc) + timedelta(minutes=10)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "Expiring Soon" status (threshold is <= 600 seconds)


@pytest.mark.integration
def test_list_profiles_expiration_just_over_10_minutes(cli_runner, mocker, mock_aws_config_dir):
    """Test listing profiles with expiration just over 10 minutes."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-sso-profile", "sso")])

    # Mock get_profile_config
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={"sso_start_url": "https://my-sso.awsapps.com/start", "sso_region": "us-east-1"},
    )

    # Mock get_profile_credentials_expiration to return 11 minutes
    expiration = datetime.now(timezone.utc) + timedelta(minutes=11)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show "Valid" status (over 10 minute threshold)


@pytest.mark.integration
def test_list_profiles_both_source(cli_runner, mocker, mock_aws_config_dir):
    """Test listing profiles that exist in both config and credentials files."""
    # Mock list_aws_profiles
    mocker.patch("cli_tool.commands.aws_login.commands.list.list_aws_profiles", return_value=[("my-profile", "both")])

    # Mock get_profile_config to return SSO config
    mocker.patch(
        "cli_tool.commands.aws_login.commands.list.get_profile_config",
        return_value={"sso_start_url": "https://my-sso.awsapps.com/start", "sso_region": "us-east-1"},
    )

    # Mock get_profile_credentials_expiration
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mocker.patch("cli_tool.commands.aws_login.commands.list.get_profile_credentials_expiration", return_value=expiration)

    # Invoke the command
    list_profiles()

    # Verify no errors occurred
    # Should show profile with "both" source
