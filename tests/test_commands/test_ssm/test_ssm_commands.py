"""
Integration tests for SSM commands.

Tests the complete SSM workflow including:
- Database configuration management (add, list, remove)
- SSM session start with instance ID
- SSM port forwarding setup
- Database connection tunnels
- /etc/hosts file modifications (mocked)
"""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from cli_tool.commands.ssm.commands.database.add import add_database
from cli_tool.commands.ssm.commands.database.connect import connect_database
from cli_tool.commands.ssm.commands.database.list import list_databases
from cli_tool.commands.ssm.commands.database.remove import remove_database


@pytest.fixture
def mock_ssm_config(mocker, temp_config_dir):
    """Mock SSM configuration manager."""
    mock_config = {"ssm": {"databases": {}}}

    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value=mock_config)
    mocker.patch("cli_tool.commands.ssm.core.config.save_config")

    return mock_config


@pytest.fixture
def sample_database_config():
    """Sample database configuration for testing."""
    return {
        "test-db": {
            "bastion": "i-1234567890abcdef0",
            "host": "test-db.example.com",
            "port": 5432,
            "local_port": 15432,
            "region": "us-east-1",
            "profile": "test-profile",
            "local_address": "127.0.0.1",
        }
    }


@pytest.mark.integration
def test_add_database_success(cli_runner, mock_ssm_config):
    """Test adding a database configuration."""
    result = cli_runner.invoke(
        add_database,
        [
            "--name",
            "test-db",
            "--bastion",
            "i-1234567890abcdef0",
            "--host",
            "test-db.example.com",
            "--port",
            "5432",
            "--local-port",
            "15432",
            "--region",
            "us-east-1",
            "--profile",
            "test-profile",
        ],
    )

    assert result.exit_code == 0
    assert "Database 'test-db' added successfully" in result.output
    assert "devo ssm connect test-db" in result.output


@pytest.mark.integration
def test_add_database_without_local_port(cli_runner, mock_ssm_config):
    """Test adding a database without specifying local port (uses remote port)."""
    result = cli_runner.invoke(
        add_database,
        ["--name", "test-db", "--bastion", "i-1234567890abcdef0", "--host", "test-db.example.com", "--port", "5432", "--region", "us-east-1"],
    )

    assert result.exit_code == 0
    assert "Database 'test-db' added successfully" in result.output


@pytest.mark.integration
def test_add_database_missing_required_options(cli_runner, mock_ssm_config):
    """Test adding a database with missing required options."""
    result = cli_runner.invoke(
        add_database,
        [
            "--name",
            "test-db",
            "--bastion",
            "i-1234567890abcdef0",
            # Missing --host and --port
        ],
    )

    assert result.exit_code != 0
    assert "Missing option" in result.output or "required" in result.output.lower()


@pytest.mark.integration
def test_list_databases_empty(cli_runner, mock_ssm_config):
    """Test listing databases when none are configured."""
    result = cli_runner.invoke(list_databases, [])

    assert result.exit_code == 0
    assert "No databases configured" in result.output
    assert "devo ssm database add" in result.output


@pytest.mark.integration
def test_list_databases_with_entries(cli_runner, mock_ssm_config, sample_database_config):
    """Test listing databases with configured entries."""
    # Add database to mock config
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    result = cli_runner.invoke(list_databases, [])

    assert result.exit_code == 0
    assert "Configured Databases" in result.output
    assert "test-db" in result.output
    assert "test-db.example.com" in result.output
    assert "5432" in result.output
    assert "test-profile" in result.output


@pytest.mark.integration
def test_remove_database_success(cli_runner, mock_ssm_config, sample_database_config):
    """Test removing an existing database configuration."""
    # Add database to mock config
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    result = cli_runner.invoke(remove_database, ["test-db"])

    assert result.exit_code == 0
    assert "Database 'test-db' removed" in result.output


@pytest.mark.integration
def test_remove_database_not_found(cli_runner, mock_ssm_config):
    """Test removing a non-existent database configuration."""
    result = cli_runner.invoke(remove_database, ["nonexistent-db"])

    assert result.exit_code == 0
    assert "Database 'nonexistent-db' not found" in result.output


@pytest.mark.integration
def test_connect_database_not_configured(cli_runner, mock_ssm_config):
    """Test connecting to a database when none are configured."""
    result = cli_runner.invoke(connect_database, ["test-db"])

    assert result.exit_code == 0
    assert "No databases configured" in result.output
    assert "devo ssm database add" in result.output


@pytest.mark.integration
def test_connect_database_not_found(cli_runner, mock_ssm_config, sample_database_config):
    """Test connecting to a non-existent database."""
    # Add a different database
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    result = cli_runner.invoke(connect_database, ["nonexistent-db"])

    assert result.exit_code == 0
    assert "Database 'nonexistent-db' not found" in result.output
    assert "Available databases:" in result.output
    assert "test-db" in result.output


@pytest.mark.integration
def test_connect_database_without_hostname_forwarding(cli_runner, mock_ssm_config, sample_database_config, mocker):
    """Test connecting to a database without hostname forwarding (localhost)."""
    # Database configured with localhost
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    # Mock SSMSession to raise KeyboardInterrupt (simulate user stopping)
    mock_ssm_session = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    result = cli_runner.invoke(connect_database, ["test-db"])

    assert result.exit_code == 0
    assert "Connecting to test-db" in result.output
    assert "localhost:15432" in result.output
    assert "Connection closed" in result.output

    # Verify SSM session was started
    mock_ssm_session.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-1234567890abcdef0", host="test-db.example.com", port=5432, local_port=15432, region="us-east-1", profile="test-profile"
    )


@pytest.mark.integration
def test_connect_database_ssm_session_failure(cli_runner, mock_ssm_config, sample_database_config, mocker):
    """Test handling SSM session failures."""
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    # Mock SSMSession to return non-zero exit code
    mock_ssm_session = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session.start_port_forwarding_to_remote.return_value = 1

    result = cli_runner.invoke(connect_database, ["test-db"])

    assert result.exit_code == 0
    assert "Connection failed" in result.output or "SSM session failed" in result.output
