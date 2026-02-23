from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cli_tool.commands.commit_prompt import commit


@pytest.fixture
def runner():
    return CliRunner()


@patch("cli_tool.commands.commit_prompt.get_staged_diff")
@patch("cli_tool.commands.commit_prompt.get_branch_name")
@patch("cli_tool.commands.commit_prompt.get_remote_url")
@patch("cli_tool.commands.commit_prompt.BaseAgent")
@patch("cli_tool.commands.commit_prompt.subprocess.run")
@patch("cli_tool.commands.commit_prompt.webbrowser.open")
def test_commit_all_options(
    mock_webbrowser_open,
    mock_subprocess_run,
    mock_base_agent,
    mock_get_remote_url,
    mock_get_branch_name,
    mock_get_staged_diff,
    runner,
):
    # Mock external dependencies
    mock_get_staged_diff.return_value = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    mock_get_branch_name.return_value = "feature/TICKET-123"
    mock_get_remote_url.return_value = "https://github.com/edu526/devo-cli"

    # Mock git commands and operations in sequence
    mock_subprocess_run.side_effect = [
        None,  # git add .
        MagicMock(stdout="M  file.txt"),  # git status
        MagicMock(stdout="abc123 Previous commit"),  # git log
        None,  # git commit
        None,  # git push
    ]

    # Mock AI agent with text response
    mock_agent_instance = MagicMock()
    mock_agent_instance.query.return_value = "feat(cli): Add new feature\n\n- Added a new feature to the CLI."
    mock_base_agent.return_value = mock_agent_instance

    # Run the command with --all flag
    result = runner.invoke(commit, ["--all"], input="y\n")

    # Assertions
    assert result.exit_code == 0
    assert "Adding all changes to the staging area..." in result.output
    assert "✅ All changes added." in result.output
    assert "✅ Commit message accepted" in result.output
    assert "✅ Changes pushed to origin/feature/TICKET-123" in result.output

    # Verify git operations were called
    mock_subprocess_run.assert_any_call(["git", "add", "."], check=True)
    mock_subprocess_run.assert_any_call(
        [
            "git",
            "commit",
            "-m",
            "feat(cli): TICKET-123 Add new feature\n\n- Added a new feature to the CLI.",
        ],
        check=True,
    )
    mock_subprocess_run.assert_any_call(["git", "push", "origin", "feature/TICKET-123"], check=True)

    # Verify webbrowser was opened for PR
    mock_webbrowser_open.assert_called_once()


@patch("cli_tool.commands.commit_prompt.get_staged_diff")
@patch("cli_tool.commands.commit_prompt.get_branch_name")
@patch("cli_tool.commands.commit_prompt.BaseAgent")
@patch("cli_tool.commands.commit_prompt.subprocess.run")
def test_commit_manual_message_with_ticket(
    mock_subprocess_run,
    mock_base_agent,
    mock_get_branch_name,
    mock_get_staged_diff,
    runner,
):
    # Mock external dependencies
    mock_get_staged_diff.return_value = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    mock_get_branch_name.return_value = "feature/TICKET-456"

    # Mock git commands
    mock_subprocess_run.side_effect = [
        MagicMock(stdout="M  file.txt"),  # git status
        MagicMock(stdout="abc123 Previous commit"),  # git log
        None,  # git commit
    ]

    # Mock AI agent with text response
    mock_agent_instance = MagicMock()
    mock_agent_instance.query.return_value = "fix(auth): Fix a bug\n\n- Fixed a critical bug."
    mock_base_agent.return_value = mock_agent_instance

    # Simulate user rejecting AI message and providing their own
    result = runner.invoke(commit, input="n\nMy manual commit message\n")

    assert result.exit_code == 0
    assert "Enter your commit message" in result.output

    # Check that git commit was called with the manual message, including the ticket number
    commit_calls = [call_args for call_args in mock_subprocess_run.call_args_list if call_args[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1
    commit_message = commit_calls[0][0][0][3]  # The message argument (after -m)
    assert "TICKET-456" in commit_message
    assert "My manual commit message" in commit_message


@patch("cli_tool.commands.commit_prompt.get_staged_diff")
@patch("cli_tool.commands.commit_prompt.get_branch_name")
@patch("cli_tool.commands.commit_prompt.BaseAgent")
@patch("cli_tool.commands.commit_prompt.subprocess.run")
def test_commit_aws_credentials_error(
    mock_subprocess_run,
    mock_base_agent,
    mock_get_branch_name,
    mock_get_staged_diff,
    runner,
):
    # Mock external dependencies
    mock_get_staged_diff.return_value = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    mock_get_branch_name.return_value = "feature/TICKET-789"

    # Mock git commands
    mock_subprocess_run.side_effect = [
        MagicMock(stdout="M  file.txt"),  # git status
        MagicMock(stdout="abc123 Previous commit"),  # git log
    ]

    # Mock AI agent to raise credentials error
    mock_agent_instance = MagicMock()
    mock_agent_instance.query.side_effect = Exception("NoCredentialsError: Unable to locate credentials")
    mock_base_agent.return_value = mock_agent_instance

    result = runner.invoke(commit)

    assert result.exit_code == 0
    assert "❌ No AWS credentials found. Please configure your AWS CLI." in result.output


@patch("cli_tool.commands.commit_prompt.get_staged_diff")
@patch("cli_tool.commands.commit_prompt.get_branch_name")
@patch("cli_tool.commands.commit_prompt.BaseAgent")
@patch("cli_tool.commands.commit_prompt.subprocess.run")
def test_commit_general_error(
    mock_subprocess_run,
    mock_base_agent,
    mock_get_branch_name,
    mock_get_staged_diff,
    runner,
):
    # Mock external dependencies
    mock_get_staged_diff.return_value = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    mock_get_branch_name.return_value = "feature/TICKET-999"

    # Mock git commands
    mock_subprocess_run.side_effect = [
        MagicMock(stdout="M  file.txt"),  # git status
        MagicMock(stdout="abc123 Previous commit"),  # git log
    ]

    # Mock AI agent to raise general error
    mock_agent_instance = MagicMock()
    mock_agent_instance.query.side_effect = Exception("Some other error")
    mock_base_agent.return_value = mock_agent_instance

    result = runner.invoke(commit)

    assert result.exit_code == 0
    assert "❌ Error sending request: Some other error" in result.output


@patch("cli_tool.commands.commit_prompt.get_staged_diff")
@patch("cli_tool.commands.commit_prompt.get_branch_name")
@patch("cli_tool.commands.commit_prompt.BaseAgent")
@patch("cli_tool.commands.commit_prompt.subprocess.run")
def test_commit_no_ticket_in_branch(
    mock_subprocess_run,
    mock_base_agent,
    mock_get_branch_name,
    mock_get_staged_diff,
    runner,
):
    # Mock external dependencies
    mock_get_staged_diff.return_value = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    mock_get_branch_name.return_value = "main"  # No ticket number in branch name

    # Mock git commands
    mock_subprocess_run.side_effect = [
        MagicMock(stdout="M  file.txt"),  # git status
        MagicMock(stdout="abc123 Previous commit"),  # git log
        None,  # git commit
    ]

    # Mock AI agent with text response
    mock_agent_instance = MagicMock()
    mock_agent_instance.query.return_value = "refactor(core): Refactor core components"
    mock_base_agent.return_value = mock_agent_instance

    result = runner.invoke(commit, input="y\n")

    assert result.exit_code == 0
    commit_message = "refactor(core): Refactor core components"
    mock_subprocess_run.assert_any_call(["git", "commit", "-m", commit_message], check=True)
    assert "TICKET-" not in result.output


def test_commit_no_staged_changes(runner):
    with patch("cli_tool.commands.commit_prompt.get_staged_diff") as mock_get_staged_diff:
        mock_get_staged_diff.return_value = ""

        result = runner.invoke(commit)

        assert result.exit_code == 0
        assert "No staged changes found." in result.output


@patch("cli_tool.commands.commit_prompt.get_staged_diff")
@patch("cli_tool.commands.commit_prompt.get_branch_name")
@patch("cli_tool.commands.commit_prompt.BaseAgent")
@patch("cli_tool.commands.commit_prompt.subprocess.run")
def test_commit_structured_output(
    mock_subprocess_run,
    mock_base_agent,
    mock_get_branch_name,
    mock_get_staged_diff,
    runner,
):
    # Mock external dependencies
    mock_get_staged_diff.return_value = "diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-hello\n+world"
    mock_get_branch_name.return_value = "feature/TICKET-111"

    # Mock git commands
    mock_subprocess_run.side_effect = [
        MagicMock(stdout="M  file.txt"),  # git status
        MagicMock(stdout="abc123 Previous commit"),  # git log
        None,  # git commit
    ]

    # Mock AI agent with text response
    mock_agent_instance = MagicMock()
    mock_agent_instance.query.return_value = "feat(api): Add new endpoint for user management"
    mock_base_agent.return_value = mock_agent_instance

    result = runner.invoke(commit, input="y\n")

    assert result.exit_code == 0

    # Should commit with the structured response
    commit_calls = [call_args for call_args in mock_subprocess_run.call_args_list if call_args[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1
    commit_message = commit_calls[0][0][0][3]  # The message argument (after -m)
    assert "feat(api): TICKET-111 Add new endpoint for user management" in commit_message
