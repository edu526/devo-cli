"""
Pytest configuration and shared fixtures for the Devo CLI test suite.

This module provides reusable fixtures for testing CLI commands, AWS services,
git operations, and file system interactions. All fixtures follow pytest best
practices with appropriate scoping for test isolation.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from click.testing import CliRunner
from moto import mock_aws
from rich.console import Console

# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def fixtures_dir():
    """
    Provide path to fixtures directory for test data access.

    Returns:
      Path: Absolute path to tests/fixtures/ directory

    Example:
      def test_with_fixture(fixtures_dir):
        data_file = fixtures_dir / 'git_diffs' / 'simple_change.json'
        with open(data_file) as f:
          data = json.load(f)
    """
    return Path(__file__).parent / "fixtures"


# ============================================================================
# CLI Testing Fixtures
# ============================================================================


@pytest.fixture
def cli_runner():
    """
    Provide Click CliRunner for command testing.

    Returns:
      CliRunner: Click test runner for invoking CLI commands

    Example:
      def test_command(cli_runner):
        result = cli_runner.invoke(my_command, ['arg1', 'arg2'])
        assert result.exit_code == 0
    """
    return CliRunner()


@pytest.fixture
def rich_console():
    """
    Provide Rich Console with terminal forcing for testing.

    Returns:
      Console: Rich Console configured for testing with ANSI codes preserved

    Example:
      def test_rich_output(rich_console):
        rich_console.print("[green]Success[/green]")
        # Output will contain ANSI escape codes
    """
    return Console(force_terminal=True, force_jupyter=False, width=120)


# ============================================================================
# AWS Service Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_dynamodb_client(monkeypatch):
    """
    Provide mocked DynamoDB client using moto.

    Yields:
      boto3.client: Mocked DynamoDB client with realistic AWS behavior

    Example:
      def test_dynamodb(mock_dynamodb_client):
        # Create table
        mock_dynamodb_client.create_table(...)
        # Use client as normal
    """
    # Set fake AWS credentials to prevent boto3 from trying to load real credentials
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    # Unset AWS_PROFILE to prevent boto3 from trying to read config file
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    with mock_aws():
        yield boto3.client("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))


@pytest.fixture
def mock_bedrock_client(mocker):
    """
    Provide mocked Bedrock client using pytest-mock.

    Note: Moto has limited support for bedrock-runtime, so we use pytest-mock
    to mock the client directly.

    Args:
      mocker: pytest-mock fixture

    Returns:
      MagicMock: Mocked Bedrock client with invoke_model method

    Example:
      def test_ai_feature(mock_bedrock_client):
        mock_bedrock_client.invoke_model.return_value = {
          'body': MagicMock(read=lambda: b'{"response": "test"}')
        }
    """
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = {"body": MagicMock(read=lambda: b'{"response": "mocked"}')}
    mocker.patch("boto3.client", return_value=mock_client)
    return mock_client


# ============================================================================
# File System Fixtures
# ============================================================================


@pytest.fixture
def temp_config_dir(tmp_path):
    """
    Provide temporary config directory for testing.

    Args:
      tmp_path: pytest built-in fixture for temporary directories

    Returns:
      Path: Temporary directory path for config files

    Example:
      def test_config(temp_config_dir):
        config_file = temp_config_dir / 'config.json'
        # Write and read config files safely
    """
    config_dir = tmp_path / ".devo"
    config_dir.mkdir()
    return config_dir


# ============================================================================
# Git Operation Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_git_repo(mocker):
    """
    Provide mocked git repository using pytest-mock.

    This fixture mocks GitPython's Repo object for testing git operations
    without requiring a real git repository.

    Args:
      mocker: pytest-mock fixture

    Returns:
      MagicMock: Mocked git.Repo object

    Example:
      def test_git_operation(mock_git_repo):
        mock_git_repo.git.diff.return_value = "diff content"
        mock_git_repo.is_dirty.return_value = True
    """
    mock_repo = MagicMock()
    mock_repo.git.diff.return_value = "diff --git a/file.py b/file.py\n+new line"
    mock_repo.is_dirty.return_value = True
    mocker.patch("git.Repo", return_value=mock_repo)
    return mock_repo


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """
    Register custom pytest markers.

    This function is called by pytest during initialization to register
    custom markers used for test categorization.

    Args:
      config: pytest configuration object
    """
    config.addinivalue_line("markers", "unit: Unit tests for core business logic")
    config.addinivalue_line("markers", "integration: Integration tests for CLI commands")
    config.addinivalue_line("markers", "platform: Platform-specific tests")
    config.addinivalue_line("markers", "slow: Slow tests (skipped by default)")
