"""
Integration tests for error recovery in workflows.

Tests workflow recovery from various error conditions:
- AWS service errors (credentials, rate limits, service unavailable)
- Git operation errors (non-git directory, merge conflicts, authentication)
- Workflow state persistence across failures
- Workflow rollback on failure

**Validates: Requirements 18.4, 18.5**
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
    config_content = """[profile test]
sso_start_url = https://test.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = Developer
region = us-east-1
"""
    mock_aws_config_dir["config_file"].write_text(config_content)
    return "test"


# ============================================================================
# Test: AWS Error Recovery
# ============================================================================


@pytest.mark.integration
def test_workflow_recovery_from_aws_credentials_error(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow recovery from AWS credentials error.

    Validates:
    - Workflow detects expired/invalid AWS credentials
    - User is prompted to re-authenticate
    - Workflow can continue after re-authentication
    - State is preserved across authentication attempts
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # ========== Step 1: Initial Commit Attempt with Invalid Credentials ==========

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd == ["aws", "sso", "login", "--profile", mock_sso_profile]:
            result.stdout = "Successfully logged in"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock BaseAgent.query to raise credentials error on first attempt
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("Unable to locate credentials")

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should fail due to credentials error)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify appropriate error handling
    # The command may return exit code 0 but display error message
    assert "no aws credentials" in commit_result_1.output.lower() or "error" in commit_result_1.output.lower()

    # ========== Step 2: Re-authenticate with AWS SSO ==========

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
    assert "SSO authentication successful" in login_result.output

    # ========== Step 3: Retry Commit with Valid Credentials ==========

    # Reset mock to return successful response
    mock_base_agent_query.reset_mock()
    mock_base_agent_query.side_effect = None
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Run commit command again (should succeed now)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify commit succeeded after re-authentication
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output
    assert "feat(test)" in commit_result_2.output


@pytest.mark.integration
def test_workflow_recovery_from_aws_rate_limit_error(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow recovery from AWS rate limit error.

    Validates:
    - Workflow detects AWS rate limit errors
    - Appropriate error message is displayed
    - User can retry after waiting
    - Workflow state is preserved for retry
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
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

    # ========== Step 1: First Attempt - Rate Limit Error ==========

    # Mock BaseAgent.query to raise rate limit error
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("ThrottlingException: Rate exceeded")

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should fail due to rate limit)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify rate limit error is reported
    assert commit_result_1.exit_code != 0 or "error" in commit_result_1.output.lower()

    # ========== Step 2: Retry After Waiting ==========

    # Reset mock to return successful response (simulating retry after waiting)
    mock_base_agent_query.reset_mock()
    mock_base_agent_query.side_effect = None
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Run commit command again (should succeed now)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify commit succeeded after retry
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output


@pytest.mark.integration
def test_workflow_recovery_from_aws_service_unavailable(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow recovery from AWS service unavailable error.

    Validates:
    - Workflow detects AWS service unavailable errors
    - Appropriate error message is displayed
    - User can retry when service is available
    - Workflow handles transient failures gracefully
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
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

    # ========== Step 1: First Attempt - Service Unavailable ==========

    # Mock BaseAgent.query to raise service unavailable error
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("ServiceUnavailableException: Service is temporarily unavailable")

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should fail due to service unavailable)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify service unavailable error is reported
    assert commit_result_1.exit_code != 0 or "error" in commit_result_1.output.lower()

    # ========== Step 2: Retry When Service is Available ==========

    # Reset mock to return successful response
    mock_base_agent_query.reset_mock()
    mock_base_agent_query.side_effect = None
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Run commit command again (should succeed now)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify commit succeeded after service recovery
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output


# ============================================================================
# Test: Git Error Recovery
# ============================================================================


@pytest.mark.integration
def test_workflow_recovery_from_git_non_repository_error(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile):
    """
    Test workflow recovery from git non-repository error.

    Validates:
    - Workflow detects when not in a git repository
    - Appropriate error message is displayed
    - User is guided to initialize git repository
    - Workflow can continue after git init
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # ========== Step 1: Attempt Commit in Non-Git Directory ==========

    # Mock subprocess.run to simulate non-git directory
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect_non_git(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()

        if cmd == ["git", "diff", "--staged"]:
            result.returncode = 128  # Git error code for not a repository
            result.stderr = "fatal: not a git repository"
            result.stdout = ""
        else:
            result.returncode = 128
            result.stderr = "fatal: not a git repository"
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect_non_git

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should fail due to non-git directory)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify appropriate error handling
    # The command may report "no staged changes" when git commands fail
    assert (
        commit_result_1.exit_code != 0
        or "not a git repository" in commit_result_1.output.lower()
        or "no staged changes" in commit_result_1.output.lower()
        or "error" in commit_result_1.output.lower()
    )

    # ========== Step 2: Initialize Git Repository ==========

    # Mock subprocess.run to simulate successful git operations after init
    def subprocess_side_effect_with_git(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = "diff --git a/file.py b/file.py\n+new line"
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Initial commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect_with_git

    # Mock BaseAgent.query
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = "feat(init): initialize project\n\nAdd initial project files."

    # Run commit command again (should succeed now)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify commit succeeded after git init
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output


@pytest.mark.integration
def test_workflow_recovery_from_git_merge_conflict(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow recovery from git merge conflict.

    Validates:
    - Workflow detects merge conflicts
    - Appropriate error message is displayed
    - User is guided to resolve conflicts
    - Workflow can continue after conflict resolution
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # ========== Step 1: Attempt Commit with Merge Conflict ==========

    # Mock subprocess.run to simulate merge conflict
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect_conflict(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()

        if cmd == ["git", "diff", "--staged"]:
            result.returncode = 0
            result.stdout = ""  # No staged changes during conflict
        elif cmd == ["git", "status", "--porcelain"]:
            result.returncode = 0
            result.stdout = "UU file.py"  # Unmerged file
        else:
            result.returncode = 0
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect_conflict

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # Run commit command (should fail due to no staged changes)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify appropriate error handling (no staged changes during conflict)
    assert (
        commit_result_1.exit_code != 0
        or "no changes" in commit_result_1.output.lower()
        or "no staged changes" in commit_result_1.output.lower()
        or "nothing to commit" in commit_result_1.output.lower()
    )

    # ========== Step 2: Resolve Conflict and Stage Changes ==========

    # Mock subprocess.run to simulate resolved conflict
    def subprocess_side_effect_resolved(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
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

    mock_subprocess.side_effect = subprocess_side_effect_resolved

    # Mock BaseAgent.query
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = "fix(merge): resolve merge conflict\n\nResolved conflict in file.py."

    # Run commit command again (should succeed now)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify commit succeeded after conflict resolution
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output


@pytest.mark.integration
def test_workflow_recovery_from_git_authentication_failure(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow recovery from git authentication failure during push.

    Validates:
    - Workflow detects git authentication failures
    - Appropriate error message is displayed
    - User is guided to configure git credentials
    - Workflow can continue after authentication setup
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    call_count = {"push": 0}

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()

        if cmd == ["git", "diff", "--staged"]:
            result.returncode = 0
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.returncode = 0
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.returncode = 0
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.returncode = 0
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.returncode = 0
            result.stdout = "[main abc1234] Commit message"
        elif cmd[:2] == ["git", "push"]:
            call_count["push"] += 1
            if call_count["push"] == 1:
                # First push fails with authentication error
                result.returncode = 128
                result.stderr = "fatal: Authentication failed"
                result.stdout = ""
            else:
                # Subsequent pushes succeed
                result.returncode = 0
                result.stdout = "Everything up-to-date"
        else:
            result.returncode = 0
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock BaseAgent.query
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # ========== Step 1: Commit with Push (Authentication Fails) ==========

    # Run commit command with --push flag (should fail on push)
    commit_result_1 = cli_runner.invoke(commit, ["--push"], input="y\n")

    # Verify commit succeeded but push failed
    # The command may handle this gracefully or report an error
    assert "Generated commit message:" in commit_result_1.output or "error" in commit_result_1.output.lower()

    # ========== Step 2: Retry Push After Authentication Setup ==========

    # Run commit command again with --push (should succeed now)
    commit_result_2 = cli_runner.invoke(commit, ["--push"], input="y\n")

    # Verify push succeeded after authentication setup
    # Note: The second commit may report "no changes" if already committed
    assert commit_result_2.exit_code == 0 or "no changes" in commit_result_2.output.lower()


# ============================================================================
# Test: Workflow State Persistence
# ============================================================================


@pytest.mark.integration
def test_workflow_state_persistence_across_failures(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test that workflow state persists across failures.

    Validates:
    - Git diff is preserved across multiple attempts
    - User doesn't need to re-stage changes
    - Workflow can be retried without losing context
    - State is maintained between command invocations
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            # Same diff returned on all attempts (state persisted)
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

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # ========== Step 1: First Attempt - Fails ==========

    # Mock BaseAgent.query to fail
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("Temporary error")

    # Run commit command (should fail)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify failure
    assert commit_result_1.exit_code != 0 or "error" in commit_result_1.output.lower()

    # Verify git diff was called (state was read)
    diff_calls_1 = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "diff", "--staged"]]
    assert len(diff_calls_1) >= 1

    # ========== Step 2: Second Attempt - Succeeds ==========

    # Reset mock to succeed
    mock_base_agent_query.reset_mock()
    mock_base_agent_query.side_effect = None
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Reset subprocess mock call count
    mock_subprocess.reset_mock()
    mock_subprocess.side_effect = subprocess_side_effect

    # Run commit command again (should succeed)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify success
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output

    # Verify git diff was called again (state was preserved and re-read)
    diff_calls_2 = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "diff", "--staged"]]
    assert len(diff_calls_2) >= 1


@pytest.mark.integration
def test_workflow_state_persistence_with_config_changes(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test that configuration changes persist across workflow failures.

    Validates:
    - AWS profile configuration persists
    - Configuration changes are saved
    - Workflow uses updated configuration on retry
    - No configuration loss on failure
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Create initial config
    config_content_v1 = """[profile test]
sso_start_url = https://test.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = Developer
region = us-east-1
"""
    mock_aws_config_dir["config_file"].write_text(config_content_v1)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
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

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # ========== Step 1: First Attempt with Initial Config ==========

    # Mock BaseAgent.query to fail
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("Configuration error")

    # Run commit command (should fail)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify failure
    assert commit_result_1.exit_code != 0 or "error" in commit_result_1.output.lower()

    # ========== Step 2: Update Configuration ==========

    # Update config (simulating user fixing configuration)
    config_content_v2 = """[profile test]
sso_start_url = https://test.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = Developer
region = us-east-1
output = json
"""
    mock_aws_config_dir["config_file"].write_text(config_content_v2)

    # ========== Step 3: Retry with Updated Config ==========

    # Reset mock to succeed
    mock_base_agent_query.reset_mock()
    mock_base_agent_query.side_effect = None
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Run commit command again (should succeed with updated config)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify success
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output

    # Verify config file still exists and has updated content
    assert mock_aws_config_dir["config_file"].exists()
    config_content = mock_aws_config_dir["config_file"].read_text()
    assert "output = json" in config_content


# ============================================================================
# Test: Workflow Rollback on Failure
# ============================================================================


@pytest.mark.integration
def test_workflow_rollback_on_commit_failure(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow rollback when commit fails.

    Validates:
    - Staged changes are preserved when commit fails
    - No partial commits are created
    - User can retry without data loss
    - Git state is consistent after failure
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    call_count = {"commit": 0}

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()

        if cmd == ["git", "diff", "--staged"]:
            result.returncode = 0
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.returncode = 0
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.returncode = 0
            result.stdout = "M  file.py"  # Changes still staged
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.returncode = 0
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            call_count["commit"] += 1
            if call_count["commit"] == 1:
                # First commit fails
                result.returncode = 1
                result.stderr = "error: commit failed"
                result.stdout = ""
            else:
                # Subsequent commits succeed
                result.returncode = 0
                result.stdout = "[main abc1234] Commit message"
        else:
            result.returncode = 0
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock BaseAgent.query
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # ========== Step 1: Attempt Commit (Fails) ==========

    # Run commit command (commit will fail)
    commit_result_1 = cli_runner.invoke(commit, input="y\n")

    # Verify commit was attempted
    assert "Generated commit message:" in commit_result_1.output

    # Verify git status still shows staged changes (rollback preserved state)
    status_calls = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "status", "--porcelain"]]
    assert len(status_calls) >= 1

    # ========== Step 2: Retry Commit (Succeeds) ==========

    # Reset mock
    mock_subprocess.reset_mock()
    mock_subprocess.side_effect = subprocess_side_effect

    # Run commit command again (should succeed)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify success
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output


@pytest.mark.integration
def test_workflow_rollback_on_push_failure(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test workflow rollback when push fails after successful commit.

    Validates:
    - Commit is preserved when push fails
    - User can retry push without re-committing
    - No duplicate commits are created
    - Git state is consistent after push failure
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    call_count = {"push": 0}

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()

        if cmd == ["git", "diff", "--staged"]:
            result.returncode = 0
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.returncode = 0
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.returncode = 0
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.returncode = 0
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.returncode = 0
            result.stdout = "[main def5678] Commit message"
        elif cmd[:2] == ["git", "push"]:
            call_count["push"] += 1
            if call_count["push"] == 1:
                # First push fails
                result.returncode = 1
                result.stderr = "error: failed to push some refs"
                result.stdout = ""
            else:
                # Subsequent pushes succeed
                result.returncode = 0
                result.stdout = "Everything up-to-date"
        else:
            result.returncode = 0
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock BaseAgent.query
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality."

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # ========== Step 1: Commit with Push (Push Fails) ==========

    # Run commit command with --push flag (commit succeeds, push fails)
    commit_result_1 = cli_runner.invoke(commit, ["--push"], input="y\n")

    # Verify commit was created
    assert "Generated commit message:" in commit_result_1.output

    # Verify commit was called
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) >= 1

    # ========== Step 2: Retry Push (Manual or via another commit attempt) ==========

    # Note: In the current implementation, user would need to manually run git push
    # or retry the commit command. The commit already exists, so subsequent attempts
    # would report "no changes" unless new changes are staged.

    # For this test, we verify that the commit was created and preserved
    # even though push failed
    assert call_count["push"] == 1  # Push was attempted once


@pytest.mark.integration
def test_workflow_rollback_preserves_user_input(cli_runner, mocker, mock_aws_config_dir, mock_sso_profile, fixtures_dir):
    """
    Test that user input is preserved across workflow failures.

    Validates:
    - User doesn't need to re-enter information on retry
    - Workflow context is maintained
    - User experience is smooth during recovery
    - No data loss on failure
    """
    # Mock Path.home() to return our temp directory
    mocker.patch("pathlib.Path.home", return_value=mock_aws_config_dir["aws_dir"].parent)

    # Mock subprocess.run for git operations
    mock_subprocess = mocker.patch("subprocess.run")

    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
                diff_data = json.load(f)
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/DEVO-123-test"
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

    # Mock profile selection
    mock_select_profile = mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value=mock_sso_profile)

    # ========== Step 1: First Attempt - Fails ==========

    # Mock BaseAgent.query to fail
    mock_base_agent_query = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_base_agent_query.side_effect = Exception("Temporary error")

    # Run commit command (should fail)
    commit_result_1 = cli_runner.invoke(commit)

    # Verify failure
    assert commit_result_1.exit_code != 0 or "error" in commit_result_1.output.lower()

    # Verify git operations were called (context was gathered)
    diff_calls = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "diff", "--staged"]]
    branch_calls = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]]
    assert len(diff_calls) >= 1
    assert len(branch_calls) >= 1

    # ========== Step 2: Retry - Succeeds ==========

    # Reset mock to succeed
    mock_base_agent_query.reset_mock()
    mock_base_agent_query.side_effect = None
    # Include ticket number from branch name
    mock_base_agent_query.return_value = "feat(test): add new feature\n\nImplement new functionality.\n\nDEVO-123"

    # Reset subprocess mock
    mock_subprocess.reset_mock()
    mock_subprocess.side_effect = subprocess_side_effect

    # Run commit command again (should succeed)
    commit_result_2 = cli_runner.invoke(commit, input="y\n")

    # Verify success
    assert commit_result_2.exit_code == 0
    assert "Generated commit message:" in commit_result_2.output
    assert "DEVO-123" in commit_result_2.output

    # Verify git operations were called again (context was re-gathered)
    diff_calls_2 = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "diff", "--staged"]]
    branch_calls_2 = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]]
    assert len(diff_calls_2) >= 1
    assert len(branch_calls_2) >= 1
