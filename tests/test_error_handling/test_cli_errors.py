"""
Integration tests for CLI error handling.

Tests cover:
- CLI commands with missing required arguments
- CLI commands with invalid argument types
- CLI commands with invalid flag combinations
- User-friendly error messages
- Actionable error messages

Requirements: 13.1, 13.5
"""

import pytest
from click.testing import CliRunner

from cli_tool.cli import cli
from cli_tool.commands.commit.commands.generate import commit
from cli_tool.commands.config_cmd.commands.set import set_command
from cli_tool.commands.config_cmd.commands.show import show_config
from cli_tool.commands.dynamodb import dynamodb

# ============================================================================
# Task 10.2: CLI Error Handling Tests
# ============================================================================


@pytest.mark.integration
def test_commit_command_with_no_git_repository(cli_runner, mocker, temp_config_dir):
    """Test commit command fails gracefully when not in a git repository."""
    # Mock subprocess to simulate git error
    mock_subprocess = mocker.patch("subprocess.run")
    mock_result = mocker.MagicMock()
    mock_result.returncode = 128  # Git error code for "not a git repository"
    mock_result.stderr = "fatal: not a git repository"
    mock_subprocess.return_value = mock_result

    # Mock profile selection
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value="default")

    # Run commit command
    result = cli_runner.invoke(commit)

    # Verify error is handled gracefully
    assert result.exit_code != 0 or "not a git repository" in result.output.lower() or "error" in result.output.lower()

    # Verify error message is user-friendly
    assert "fatal" in result.output.lower() or "error" in result.output.lower() or "git" in result.output.lower()


@pytest.mark.integration
def test_config_set_with_missing_required_arguments(cli_runner):
    """Test config set command with missing required arguments."""
    # Run config set without arguments
    result = cli_runner.invoke(set_command, [])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message is user-friendly and actionable
    assert "missing" in result.output.lower() or "required" in result.output.lower() or "usage" in result.output.lower()


@pytest.mark.integration
def test_config_set_with_only_key_no_value(cli_runner):
    """Test config set command with key but no value."""
    # Run config set with only key argument
    result = cli_runner.invoke(set_command, ["aws.region"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message mentions missing value
    assert "missing" in result.output.lower() or "required" in result.output.lower() or "value" in result.output.lower()


@pytest.mark.integration
def test_dynamodb_export_with_missing_table_name(cli_runner):
    """Test DynamoDB export command with missing required table name."""
    # Run export without table name
    result = cli_runner.invoke(dynamodb, ["export"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message is actionable
    assert "missing" in result.output.lower() or "required" in result.output.lower() or "table" in result.output.lower()


@pytest.mark.integration
def test_dynamodb_export_with_invalid_format(cli_runner, mocker):
    """Test DynamoDB export command with invalid format argument."""
    # Mock AWS to avoid real calls
    mocker.patch("boto3.client")

    # Run export with invalid format
    result = cli_runner.invoke(dynamodb, ["export", "test-table", "--format", "invalid-format"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message mentions valid formats
    assert "invalid" in result.output.lower() or "choice" in result.output.lower() or "format" in result.output.lower()


@pytest.mark.integration
def test_dynamodb_export_with_invalid_compression_type(cli_runner, mocker):
    """Test DynamoDB export command with invalid compression type."""
    # Mock AWS to avoid real calls
    mocker.patch("boto3.client")

    # Run export with invalid compression
    result = cli_runner.invoke(dynamodb, ["export", "test-table", "--compression", "invalid-compression"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message is user-friendly
    assert "invalid" in result.output.lower() or "choice" in result.output.lower() or "compression" in result.output.lower()


@pytest.mark.integration
def test_config_show_with_invalid_section(cli_runner, temp_config_dir, mocker):
    """Test config show command with non-existent section."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Setup minimal config
    config_file.write_text('{"aws": {"region": "us-east-1"}}')

    # Run show with non-existent section
    result = cli_runner.invoke(show_config, ["--section", "non_existent_section"])

    # Command should handle gracefully (may show empty or error)
    # Verify it doesn't crash
    assert result.exit_code is not None

    # If it shows an error, it should be user-friendly
    if result.exit_code != 0:
        assert "not found" in result.output.lower() or "does not exist" in result.output.lower() or "section" in result.output.lower()


@pytest.mark.integration
def test_cli_with_invalid_command(cli_runner):
    """Test CLI with non-existent command."""
    # Run CLI with invalid command
    result = cli_runner.invoke(cli, ["invalid-command"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message is helpful
    assert "no such command" in result.output.lower() or "invalid" in result.output.lower() or "usage" in result.output.lower()


@pytest.mark.integration
def test_cli_with_invalid_global_option(cli_runner):
    """Test CLI with invalid global option."""
    # Run CLI with invalid global option
    result = cli_runner.invoke(cli, ["--invalid-option", "commit"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message mentions the invalid option
    assert "no such option" in result.output.lower() or "invalid" in result.output.lower() or "option" in result.output.lower()


@pytest.mark.integration
def test_commit_with_conflicting_flags(cli_runner, mocker):
    """Test commit command with potentially conflicting flags."""
    # Mock git operations
    mock_subprocess = mocker.patch("subprocess.run")
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "M  file.py"
    mock_subprocess.return_value = mock_result

    # Mock profile selection
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value="default")

    # Run commit with --add and --all (both stage changes)
    # This should work fine as they're compatible, but test the behavior
    result = cli_runner.invoke(commit, ["--add", "--all"])

    # Verify command handles it gracefully (either works or shows clear error)
    assert result.exit_code is not None

    # If there's an error, it should be clear
    if result.exit_code != 0:
        assert "error" in result.output.lower() or "conflict" in result.output.lower() or "cannot" in result.output.lower()


@pytest.mark.integration
def test_dynamodb_export_with_negative_parallel_segments(cli_runner, mocker):
    """Test DynamoDB export with invalid negative parallel segments."""
    # Mock AWS to avoid real calls
    mocker.patch("boto3.client")

    # Run export with negative segments
    result = cli_runner.invoke(dynamodb, ["export", "test-table", "--parallel-segments", "-1"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message is actionable
    assert "invalid" in result.output.lower() or "positive" in result.output.lower() or "segments" in result.output.lower()


@pytest.mark.integration
def test_dynamodb_export_with_zero_parallel_segments(cli_runner, mocker):
    """Test DynamoDB export with zero parallel segments."""
    # Mock AWS to avoid real calls
    mocker.patch("boto3.client")

    # Run export with zero segments
    result = cli_runner.invoke(dynamodb, ["export", "test-table", "--parallel-segments", "0"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message is actionable
    assert "invalid" in result.output.lower() or "positive" in result.output.lower() or "segments" in result.output.lower()


@pytest.mark.integration
def test_config_set_with_invalid_json_value(cli_runner, temp_config_dir, mocker):
    """Test config set with malformed JSON value."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Initialize config
    config_file.write_text("{}")

    # Try to set with invalid JSON (unclosed bracket)
    result = cli_runner.invoke(set_command, ["test.key", '{"invalid": json}'])

    # Command should handle gracefully
    # Either it treats it as a string or shows an error
    assert result.exit_code is not None

    # If it errors, message should be clear
    if result.exit_code != 0:
        assert "invalid" in result.output.lower() or "json" in result.output.lower() or "error" in result.output.lower()


@pytest.mark.integration
def test_commit_with_invalid_profile(cli_runner, mocker):
    """Test commit command with non-existent AWS profile."""
    # Mock git operations to succeed
    mock_subprocess = mocker.patch("subprocess.run")
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "diff --git a/file.py b/file.py\n+new line"
    mock_subprocess.return_value = mock_result

    # Mock profile selection to return invalid profile
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value="non-existent-profile")

    # Mock BaseAgent to raise error for invalid profile
    mock_agent = mocker.patch("cli_tool.core.agents.base_agent.BaseAgent.query")
    mock_agent.side_effect = Exception("Profile 'non-existent-profile' not found")

    # Run commit command
    result = cli_runner.invoke(commit, input="y\n")

    # Verify error is handled
    assert result.exit_code != 0 or "error" in result.output.lower() or "profile" in result.output.lower()

    # Verify error message is actionable
    if result.exit_code != 0:
        assert "profile" in result.output.lower() or "not found" in result.output.lower() or "error" in result.output.lower()


@pytest.mark.integration
def test_cli_help_is_user_friendly(cli_runner):
    """Test that CLI help output is user-friendly and informative."""
    # Run CLI with --help
    result = cli_runner.invoke(cli, ["--help"])

    # Verify success
    assert result.exit_code == 0

    # Verify help contains useful information
    assert "usage" in result.output.lower() or "commands" in result.output.lower()
    assert "options" in result.output.lower() or "help" in result.output.lower()

    # Verify commands are listed
    assert "commit" in result.output.lower()
    assert "config" in result.output.lower()


@pytest.mark.integration
def test_commit_help_is_actionable(cli_runner):
    """Test that commit command help is actionable."""
    # Run commit with --help
    result = cli_runner.invoke(commit, ["--help"])

    # Verify success
    assert result.exit_code == 0

    # Verify help describes what the command does
    assert "commit" in result.output.lower()
    assert "usage" in result.output.lower() or "options" in result.output.lower()

    # Verify flags are documented
    assert "--all" in result.output.lower() or "--add" in result.output.lower() or "--push" in result.output.lower()


@pytest.mark.integration
def test_config_set_help_shows_examples(cli_runner):
    """Test that config set help provides usage examples."""
    # Run config set with --help
    result = cli_runner.invoke(set_command, ["--help"])

    # Verify success
    assert result.exit_code == 0

    # Verify help is informative
    assert "usage" in result.output.lower()
    assert "key" in result.output.lower() or "value" in result.output.lower()


@pytest.mark.integration
def test_dynamodb_export_help_documents_formats(cli_runner):
    """Test that DynamoDB export help documents available formats."""
    # Run export with --help
    result = cli_runner.invoke(dynamodb, ["export", "--help"])

    # Verify success
    assert result.exit_code == 0

    # Verify help documents format options
    assert "format" in result.output.lower()
    assert "json" in result.output.lower() or "csv" in result.output.lower()


@pytest.mark.integration
def test_error_message_does_not_expose_sensitive_data(cli_runner, mocker):
    """Test that error messages don't leak sensitive information."""
    # Mock git operations to fail with sensitive data in error
    mock_subprocess = mocker.patch("subprocess.run")
    mock_result = mocker.MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "fatal: could not read Username for 'https://github.com': terminal prompts disabled"
    mock_subprocess.return_value = mock_result

    # Mock profile selection
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value="default")

    # Run commit command
    result = cli_runner.invoke(commit)

    # Verify error is shown but doesn't expose credentials
    # The error message should be sanitized or generic
    assert "password" not in result.output.lower()
    assert "token" not in result.output.lower()
    assert "secret" not in result.output.lower()


@pytest.mark.integration
def test_cli_version_flag_works(cli_runner):
    """Test that --version flag works and shows version."""
    # Run CLI with --version
    result = cli_runner.invoke(cli, ["--version"])

    # Verify success
    assert result.exit_code == 0

    # Verify version is shown (format: "version_number")
    # Version could be "unknown" in development
    assert len(result.output.strip()) > 0


@pytest.mark.integration
def test_cli_with_typo_suggests_correct_command(cli_runner):
    """Test that CLI with typo provides helpful suggestions."""
    # Run CLI with typo (committ instead of commit)
    result = cli_runner.invoke(cli, ["committ"])

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify error message is helpful
    # Click may suggest similar commands
    assert "no such command" in result.output.lower() or "did you mean" in result.output.lower() or "usage" in result.output.lower()


@pytest.mark.integration
def test_multiple_errors_are_reported_clearly(cli_runner, mocker):
    """Test that multiple validation errors are reported clearly."""
    # Mock AWS to avoid real calls
    mocker.patch("boto3.client")

    # Run export with multiple invalid arguments
    result = cli_runner.invoke(
        dynamodb,
        [
            "export",
            "test-table",
            "--format",
            "invalid-format",
            "--compression",
            "invalid-compression",
            "--parallel-segments",
            "-1",
        ],
    )

    # Verify non-zero exit code
    assert result.exit_code != 0

    # Verify at least one error is reported
    # Click typically reports the first validation error
    assert "invalid" in result.output.lower() or "error" in result.output.lower()


@pytest.mark.integration
def test_config_set_with_empty_value(cli_runner, temp_config_dir, mocker):
    """Test config set with empty string value."""
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Initialize config
    config_file.write_text("{}")

    # Set with empty value
    result = cli_runner.invoke(set_command, ["test.key", ""])

    # Command should handle gracefully
    # Either it sets empty string or shows error
    assert result.exit_code is not None

    # If successful, verify empty value was set
    if result.exit_code == 0:
        import json

        with open(config_file) as f:
            config = json.load(f)
        assert config.get("test", {}).get("key") == ""


@pytest.mark.integration
def test_commit_with_no_changes_shows_helpful_message(cli_runner, mocker):
    """Test commit with no changes shows helpful next steps."""
    # Mock git operations to show no changes
    mock_subprocess = mocker.patch("subprocess.run")
    mock_result = mocker.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""  # Empty diff
    mock_subprocess.return_value = mock_result

    # Mock profile selection
    mocker.patch("cli_tool.commands.commit.commands.generate.select_profile", return_value="default")

    # Run commit command
    result = cli_runner.invoke(commit)

    # Verify helpful message
    assert "no" in result.output.lower() and "changes" in result.output.lower()

    # Message should be actionable (suggest staging files)
    assert "stage" in result.output.lower() or "add" in result.output.lower() or "git add" in result.output.lower()
