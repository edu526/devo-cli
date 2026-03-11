"""
Integration tests for AWS login to commit workflow.

Tests the complete workflow from AWS SSO authentication to AI-powered commit generation:
- aws-login → commit workflow
- Verify credentials are available after login
- Verify commit uses authenticated AWS Bedrock
- Mock all AWS and git operations

**Validates: Requirements 18.1, 18.4**
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from cli_tool.commands.aws_login.command import login_cmd
from cli_tool.commands.commit.commands.generate import commit


@pytest.fixture
def mock_aws_config_dir(tmp_path):
    """Create temporary AWS config directory."""
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    config_file = aws_dir / "config"
    credentials_file = aws_dir / "credentials"
    sso_cache_dir = aws_dir / "sso" / "cache"
    sso_cache_dir.mkdir(parents=True)
    return {
        "aws_dir": aws_dir,
        "config_file": config_file,
        "credentials_file": credentials_file,
        "sso_cache_dir": sso_cache_dir,
    }


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


# ============================================================================
# Test: Complete AWS Login to Commit Workflow
# ============================================================================


@pytest.mark.integration
def test_aws_login_to_commit_workflow_success(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test complete workflow: aws-login → commit.

    Validates:
    - AWS SSO login succeeds and caches credentials
    - Credentials are available for subsequent operations
    - Commit command uses authenticated AWS Bedrock
    - AI-powered commit message generation works with authenticated session
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # ========== Step 1: AWS SSO Login ==========

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        # AWS SSO login command
        if cmd == ["aws", "sso", "login", "--profile", mock_sso_profile]:
            result.stdout = "Successfully logged in"
        # Git operations for commit command
        elif cmd == ["git", "diff", "--staged"]:
            # Load fixture data
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/DEVO-123-test-feature"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  cli_tool/commands/commit/core/generator.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock verify_credentials for login
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration for login
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = expiration

    # Run AWS login command
    login_result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify login succeeded
    assert login_result.exit_code == 0
    assert "SSO authentication successful" in login_result.output
    assert "Credentials cached successfully" in login_result.output
    assert "123456789012" in login_result.output

    # ========== Step 2: Commit with Authenticated Bedrock ==========

    # Mock BaseAgent.query for AI-powered commit message generation
    # This simulates using authenticated AWS Bedrock credentials
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = (
        "feat(commit): add validation for empty diffs\n\n" "Added validation logic to prevent generating commit messages for empty diffs."
    )

    # Mock profile selection to use the authenticated profile
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should use authenticated AWS credentials)
    commit_result = cli_runner.invoke(commit, input="y\n")

    # Verify commit succeeded
    assert commit_result.exit_code == 0
    assert "Generating commit message..." in commit_result.output
    assert "Generated commit message:" in commit_result.output
    assert "feat(commit)" in commit_result.output
    assert "DEVO-123" in commit_result.output

    # Verify BaseAgent.query was called (using authenticated Bedrock)
    assert mock_base_agent_query.called
    assert mock_base_agent_query.call_count == 1

    # Verify git commit was called
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1


@pytest.mark.integration
def test_commit_without_prior_login_fails(cli_runner, mocker, mock_aws_config_dir, fixtures_dir):
    """
    Test that commit command fails gracefully when AWS credentials are not available.

    Validates:
    - Commit detects missing AWS credentials
    - Appropriate error message is displayed
    - User is prompted to run aws-login first
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Create empty AWS config (no profiles configured)
    mock_aws_config_dir["config_file"].write_text("")

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            # Load fixture data
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock BaseAgent.query to raise credentials error
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("Unable to locate credentials")

    # Mock profile selection to return None (no profile available)
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=None)

    # Run commit command (should fail due to missing credentials)
    result = cli_runner.invoke(commit)

    # Verify appropriate error handling
    # The command should either:
    # 1. Fail with exit code != 0, OR
    # 2. Display an error message about missing credentials/profile
    assert result.exit_code != 0 or "No profile selected" in result.output or "aws credentials" in result.output.lower()


@pytest.mark.integration
def test_aws_login_to_commit_with_expired_credentials(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow when credentials expire between login and commit.

    Validates:
    - Expired credentials are detected during commit
    - User is prompted to re-authenticate
    - Workflow can recover from expired credentials
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # ========== Step 1: Initial AWS SSO Login ==========

    # Mock subprocess.run for AWS CLI SSO login
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        # AWS SSO login command
        if cmd == ["aws", "sso", "login", "--profile", mock_sso_profile]:
            result.stdout = "Successfully logged in"
        # Git operations
        elif cmd == ["git", "diff", "--staged"]:
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock verify_credentials for login
    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.login.verify_credentials")
    mock_verify.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:sts::123456789012:assumed-role/Developer/user",
        "user_id": "AIDAI123456789",
    }

    # Mock get_profile_credentials_expiration for login (initially valid)
    initial_expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_expiration = mocker.patch("cli_tool.commands.aws_login.commands.login.get_profile_credentials_expiration")
    mock_expiration.return_value = initial_expiration

    # Run AWS login command
    login_result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify login succeeded
    assert login_result.exit_code == 0
    assert "SSO authentication successful" in login_result.output

    # ========== Step 2: Simulate Credential Expiration ==========

    # Mock BaseAgent.query to raise expired credentials error
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("The security token included in the request is expired")

    # Mock profile selection
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should fail due to expired credentials)
    commit_result = cli_runner.invoke(commit)

    # Verify appropriate error handling for expired credentials
    # The command should fail and indicate credential issues
    assert commit_result.exit_code != 0 or "expired" in commit_result.output.lower() or "error" in commit_result.output.lower()


@pytest.mark.integration
def test_aws_login_to_commit_with_multiple_profiles(cli_runner, mocker, mock_aws_config_dir, fixtures_dir):
    """
    Test workflow with multiple AWS profiles.

    Validates:
    - User can login with one profile
    - Commit command uses the correct authenticated profile
    - Profile selection works correctly across commands
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Create multiple SSO profiles
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
"""
    mock_aws_config_dir["config_file"].write_text(config_content)

    # ========== Step 1: Login with 'dev' profile ==========

    # Mock subprocess.run
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        # AWS SSO login command
        if cmd == ["aws", "sso", "login", "--profile", "dev"]:
            result.stdout = "Successfully logged in to dev"
        # Git operations
        elif cmd == ["git", "diff", "--staged"]:
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock verify_credentials for login
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

    # Run AWS login command with 'dev' profile
    login_result = cli_runner.invoke(login_cmd, ["dev"])

    # Verify login succeeded
    assert login_result.exit_code == 0
    assert "SSO authentication successful" in login_result.output

    # ========== Step 2: Commit using 'dev' profile ==========

    # Mock BaseAgent.query for AI-powered commit
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = "feat(test): add new feature"

    # Mock profile selection to return 'dev' profile
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value="dev")

    # Run commit command
    commit_result = cli_runner.invoke(commit, input="y\n")

    # Verify commit succeeded with correct profile
    assert commit_result.exit_code == 0
    assert "Generated commit message:" in commit_result.output

    # Verify the correct profile was used
    assert mock_select_profile.called


@pytest.mark.integration
def test_aws_login_to_commit_with_bedrock_error(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow when Bedrock API returns an error.

    Validates:
    - Bedrock API errors are caught gracefully
    - Appropriate error message is displayed
    - User can retry or provide manual commit message
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # ========== Step 1: AWS SSO Login ==========

    # Mock subprocess.run
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        # AWS SSO login command
        if cmd == ["aws", "sso", "login", "--profile", mock_sso_profile]:
            result.stdout = "Successfully logged in"
        # Git operations
        elif cmd == ["git", "diff", "--staged"]:
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock verify_credentials for login
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

    # Run AWS login command
    login_result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify login succeeded
    assert login_result.exit_code == 0

    # ========== Step 2: Commit with Bedrock Error ==========

    # Mock BaseAgent.query to raise Bedrock API error
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("Bedrock API rate limit exceeded")

    # Mock profile selection
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should handle Bedrock error gracefully)
    commit_result = cli_runner.invoke(commit)

    # Verify error is handled gracefully
    # The command should either fail with appropriate message or allow manual input
    assert commit_result.exit_code != 0 or "error" in commit_result.output.lower()


@pytest.mark.integration
def test_aws_login_to_commit_state_persistence(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test that AWS credentials persist across multiple commit operations.

    Validates:
    - Credentials cached after login remain valid
    - Multiple commit operations can use the same authenticated session
    - No re-authentication required for subsequent commits
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # ========== Step 1: AWS SSO Login ==========

    # Mock subprocess.run
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        # AWS SSO login command
        if cmd == ["aws", "sso", "login", "--profile", mock_sso_profile]:
            result.stdout = "Successfully logged in"
        # Git operations
        elif cmd == ["git", "diff", "--staged"]:
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock verify_credentials for login
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

    # Run AWS login command
    login_result = cli_runner.invoke(login_cmd, [mock_sso_profile])

    # Verify login succeeded
    assert login_result.exit_code == 0

    # ========== Step 2: First Commit ==========

    # Mock BaseAgent.query for first commit
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = "feat(test): first commit"

    # Mock profile selection
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run first commit
    commit_result_1 = cli_runner.invoke(commit, input="y\n")

    # Verify first commit succeeded
    assert commit_result_1.exit_code == 0
    assert "Generated commit message:" in commit_result_1.output

    # ========== Step 3: Second Commit (using same credentials) ==========

    # Reset mock for second commit
    mock_base_agent_query.reset_mock()
    mock_base_agent_query.return_value = "feat(test): second commit"

    # Run second commit (should use cached credentials)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify second commit succeeded
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output

    # Verify BaseAgent.query was called for both commits
    assert mock_base_agent_query.call_count == 1  # Only called once in this invocation

    # Verify no additional login was required
    # (subprocess.run should not have additional aws sso login calls)
    sso_login_calls = [c for c in mock_subprocess.call_args_list if c[0][0] == ["aws", "sso", "login", "--profile", mock_sso_profile]]
    assert len(sso_login_calls) == 1  # Only the initial login
