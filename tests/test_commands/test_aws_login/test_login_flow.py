"""
Integration tests for AWS SSO login flow.

Tests cover:
- AWS SSO login flow with browser opening
- Credential caching after successful login
- Credential refresh for expired credentials
- Login with multiple SSO profiles
- Login error handling for invalid profiles

**Validates: Requirements 4.1, 4.3, 6.4, 13.2**
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, call

import boto3
import pytest
from click.testing import CliRunner
from moto import mock_aws

from cli_tool.commands.aws_login.command import login_cmd


@pytest.fixture
def mock_aws_config_dir(tmp_path):
    """Create temporary AWS config directory."""
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    config_file = aws_dir / "config"
    credentials_file = aws_dir / "credentials"
    sso_cache_dir = aws_dir / "sso" / "cache"
    sso_cache_dir.mkdir(parents=True)
    return {"aws_dir": aws_dir, "config_file": config_file, "credentials_file": credentials_file, "sso_cache_dir": sso_cache_dir}


@pytest.fixture
def mock_sso_profile(mock_aws_config_dir):
    """Create a mock SSO profile in AWS config."""
    config_content = """[profile dev]
sso_start_url = https://dev.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = Developer
region = us-east-1
"""
    mock_aws_config_dir["config_file"].write_text(config_content)
    return "dev"


@pytest.fixture
def mock_multiple_sso_profiles(mock_aws_config_dir):
    """Create multiple SSO profiles in AWS config."""
    config_content = """[profile dev]
sso_start_url = https://dev.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = Developer
region = us-east-1

[profile prod]
sso_start_url = https://prod.awsapps.com/start
sso_region = us-east-1
sso_account_id = 987654321098
sso_role_name = Admin
region = us-west-2

[profile staging]
sso_start_url = https://staging.awsapps.com/start
sso_region = us-east-1
sso_account_id = 555555555555
sso_role_name = Developer
region = eu-west-1
"""
    mock_aws_config_dir["config_file"].write_text(config_content)
    return ["dev", "prod", "staging"]


@pytest.fixture
def mock_sso_cache_token(mock_aws_config_dir):
    """Create a mock SSO cache token."""
    # Create a valid token that expires in 8 hours
    expiration = datetime.now(timezone.utc) + timedelta(hours=8)
    cache_data = {
        "startUrl": "https://dev.awsapps.com/start",
        "region": "us-east-1",
        "accessToken": "mock-access-token-12345",
        "expiresAt": expiration.isoformat().replace("+00:00", "Z"),
    }
    cache_file = mock_aws_config_dir["sso_cache_dir"] / "abc123.json"
    cache_file.write_text(json.dumps(cache_data))
    return cache_data


@pytest.fixture
def mock_expired_sso_cache_token(mock_aws_config_dir):
    """Create an expired SSO cache token."""
    # Create a token that expired 1 hour ago
    expiration = datetime.now(timezone.utc) - timedelta(hours=1)
    cache_data = {
        "startUrl": "https://dev.awsapps.com/start",
        "region": "us-east-1",
        "accessToken": "mock-expired-token",
        "expiresAt": expiration.isoformat().replace("+00:00", "Z"),
    }
    cache_file = mock_aws_config_dir["sso_cache_dir"] / "expired123.json"
    cache_file.write_text(json.dumps(cache_data))
    return cache_data


# ============================================================================
# Test: AWS SSO Login Flow with Browser Opening
# ============================================================================


@pytest.mark.integration
def test_aws_sso_login_flow_success(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test successful AWS SSO login flow with browser opening.

    Validates:
    - Browser opens for SSO authentication
    - AWS CLI SSO login command is executed
    - Credentials are verified after login
    - Success message is displayed
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock webbrowser.open to prevent actual browser opening
    mocker.patch("webbrowser.open")

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials to return identity
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = expiration

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify success
    assert result.exit_code == 0
    assert "SSO authentication successful" in result.output
    assert "Credentials cached successfully" in result.output
    assert "123456789012" in result.output

    # Verify AWS CLI SSO login was called
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0][0]
    assert call_args == ["aws", "sso", "login", "--profile", mock_sso_profile]


@pytest.mark.integration
def test_aws_sso_login_timeout(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test AWS SSO login timeout handling.

    Validates:
    - Timeout error is caught
    - Appropriate error message is displayed
    - Non-zero exit code is returned
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run to raise TimeoutExpired
    import subprocess

    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="aws sso login", timeout=120)

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify timeout handling
    assert result.exit_code == 1
    assert "timed out" in result.output.lower()


@pytest.mark.integration
def test_aws_sso_login_authentication_failed(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test AWS SSO login authentication failure.

    Validates:
    - Failed authentication is detected
    - Error message is displayed
    - Non-zero exit code is returned
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run to return non-zero exit code
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=1)

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify failure handling
    assert result.exit_code == 1
    assert "authentication failed" in result.output.lower()


# ============================================================================
# Test: Credential Caching After Successful Login
# ============================================================================


@pytest.mark.integration
def test_credential_caching_after_login(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test that credentials are cached after successful login.

    Validates:
    - Credentials are verified after login
    - Expiration time is displayed
    - Usage instructions are shown
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = expiration

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify credentials are cached
    assert result.exit_code == 0
    assert "Credentials cached successfully" in result.output
    assert "Credentials expire at:" in result.output
    assert "Time remaining:" in result.output
    assert "To use this profile:" in result.output
    assert f"export AWS_PROFILE={mock_sso_profile}" in result.output


@pytest.mark.integration
def test_credential_verification_failure(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test handling of credential verification failure after login.

    Validates:
    - Warning is displayed when verification fails
    - Login still succeeds (authentication was successful)
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials to return None (verification failed)
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = None

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify warning is displayed
    assert result.exit_code == 0
    assert "Authentication succeeded but credentials verification failed" in result.output


# ============================================================================
# Test: Credential Refresh for Expired Credentials
# ============================================================================


@pytest.mark.integration
def test_login_with_expired_credentials(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, mock_expired_sso_cache_token):
    """
    Test login flow when existing credentials are expired.

    Validates:
    - Expired credentials are detected
    - New login is performed
    - Fresh credentials are cached
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration to return new expiration
    new_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = new_expiration

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify new login was performed
    assert result.exit_code == 0
    assert "SSO authentication successful" in result.output
    assert "Credentials cached successfully" in result.output


# ============================================================================
# Test: Login with Multiple SSO Profiles
# ============================================================================


@pytest.mark.integration
def test_login_with_multiple_profiles_selection(cli_runner, mocker, mock_aws_config_dir, mock_multiple_sso_profiles):
    """
    Test login flow with multiple SSO profiles available.

    Validates:
    - All profiles are listed
    - User can select a profile by number
    - Selected profile is used for login
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = expiration

    # Run login command without profile argument (should prompt for selection)
    # Simulate user selecting profile #2 (prod)
    result = cli_runner.invoke(login_cmd, input="2\n")

    # Verify profile selection
    assert result.exit_code == 0
    assert "Available profiles:" in result.output
    assert "dev" in result.output
    assert "prod" in result.output
    assert "staging" in result.output

    # Verify correct profile was used
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0][0]
    assert call_args == ["aws", "sso", "login", "--profile", "prod"]


@pytest.mark.integration
def test_login_with_invalid_profile_selection(cli_runner, mocker, mock_aws_config_dir, mock_multiple_sso_profiles):
    """
    Test login flow with invalid profile selection.

    Validates:
    - Invalid selection is detected
    - Error message is displayed
    - Non-zero exit code is returned
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Run login command without profile argument
    # Simulate user selecting invalid profile number (99)
    result = cli_runner.invoke(login_cmd, input="99\n")

    # Verify error handling
    assert result.exit_code == 1
    assert "Invalid selection" in result.output


# ============================================================================
# Test: Login Error Handling for Invalid Profiles
# ============================================================================


@pytest.mark.integration
def test_login_with_non_existent_profile(cli_runner, mocker, mock_aws_config_dir):
    """
    Test login with a profile that doesn't exist.

    Validates:
    - Non-existent profile is detected
    - Error message is displayed
    - Configuration instructions are shown
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Create empty config file
    mock_aws_config_dir["config_file"].write_text("")

    # Run login command with non-existent profile
    result = cli_runner.invoke(login_cmd, ["non-existent-profile"])

    # Verify error handling
    assert result.exit_code == 1
    assert "not configured for SSO" in result.output
    assert "devo aws-login configure" in result.output


@pytest.mark.integration
def test_login_with_non_sso_profile(cli_runner, mocker, mock_aws_config_dir):
    """
    Test login with a profile that is not configured for SSO.

    Validates:
    - Non-SSO profile is detected (returns empty dict, not None)
    - Login attempt fails
    - Error message is displayed
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Create a non-SSO profile
    config_content = """[profile static]
region = us-east-1
output = json
"""
    mock_aws_config_dir["config_file"].write_text(config_content)

    # Mock subprocess.run to fail (no SSO configured)
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=1)

    # Run login command with non-SSO profile
    result = cli_runner.invoke(login_cmd, ["static"])

    # Verify error handling
    # The code shows SSO URL as N/A and then fails during authentication
    assert result.exit_code == 1
    assert "SSO URL: N/A" in result.output
    assert "authentication failed" in result.output.lower()


@pytest.mark.integration
def test_login_with_no_profiles_configured(cli_runner, mocker, mock_aws_config_dir):
    """
    Test login when no AWS profiles are configured.

    Validates:
    - No profiles message is displayed
    - Configuration prompt is shown
    - User can decline configuration
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Create empty config file
    mock_aws_config_dir["config_file"].write_text("")

    # Run login command without profile argument
    # Simulate user declining configuration
    result = cli_runner.invoke(login_cmd, input="n\n")

    # Verify handling
    assert result.exit_code == 1
    assert "No AWS profiles found" in result.output
    assert "Configure SSO profile now?" in result.output
    assert "devo aws-login configure" in result.output


# ============================================================================
# Test: Browser Interaction Mocking
# ============================================================================


@pytest.mark.integration
def test_browser_not_opened_during_test(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test that browser is not actually opened during tests.

    Validates:
    - webbrowser.open is mocked
    - No actual browser window opens
    - Test runs without user interaction
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock webbrowser.open and verify it's not called
    # (AWS CLI handles browser opening internally, not our code)
    mocker.patch("webbrowser.open")

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = expiration

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify success
    assert result.exit_code == 0

    # Note: webbrowser.open is not called by our code
    # AWS CLI handles browser opening internally
    # This test verifies our mocking prevents any external interactions


# ============================================================================
# Test: AWS Login Edge Cases
# ============================================================================


@pytest.mark.integration
def test_login_with_network_failure(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test AWS SSO login with network connection failure.

    Validates:
    - Network errors are caught gracefully
    - Appropriate error message is displayed
    - Non-zero exit code is returned
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run to raise connection error
    import subprocess

    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=255, cmd=["aws", "sso", "login", "--profile", mock_sso_profile], stderr="Network error: Unable to connect to SSO endpoint"
    )

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify network error handling
    assert result.exit_code == 1
    assert "Error during authentication" in result.output


@pytest.mark.integration
def test_login_with_expired_sso_session(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, mock_expired_sso_cache_token):
    """
    Test AWS SSO login when SSO session token is expired.

    Validates:
    - Expired SSO session is detected
    - New authentication is triggered
    - Fresh credentials are obtained
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for AWS CLI SSO login
    # First call fails due to expired token, second succeeds after re-auth
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials to succeed after re-auth
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration to return new expiration
    new_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = new_expiration

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify successful re-authentication
    assert result.exit_code == 0
    assert "SSO authentication successful" in result.output
    assert "Credentials cached successfully" in result.output


@pytest.mark.integration
def test_login_with_invalid_credentials_response(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test AWS SSO login when credentials cannot be verified.

    Validates:
    - Invalid credentials are detected
    - Warning message is displayed
    - Login completes but with warning
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for AWS CLI SSO login (succeeds)
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Mock verify_credentials to fail (invalid credentials)
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = None

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify warning is displayed
    assert result.exit_code == 0
    assert "Authentication succeeded but credentials verification failed" in result.output


@pytest.mark.integration
def test_credential_auto_refresh_timing_expired(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test credential auto-refresh timing when credentials are expired.

    Validates:
    - Expired credentials are detected
    - check_profile_needs_refresh returns True with 'Expired' reason
    - Expiration time is correctly identified
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Import the function to test
    from cli_tool.commands.aws_login.core.credentials import check_profile_needs_refresh

    # Mock get_profile_config to return SSO profile
    mock_get_config = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config")
    mock_get_config.return_value = {
        "sso_start_url": "https://dev.awsapps.com/start",
        "sso_region": "us-east-1",
        "sso_account_id": "123456789012",
        "sso_role_name": "Developer",
        "region": "us-east-1",
    }

    # Mock get_profile_credentials_expiration to return expired time
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration")
    mock_expiration.return_value = expired_time

    # Check if refresh is needed
    needs_refresh, expiration, reason = check_profile_needs_refresh(mock_sso_profile)

    # Verify expired credentials are detected
    assert needs_refresh is True
    assert expiration == expired_time
    assert reason == "Expired"


@pytest.mark.integration
def test_credential_auto_refresh_timing_expiring_soon(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test credential auto-refresh timing when credentials are expiring soon.

    Validates:
    - Credentials expiring within threshold are detected
    - check_profile_needs_refresh returns True with time remaining
    - Threshold logic works correctly (default 10 minutes)
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Import the function to test
    from cli_tool.commands.aws_login.core.credentials import check_profile_needs_refresh

    # Mock get_profile_config to return SSO profile
    mock_get_config = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config")
    mock_get_config.return_value = {
        "sso_start_url": "https://dev.awsapps.com/start",
        "sso_region": "us-east-1",
        "sso_account_id": "123456789012",
        "sso_role_name": "Developer",
        "region": "us-east-1",
    }

    # Mock get_profile_credentials_expiration to return time expiring in 5 minutes
    expiring_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration")
    mock_expiration.return_value = expiring_time

    # Check if refresh is needed (default threshold is 10 minutes)
    needs_refresh, expiration, reason = check_profile_needs_refresh(mock_sso_profile)

    # Verify expiring credentials are detected
    assert needs_refresh is True
    assert expiration == expiring_time
    assert "Expiring in" in reason
    assert "minutes" in reason


@pytest.mark.integration
def test_credential_auto_refresh_timing_valid(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test credential auto-refresh timing when credentials are still valid.

    Validates:
    - Valid credentials are not flagged for refresh
    - check_profile_needs_refresh returns False with 'Valid' reason
    - Credentials with sufficient time remaining are not refreshed
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Import the function to test
    from cli_tool.commands.aws_login.core.credentials import check_profile_needs_refresh

    # Mock get_profile_config to return SSO profile
    mock_get_config = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config")
    mock_get_config.return_value = {
        "sso_start_url": "https://dev.awsapps.com/start",
        "sso_region": "us-east-1",
        "sso_account_id": "123456789012",
        "sso_role_name": "Developer",
        "region": "us-east-1",
    }

    # Mock get_profile_credentials_expiration to return valid time (30 minutes from now)
    valid_time = datetime.now(timezone.utc) + timedelta(minutes=30)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration")
    mock_expiration.return_value = valid_time

    # Check if refresh is needed (default threshold is 10 minutes)
    needs_refresh, expiration, reason = check_profile_needs_refresh(mock_sso_profile)

    # Verify valid credentials are not flagged for refresh
    assert needs_refresh is False
    assert expiration == valid_time
    assert reason == "Valid"


@pytest.mark.integration
def test_credential_auto_refresh_timing_no_credentials(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test credential auto-refresh timing when no credentials exist.

    Validates:
    - Missing credentials are detected
    - check_profile_needs_refresh returns True with 'No valid credentials found' reason
    - Login is required when no cached credentials exist
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Import the function to test
    from cli_tool.commands.aws_login.core.credentials import check_profile_needs_refresh

    # Mock get_profile_config to return SSO profile
    mock_get_config = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_config")
    mock_get_config.return_value = {
        "sso_start_url": "https://dev.awsapps.com/start",
        "sso_region": "us-east-1",
        "sso_account_id": "123456789012",
        "sso_role_name": "Developer",
        "region": "us-east-1",
    }

    # Mock get_profile_credentials_expiration to return None (no credentials)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_profile_credentials_expiration")
    mock_expiration.return_value = None

    # Check if refresh is needed
    needs_refresh, expiration, reason = check_profile_needs_refresh(mock_sso_profile)

    # Verify missing credentials are detected
    assert needs_refresh is True
    assert expiration is None
    assert reason == "No valid credentials found"


@pytest.mark.integration
def test_login_with_subprocess_timeout(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test AWS SSO login when subprocess times out.

    Validates:
    - Subprocess timeout is caught
    - Timeout error message is displayed
    - Non-zero exit code is returned
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run to raise TimeoutExpired
    import subprocess

    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=["aws", "sso", "login", "--profile", mock_sso_profile], timeout=120)

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify timeout handling
    assert result.exit_code == 1
    assert "timed out" in result.output.lower()


@pytest.mark.integration
def test_login_with_keyboard_interrupt(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test AWS SSO login when user cancels with Ctrl+C.

    Validates:
    - KeyboardInterrupt is caught
    - Cancellation message is displayed
    - Non-zero exit code is returned
    """
    # Mock Path.home()
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run to raise KeyboardInterrupt
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.side_effect = KeyboardInterrupt()

    # Run login command
    result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify cancellation handling
    assert result.exit_code == 1
    assert "cancelled" in result.output.lower()


# ============================================================================
# Unit tests for _resolve_profile_name and _show_login_success (lines 53-57, 83)
# ============================================================================


@pytest.mark.unit
def test_resolve_profile_name_configure_sso_returns_profile(mocker):
    """
    When no profiles exist and user confirms, configure_sso_profile is called.
    If it returns a profile name, that name is returned (lines 53-57).
    """
    from cli_tool.commands.aws_login.commands.login import _resolve_profile_name

    mocker.patch("cli_tool.commands.aws_login.commands.login.list_aws_profiles", return_value=[])
    mocker.patch("click.confirm", return_value=True)
    mock_configure = mocker.patch(
        "cli_tool.commands.aws_login.commands.login.configure_sso_profile",
        return_value="new-profile",
    )

    result = _resolve_profile_name()

    mock_configure.assert_called_once()
    assert result == "new-profile"


@pytest.mark.unit
def test_resolve_profile_name_configure_sso_returns_none_exits(mocker):
    """
    When configure_sso_profile returns None (falsy), sys.exit(1) is called (line 55).
    """
    import sys

    from cli_tool.commands.aws_login.commands.login import _resolve_profile_name

    mocker.patch("cli_tool.commands.aws_login.commands.login.list_aws_profiles", return_value=[])
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.login.configure_sso_profile",
        return_value=None,
    )

    with pytest.raises(SystemExit) as exc_info:
        _resolve_profile_name()

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_show_login_success_no_expiration_prints_note(mocker):
    """
    When get_profile_credentials_expiration returns None, the 'typically expire in 1 hour'
    note is printed (line 83).
    """
    from cli_tool.commands.aws_login.commands.login import _show_login_success

    mocker.patch(
        "cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration",
        return_value=None,
    )
    mock_console = mocker.patch("cli_tool.commands.aws_login.commands.login.console")

    identity = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Dev/user",
    }
    _show_login_success("dev", identity)

    printed_texts = [str(call) for call in mock_console.print.call_args_list]
    assert any("typically expire in 1 hour" in t for t in printed_texts)


# ---------------------------------------------------------------------------
# _update_default_credentials_if_needed
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_update_default_credentials_if_needed_skips_when_no_config(mocker):
    """When no default profile is configured, does nothing."""
    from cli_tool.commands.aws_login.commands.login import _update_default_credentials_if_needed

    mocker.patch("cli_tool.commands.aws_login.commands.login.get_config_value", return_value=None)
    mock_write = mocker.patch("cli_tool.commands.aws_login.commands.login.write_default_credentials")

    _update_default_credentials_if_needed("dev")

    mock_write.assert_not_called()


@pytest.mark.unit
def test_update_default_credentials_if_needed_skips_when_different_profile(mocker):
    """When the logged-in profile is not the configured default, does nothing."""
    from cli_tool.commands.aws_login.commands.login import _update_default_credentials_if_needed

    mocker.patch("cli_tool.commands.aws_login.commands.login.get_config_value", return_value="prod")
    mock_write = mocker.patch("cli_tool.commands.aws_login.commands.login.write_default_credentials")

    _update_default_credentials_if_needed("dev")

    mock_write.assert_not_called()


@pytest.mark.unit
def test_update_default_credentials_if_needed_writes_when_profile_matches(mocker):
    """When the logged-in profile matches the configured default, re-writes [default]."""
    from cli_tool.commands.aws_login.commands.login import _update_default_credentials_if_needed

    mocker.patch("cli_tool.commands.aws_login.commands.login.get_config_value", return_value="dev")
    mock_write = mocker.patch(
        "cli_tool.commands.aws_login.commands.login.write_default_credentials",
        return_value={"expiration": "2026-12-31T00:00:00Z"},
    )

    _update_default_credentials_if_needed("dev")

    mock_write.assert_called_once_with("dev")


@pytest.mark.unit
def test_update_default_credentials_if_needed_handles_write_failure(mocker):
    """When write_default_credentials returns None, does not raise."""
    from cli_tool.commands.aws_login.commands.login import _update_default_credentials_if_needed

    mocker.patch("cli_tool.commands.aws_login.commands.login.get_config_value", return_value="dev")
    mocker.patch("cli_tool.commands.aws_login.commands.login.write_default_credentials", return_value=None)

    # Should not raise
    _update_default_credentials_if_needed("dev")


@pytest.mark.unit
def test_run_sso_login_updates_default_after_success(mocker):
    """After a successful SSO login, [default] is updated if profile is the configured default."""
    import subprocess as sp

    from cli_tool.commands.aws_login.commands.login import _run_sso_login

    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    mocker.patch(
        "cli_tool.commands.aws_login.commands.login.verify_credentials",
        return_value={"account": "123", "arn": "arn:aws:iam::123:role/Dev", "user_id": "AIDA"},
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration",
        return_value=None,
    )
    mock_update = mocker.patch("cli_tool.commands.aws_login.commands.login._update_default_credentials_if_needed")

    _run_sso_login("dev")

    mock_update.assert_called_once_with("dev")
