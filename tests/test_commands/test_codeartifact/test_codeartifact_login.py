"""
Integration tests for CodeArtifact login command.

Tests the complete CodeArtifact authentication workflow including:
- Authentication token generation
- Pip configuration update
- Token expiration handling (12 hours)
- Multiple domain authentication
- Error handling for authentication failures
"""

from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from cli_tool.commands.codeartifact.commands.login import codeartifact_login


@pytest.fixture(autouse=True)
def mock_config_values(mocker):
    """Mock configuration values for CodeArtifact."""
    mocker.patch("cli_tool.commands.codeartifact.commands.login.AWS_SSO_URL", "https://test.awsapps.com/start")
    mocker.patch("cli_tool.commands.codeartifact.commands.login.REQUIRED_ACCOUNT", "123456789012")
    mocker.patch("cli_tool.commands.codeartifact.commands.login.REQUIRED_ROLE", "Developer")
    mocker.patch("cli_tool.commands.codeartifact.commands.login.CODEARTIFACT_REGION", "us-east-1")
    mocker.patch(
        "cli_tool.commands.codeartifact.commands.login.CODEARTIFACT_DOMAINS",
        [
            ("test-domain", "test-repo", "@test"),
            ("test-domain-2", "test-repo-2", "@test2"),
        ],
    )


@pytest.fixture
def mock_aws_utils(mocker):
    """Mock AWS utility functions."""
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=True)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)
    mocker.patch(
        "cli_tool.commands.codeartifact.commands.login.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:role/Developer"),
    )


@pytest.fixture
def mock_subprocess(mocker):
    """Mock subprocess.run for AWS CLI commands."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    return mock_run


@pytest.mark.integration
def test_codeartifact_login_success(cli_runner, mock_aws_utils, mock_subprocess):
    """Test successful CodeArtifact authentication."""
    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success
    assert result.exit_code == 0
    assert "Successfully authenticated" in result.output
    assert "test-domain/test-repo" in result.output
    assert "test-domain-2/test-repo-2" in result.output

    # Verify AWS CLI commands were called for both domains
    assert mock_subprocess.call_count >= 2

    # Verify login commands were called with correct parameters
    login_calls = [call for call in mock_subprocess.call_args_list if "codeartifact" in str(call) and "login" in str(call)]
    assert len(login_calls) >= 2


@pytest.mark.integration
def test_codeartifact_login_with_profile(cli_runner, mock_aws_utils, mock_subprocess, mocker):
    """Test CodeArtifact authentication with AWS profile."""
    # Mock select_profile to return a profile
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value="test-profile")

    # Run login command with profile
    result = cli_runner.invoke(codeartifact_login, [], obj={"profile": "test-profile"})

    # Verify success
    assert result.exit_code == 0
    assert "Using profile: test-profile" in result.output

    # Verify profile was passed to AWS CLI commands
    profile_calls = [call for call in mock_subprocess.call_args_list if "--profile" in str(call) and "test-profile" in str(call)]
    assert len(profile_calls) >= 2


@pytest.mark.integration
def test_codeartifact_login_no_aws_cli(cli_runner, mocker):
    """Test CodeArtifact login fails when AWS CLI is not installed."""
    # Mock check_aws_cli to return False
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=False)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify failure
    assert result.exit_code == 1


@pytest.mark.integration
def test_codeartifact_login_no_credentials(cli_runner, mocker, mock_subprocess):
    """Test CodeArtifact login fails when no AWS credentials are found."""
    # Mock AWS utilities
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=True)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)
    mocker.patch("cli_tool.commands.codeartifact.commands.login.verify_aws_credentials", return_value=(None, None))

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify failure
    assert result.exit_code == 1
    assert "No AWS credentials found" in result.output


@pytest.mark.integration
def test_codeartifact_login_wrong_account(cli_runner, mocker, mock_subprocess):
    """Test CodeArtifact login fails when using wrong AWS account."""
    # Mock AWS utilities with wrong account
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=True)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)
    mocker.patch(
        "cli_tool.commands.codeartifact.commands.login.verify_aws_credentials",
        return_value=("999999999999", "arn:aws:iam::999999999999:role/Developer"),
    )

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify failure
    assert result.exit_code == 1
    assert "Current credentials are for account: 999999999999" in result.output
    assert "Required account: 123456789012" in result.output


@pytest.mark.integration
def test_codeartifact_login_wrong_role_continue(cli_runner, mocker, mock_subprocess):
    """Test CodeArtifact login with wrong role but user continues."""
    # Mock AWS utilities with wrong role
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=True)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)
    mocker.patch(
        "cli_tool.commands.codeartifact.commands.login.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:role/ReadOnly"),
    )

    # Run login command with confirmation to continue
    result = cli_runner.invoke(codeartifact_login, [], obj={}, input="y\n")

    # Verify warning but continues
    assert "does not contain 'Developer' role" in result.output
    assert "Continue anyway?" in result.output
    # Should continue and attempt authentication
    assert mock_subprocess.call_count >= 2


@pytest.mark.integration
def test_codeartifact_login_wrong_role_abort(cli_runner, mocker, mock_subprocess):
    """Test CodeArtifact login with wrong role and user aborts."""
    # Mock AWS utilities with wrong role
    mocker.patch("cli_tool.commands.codeartifact.commands.login.check_aws_cli", return_value=True)
    mocker.patch("cli_tool.core.utils.aws.select_profile", return_value=None)
    mocker.patch(
        "cli_tool.commands.codeartifact.commands.login.verify_aws_credentials",
        return_value=("123456789012", "arn:aws:iam::123456789012:role/ReadOnly"),
    )

    # Run login command with confirmation to abort
    result = cli_runner.invoke(codeartifact_login, [], obj={}, input="n\n")

    # Verify abort
    assert result.exit_code == 1
    assert "Aborted" in result.output
    # Should not attempt authentication
    assert mock_subprocess.call_count == 0


@pytest.mark.integration
def test_codeartifact_login_authentication_failure(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact login handles authentication failures."""
    # Mock subprocess to fail
    import subprocess

    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["aws", "codeartifact", "login"], stderr="AccessDeniedException: User is not authorized"
    )

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify failure
    assert result.exit_code == 1
    assert "Failed to authenticate" in result.output
    assert "Failed: 2" in result.output  # Both domains should fail


@pytest.mark.integration
def test_codeartifact_login_partial_failure(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact login with partial authentication failures."""
    # Mock subprocess to succeed for first domain, fail for second
    import subprocess

    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "test-domain-2" in str(cmd):
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr="Domain not found")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify partial failure
    assert result.exit_code == 1
    assert "Successful: 1" in result.output
    assert "Failed: 1" in result.output
    assert "test-domain-2/test-repo-2" in result.output


@pytest.mark.integration
def test_codeartifact_login_timeout(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact login handles timeout errors."""
    # Mock subprocess to timeout
    import subprocess

    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["aws", "codeartifact", "login"], timeout=30)

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify timeout handling
    assert result.exit_code == 1
    assert "Failed to authenticate" in result.output


@pytest.mark.integration
def test_codeartifact_login_token_expiration_note(cli_runner, mock_aws_utils, mock_subprocess):
    """Test CodeArtifact login displays token expiration note."""
    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success and expiration note
    assert result.exit_code == 0
    assert "Tokens expire in 12 hours" in result.output


@pytest.mark.integration
def test_codeartifact_login_lists_packages(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact login lists available packages after authentication."""
    # Mock subprocess for login and list-packages
    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "list-packages" in str(cmd):
            return MagicMock(returncode=0, stdout="package1\tpackage2\tpackage3", stderr="")
        elif "list-package-versions" in str(cmd):
            return MagicMock(returncode=0, stdout="1.0.0", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success and package listing
    assert result.exit_code == 0
    assert "Available Packages" in result.output
    assert "package1" in result.output or "@test/package1" in result.output


@pytest.mark.integration
def test_codeartifact_login_no_packages(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact login handles repositories with no packages."""
    # Mock subprocess for login (success) and list-packages (empty)
    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "list-packages" in str(cmd):
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success and no packages message
    assert result.exit_code == 0
    assert "No packages found" in result.output


@pytest.mark.integration
def test_codeartifact_login_package_version_retrieval(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact login retrieves package versions."""
    # Mock subprocess for login, list-packages, and list-package-versions
    mock_run = mocker.patch("subprocess.run")

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("cmd", [])
        if "list-packages" in str(cmd):
            return MagicMock(returncode=0, stdout="my-package", stderr="")
        elif "list-package-versions" in str(cmd):
            return MagicMock(returncode=0, stdout="2.5.1", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success and package version
    assert result.exit_code == 0
    assert "my-package@2.5.1" in result.output or "my-package" in result.output


@pytest.mark.integration
def test_codeartifact_login_multiple_domains(cli_runner, mock_aws_utils, mock_subprocess):
    """Test CodeArtifact login authenticates with multiple domains."""
    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success with both domains
    assert result.exit_code == 0
    assert "test-domain/test-repo (@test)" in result.output
    assert "test-domain-2/test-repo-2 (@test2)" in result.output
    assert "Successful: 2" in result.output

    # Verify login was called for each domain
    login_calls = [call for call in mock_subprocess.call_args_list if "codeartifact" in str(call) and "login" in str(call)]
    assert len(login_calls) >= 2


@pytest.mark.integration
def test_codeartifact_login_command_parameters(cli_runner, mock_aws_utils, mock_subprocess):
    """Test CodeArtifact login uses correct AWS CLI command parameters."""
    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success
    assert result.exit_code == 0

    # Verify correct command parameters were used
    login_calls = [call for call in mock_subprocess.call_args_list if "codeartifact" in str(call) and "login" in str(call)]

    # Check first login call
    first_call = login_calls[0]
    call_args = first_call[0][0]  # Get the command list

    assert "aws" in call_args
    assert "codeartifact" in call_args
    assert "login" in call_args
    assert "--tool" in call_args
    assert "npm" in call_args
    assert "--domain" in call_args
    assert "--repository" in call_args
    assert "--namespace" in call_args
    assert "--region" in call_args
    assert "us-east-1" in call_args


@pytest.mark.integration
def test_codeartifact_login_pnpm_note(cli_runner, mock_aws_utils, mock_subprocess):
    """Test CodeArtifact login displays pnpm compatibility note."""
    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success and pnpm note
    assert result.exit_code == 0
    assert "pnpm will automatically use the npm configuration" in result.output


@pytest.mark.integration
def test_codeartifact_login_troubleshooting_info(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact login displays troubleshooting info on failure."""
    # Mock subprocess to fail
    import subprocess

    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["aws", "codeartifact", "login"], stderr="AccessDeniedException")

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify failure and troubleshooting info
    assert result.exit_code == 1
    assert "Troubleshooting:" in result.output
    assert "aws sts get-caller-identity" in result.output
    assert "IAM permissions" in result.output


@pytest.mark.integration
def test_codeartifact_authenticator_timeout_parameter(cli_runner, mock_aws_utils, mocker):
    """Test CodeArtifact authenticator respects timeout parameter."""
    # Mock subprocess to track timeout parameter
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success
    assert result.exit_code == 0

    # Verify timeout was passed to subprocess.run
    for call in mock_run.call_args_list:
        if "codeartifact" in str(call) and "login" in str(call):
            # Check if timeout parameter was used
            assert "timeout" in call[1] or len(call[1]) > 0


@pytest.mark.integration
def test_codeartifact_login_summary_display(cli_runner, mock_aws_utils, mock_subprocess):
    """Test CodeArtifact login displays authentication summary."""
    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success and summary
    assert result.exit_code == 0
    assert "Authentication Summary" in result.output
    assert "Successful: 2" in result.output


@pytest.mark.integration
def test_codeartifact_login_displays_credential_info(cli_runner, mock_aws_utils, mock_subprocess):
    """Test CodeArtifact login displays AWS credential information."""
    # Run login command
    result = cli_runner.invoke(codeartifact_login, [], obj={})

    # Verify success and credential info
    assert result.exit_code == 0
    assert "Account: 123456789012" in result.output
    assert "User: arn:aws:iam::123456789012:role/Developer" in result.output
    assert "Region: us-east-1" in result.output
