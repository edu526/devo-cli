"""
Integration tests for commit command message generation.

Tests the complete commit workflow including:
- Commit message generation with staged changes
- Error handling for no staged changes
- Interactive confirmation and rejection flows
- --all flag behavior (add, commit, push)
- Git operations mocking
- AI agent response mocking
"""

import json
from unittest.mock import MagicMock, call

import pytest
from click.testing import CliRunner

from cli_tool.commands.commit.commands.generate import commit


@pytest.fixture
def mock_subprocess(mocker):
    """Mock subprocess.run for git operations."""
    return mocker.patch("subprocess.run")


@pytest.fixture
def mock_base_agent_query(mocker):
    """Mock BaseAgent.query for AI responses."""
    return mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")


@pytest.fixture
def mock_select_profile(mocker):
    """Mock profile selection to avoid interactive prompts."""
    return mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value="default")


@pytest.mark.integration
def test_commit_generation_with_staged_changes(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit message generation with staged changes."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/DEVO-123-test-feature"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  cli_tool/commands/commit/core/generator.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit\ndef5678 Another commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock AI response
    mock_base_agent_query.return_value = (
        "feat(commit): add validation for empty diffs\n\nAdded validation logic to prevent generating commit messages for empty diffs."
    )

    # Run commit command with confirmation
    result = cli_runner.invoke(commit, input="y\n")

    # Verify success
    assert result.exit_code == 0
    assert "Generating commit message..." in result.output
    assert "Generated commit message:" in result.output
    assert "feat(commit)" in result.output
    assert "DEVO-123" in result.output  # Ticket extracted from branch

    # Verify git commit was called
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1
    assert "DEVO-123" in commit_calls[0][0][0][3]  # Ticket in commit message


@pytest.mark.integration
def test_commit_with_no_staged_changes(cli_runner, mock_subprocess, mock_select_profile):
    """Test commit command with no staged changes returns error."""

    # Mock git diff to return empty
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Run commit command
    result = cli_runner.invoke(commit)

    # Verify error message
    assert "No staged changes found." in result.output
    assert result.exit_code == 0  # Command exits gracefully


@pytest.mark.integration
def test_commit_with_all_flag(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile, mocker):
    """Test commit with --all flag stages and commits."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "add", "."]:
            result.stdout = ""
        elif cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  cli_tool/commands/commit/core/generator.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        elif cmd[:2] == ["git", "push"]:
            result.stdout = "Pushed to origin/main"
        elif cmd == ["git", "config", "--get", "remote.origin.url"]:
            result.stdout = "https://github.com/user/repo.git"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock AI response
    mock_base_agent_query.return_value = "feat(commit): add validation for empty diffs"

    # Mock webbrowser.open to avoid opening browser
    mock_webbrowser = mocker.patch("cli_tool.commands.commit.commands.generate.webbrowser.open")

    # Run commit command with --all flag
    result = cli_runner.invoke(commit, ["--all"], input="y\n")

    # Verify success
    assert result.exit_code == 0
    assert "Adding all changes to the staging area..." in result.output
    assert "✅ All changes added." in result.output
    assert "Pushing changes to origin/main..." in result.output
    assert "✅ Changes pushed to origin/main" in result.output

    # Verify git add was called
    add_calls = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "add", "."]]
    assert len(add_calls) == 1

    # Verify git push was called
    push_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "push"]]
    assert len(push_calls) == 1

    # Verify browser was opened for PR
    assert mock_webbrowser.called


@pytest.mark.integration
def test_commit_with_interactive_confirmation(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit with interactive confirmation (input='y\\n')."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
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

    # Mock AI response
    mock_base_agent_query.return_value = "feat(test): add new feature"

    # Run commit command with 'y' confirmation
    result = cli_runner.invoke(commit, input="y\n")

    # Verify success
    assert result.exit_code == 0
    assert "✅ Commit message accepted" in result.output

    # Verify git commit was called with AI-generated message
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1


@pytest.mark.integration
def test_commit_with_rejection(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit with rejection (input='n\\n')."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/DEVO-456-custom-feature"
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

    # Mock AI response
    mock_base_agent_query.return_value = "feat(test): add new feature"

    # Run commit command with 'n' rejection and manual message
    result = cli_runner.invoke(commit, input="n\nfix: manual commit message\n")

    # Verify success
    assert result.exit_code == 0
    assert "✅ Manual commit message accepted" in result.output

    # Verify git commit was called with manual message
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1
    # Manual message should have ticket prepended
    assert "DEVO-456" in commit_calls[0][0][0][3]


@pytest.mark.integration
def test_commit_with_add_flag(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit with --add flag stages changes before committing."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "add", "."]:
            result.stdout = ""
        elif cmd == ["git", "diff", "--staged"]:
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

    # Mock AI response
    mock_base_agent_query.return_value = "feat(test): add new feature"

    # Run commit command with --add flag
    result = cli_runner.invoke(commit, ["--add"], input="y\n")

    # Verify success
    assert result.exit_code == 0
    assert "Adding all changes to the staging area..." in result.output
    assert "✅ All changes added." in result.output

    # Verify git add was called
    add_calls = [c for c in mock_subprocess.call_args_list if c[0][0] == ["git", "add", "."]]
    assert len(add_calls) == 1


@pytest.mark.integration
def test_commit_with_push_flag(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit with --push flag pushes after committing."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/test-branch"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  file.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        elif cmd[:2] == ["git", "push"]:
            result.stdout = "Pushed to origin/feature/test-branch"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock AI response
    mock_base_agent_query.return_value = "feat(test): add new feature"

    # Run commit command with --push flag
    result = cli_runner.invoke(commit, ["--push"], input="y\n")

    # Verify success
    assert result.exit_code == 0
    assert "Pushing changes to origin/feature/test-branch..." in result.output
    assert "✅ Changes pushed to origin/feature/test-branch" in result.output

    # Verify git push was called
    push_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "push"]]
    assert len(push_calls) == 1
    assert push_calls[0][0][0] == ["git", "push", "origin", "feature/test-branch"]


# Edge case tests for commit command


@pytest.mark.integration
def test_commit_with_binary_file_changes(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit with binary file changes."""
    # Load fixture data with binary file
    with open(fixtures_dir / "git_diffs" / "binary_file_change.json") as f:
        diff_data = json.load(f)

    # Combine diffs from all files
    combined_diff = "\n".join([file["diff"] for file in diff_data["files"]])

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = combined_diff
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/update-logo"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  assets/logo.png\nM  cli_tool/commands/commit/core/generator.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock AI response - should handle binary files gracefully
    mock_base_agent_query.return_value = "chore(assets): update logo image\n\nUpdated logo.png and related code references."

    # Run commit command
    result = cli_runner.invoke(commit, input="y\n")

    # Verify success - binary files should be handled
    assert result.exit_code == 0
    assert "Generated commit message:" in result.output
    assert "chore(assets)" in result.output

    # Verify git commit was called
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1


@pytest.mark.integration
def test_commit_with_very_large_diff(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit with very large diffs (150+ lines)."""
    # Load fixture data with large diff
    with open(fixtures_dir / "git_diffs" / "large_diff.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/dynamodb-exporter"
        elif cmd == ["git", "status", "--porcelain"]:
            result.stdout = "M  cli_tool/commands/dynamodb/core/exporter.py"
        elif cmd == ["git", "log", "--oneline", "-10"]:
            result.stdout = "abc1234 Previous commit"
        elif cmd[:2] == ["git", "commit"]:
            result.stdout = "[main abc1234] Commit message"
        else:
            result.stdout = ""

        return result

    mock_subprocess.side_effect = subprocess_side_effect

    # Mock AI response - should handle large diffs
    mock_base_agent_query.return_value = (
        "feat(dynamodb): add comprehensive table export functionality\n\n"
        "Implemented DynamoDB exporter with support for multiple formats (JSON, CSV, JSONL), "
        "parallel scanning, compression, and progress tracking."
    )

    # Run commit command
    result = cli_runner.invoke(commit, input="y\n")

    # Verify success - large diffs should be handled
    assert result.exit_code == 0
    assert "Generated commit message:" in result.output
    assert "feat(dynamodb)" in result.output

    # Verify git commit was called
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1

    # Verify AI was called with the large diff
    assert mock_base_agent_query.called
    # Verify the AI agent was called (the diff is passed internally)
    assert mock_base_agent_query.call_count == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    "branch_name,expected_ticket",
    [
        ("feature/DEVO-123-add-feature", "DEVO-123"),
        ("fix/PROJ-456-fix-bug", "PROJ-456"),
        ("chore/ABC-789-urgent-fix", "ABC-789"),
        ("feature/TICKET-999-some-feature", "TICKET-999"),
        ("chore/TASK-111-update-deps", "TASK-111"),
    ],
)
def test_commit_with_ticket_extraction_from_branch_name(
    cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile, branch_name, expected_ticket
):
    """Test commit with ticket extraction from branch name.

    Tests that tickets are extracted from branch names following the pattern:
    (feature|fix|chore)/TICKET-NUMBER-description
    """
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = branch_name
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

    # Mock AI response without ticket
    mock_base_agent_query.return_value = "feat(commit): add validation for empty diffs"

    # Run commit command
    result = cli_runner.invoke(commit, input="y\n")

    # Verify success
    assert result.exit_code == 0, f"Failed for branch: {branch_name}"

    # Verify git commit was called with ticket prepended
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1, f"Expected 1 commit call, got {len(commit_calls)} for branch {branch_name}"
    # Check that the ticket is in the commit message
    commit_message = commit_calls[0][0][0][3]
    assert expected_ticket in commit_message, f"Ticket {expected_ticket} not in commit message '{commit_message}' for branch {branch_name}"


@pytest.mark.integration
def test_commit_with_custom_message_template(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit with custom message template (manual message entry)."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "feature/CUSTOM-999-template-test"
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

    # Mock AI response
    mock_base_agent_query.return_value = "feat(commit): add validation for empty diffs"

    # Test custom message templates
    custom_messages = [
        "fix: resolve memory leak in exporter",
        "docs: update README with new examples",
        "refactor(core): simplify agent initialization",
        "test: add integration tests for commit command",
        "chore: bump dependencies to latest versions",
    ]

    for custom_message in custom_messages:
        # Run commit command with rejection and custom message
        result = cli_runner.invoke(commit, input=f"n\n{custom_message}\n")

        # Verify success
        assert result.exit_code == 0, f"Failed for custom message: {custom_message}"
        assert "✅ Manual commit message accepted" in result.output

        # Verify git commit was called with custom message
        commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
        assert len(commit_calls) >= 1, f"No commit calls found for custom message: {custom_message}"

        # Check that the custom message is in the commit (with ticket prepended)
        last_commit_call = commit_calls[-1]
        commit_message = last_commit_call[0][0][3]
        assert "CUSTOM-999" in commit_message, f"Ticket not prepended to custom message: {custom_message}"
        # The custom message should be in the commit (after the ticket)
        assert custom_message.split(":")[0] in commit_message, f"Custom message type not found: {custom_message}"

        # Reset mocks for next iteration
        mock_subprocess.reset_mock()
        mock_base_agent_query.reset_mock()


@pytest.mark.integration
def test_commit_with_no_ticket_in_branch_name(cli_runner, fixtures_dir, mock_subprocess, mock_base_agent_query, mock_select_profile):
    """Test commit when branch name has no ticket number."""
    # Load fixture data
    with open(fixtures_dir / "git_diffs" / "simple_change.json") as f:
        diff_data = json.load(f)

    # Mock git operations with branch name without ticket
    def subprocess_side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        result = MagicMock()
        result.returncode = 0

        if cmd == ["git", "diff", "--staged"]:
            result.stdout = diff_data["diff"]
        elif cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            result.stdout = "main"  # No ticket in branch name
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

    # Mock AI response
    mock_base_agent_query.return_value = "feat(commit): add validation for empty diffs"

    # Run commit command
    result = cli_runner.invoke(commit, input="y\n")

    # Verify success - should work without ticket
    assert result.exit_code == 0
    assert "Generated commit message:" in result.output
    assert "feat(commit)" in result.output

    # Verify git commit was called
    commit_calls = [c for c in mock_subprocess.call_args_list if c[0][0][:2] == ["git", "commit"]]
    assert len(commit_calls) == 1

    # Commit message should not have a ticket prepended
    commit_message = commit_calls[0][0][0][3]
    assert commit_message.startswith("feat(commit)"), "Commit message should start with type, not ticket"
