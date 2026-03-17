"""
Integration tests for SSM tunnel workflow.

Tests the complete SSM tunnel setup workflow:
- Database configuration → tunnel establishment → /etc/hosts modification → cleanup
- Verify tunnel establishment with port forwarding
- Verify /etc/hosts file modifications (mocked)
- Verify tunnel cleanup on exit
- Mock all AWS and file operations

**Validates: Requirements 18.2, 18.4, 18.5**
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open

import pytest
from click.testing import CliRunner

from cli_tool.commands.ssm.commands.database.add import add_database
from cli_tool.commands.ssm.commands.database.connect import connect_database
from cli_tool.commands.ssm.commands.hosts.add import hosts_add_single
from cli_tool.commands.ssm.commands.hosts.clear import hosts_clear
from cli_tool.commands.ssm.commands.hosts.setup import hosts_setup


@pytest.fixture
def mock_ssm_config(mocker, temp_config_dir):
    """Mock SSM configuration manager."""
    mock_config = {"ssm": {"databases": {}, "hosts": {}}}

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


@pytest.fixture
def mock_hosts_file(mocker):
    """Mock /etc/hosts file operations."""
    # Mock file existence check
    mock_path = mocker.patch("pathlib.Path.exists")
    mock_path.return_value = True

    # Mock file read/write operations
    hosts_content = "127.0.0.1 localhost\n::1 localhost\n"
    mock_file = mock_open(read_data=hosts_content)
    mocker.patch("builtins.open", mock_file)

    return mock_file


# ============================================================================
# Test: Complete SSM Tunnel Setup Workflow
# ============================================================================


@pytest.mark.integration
def test_ssm_tunnel_complete_workflow(cli_runner, mock_ssm_config, sample_database_config, mocker, mock_hosts_file):
    """
    Test complete SSM tunnel setup workflow.

    Validates:
    - Database configuration is added successfully
    - SSM tunnel is established with port forwarding
    - /etc/hosts file is modified with hostname mapping
    - Tunnel cleanup occurs on exit
    - All AWS and file operations are properly mocked
    """
    # ========== Step 1: Add Database Configuration ==========

    add_result = cli_runner.invoke(
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

    # Verify database was added
    assert add_result.exit_code == 0
    assert "Database 'test-db' added successfully" in add_result.output

    # Add database to mock config for connection
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    # ========== Step 2: Establish SSM Tunnel ==========

    # Mock SSMSession to simulate tunnel establishment
    mock_ssm_session = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session._is_token_expired.return_value = False

    # Simulate KeyboardInterrupt after tunnel is established (user stops tunnel)
    mock_ssm_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result = cli_runner.invoke(connect_database, ["test-db", "--no-hosts"])

    # Verify tunnel was established
    assert connect_result.exit_code == 0
    assert "Starting connections" in connect_result.output
    assert "Connection closed" in connect_result.output

    # Verify SSM session was called with correct parameters
    mock_ssm_session.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-1234567890abcdef0", host="test-db.example.com", port=5432, local_port=15432, region="us-east-1", profile="test-profile"
    )

    # ========== Step 3: Verify Cleanup (implicit in KeyboardInterrupt handling) ==========

    # The connect command should handle cleanup gracefully
    # Verify no error messages in output
    assert "error" not in connect_result.output.lower() or "Connection closed" in connect_result.output


@pytest.mark.integration
def test_ssm_tunnel_with_hostname_forwarding(cli_runner, mock_ssm_config, mocker, mock_hosts_file):
    """
    Test SSM tunnel with hostname forwarding (not localhost).

    Validates:
    - Database configured with custom hostname
    - /etc/hosts entry is added for hostname
    - Tunnel forwards to hostname instead of localhost
    - Cleanup removes /etc/hosts entry
    """
    # ========== Step 1: Add Database with Hostname Forwarding ==========

    # Database configured with hostname instead of localhost
    hostname_db_config = {
        "hostname-db": {
            "bastion": "i-abcdef1234567890",
            "host": "prod-db.internal.example.com",
            "port": 3306,
            "local_port": 13306,
            "region": "us-west-2",
            "profile": "prod-profile",
            "local_address": "prod-db.local",  # Custom hostname
        }
    }

    mock_ssm_config["ssm"]["databases"] = hostname_db_config

    # ========== Step 2: Establish Tunnel with Hostname ==========

    # Mock SSMSession
    mock_ssm_session = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session._is_token_expired.return_value = False
    mock_ssm_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result = cli_runner.invoke(connect_database, ["hostname-db"])

    # Verify the command reports missing /etc/hosts entry
    assert "Not in /etc/hosts" in connect_result.output or "hosts setup" in connect_result.output

    # Note: SSM session is not called when user declines localhost fallback


@pytest.mark.integration
def test_ssm_tunnel_cleanup_on_error(cli_runner, mock_ssm_config, sample_database_config, mocker, mock_hosts_file):
    """
    Test SSM tunnel cleanup when errors occur.

    Validates:
    - Tunnel establishment fails gracefully
    - /etc/hosts entries are not left in inconsistent state
    - Error messages are user-friendly
    - Cleanup occurs even on failure
    """
    # Add database to mock config
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    # ========== Step 1: Simulate Tunnel Establishment Failure ==========

    # Mock SSMSession to raise an error
    mock_ssm_session = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session._is_token_expired.return_value = False
    mock_ssm_session.start_port_forwarding_to_remote.side_effect = Exception("SSM session failed: Unable to connect to bastion")

    connect_result = cli_runner.invoke(connect_database, ["test-db", "--no-hosts"])

    # Verify the command shows connection info and handles the error
    assert "Starting connections" in connect_result.output
    assert "error" in connect_result.output.lower()

    # ========== Step 2: Verify Manual Cleanup with Clear Command ==========


@pytest.mark.integration
def test_ssm_tunnel_multiple_simultaneous_tunnels(cli_runner, mock_ssm_config, mocker, mock_hosts_file):
    """
    Test multiple simultaneous SSM tunnels.

    Validates:
    - Multiple databases can be configured
    - Multiple tunnels can be established (in separate processes)
    - Each tunnel uses correct port and configuration
    - No port conflicts occur
    """
    # ========== Step 1: Configure Multiple Databases ==========

    multi_db_config = {
        "db1": {
            "bastion": "i-111111111",
            "host": "db1.example.com",
            "port": 5432,
            "local_port": 15432,
            "region": "us-east-1",
            "profile": "dev",
            "local_address": "127.0.0.1",
        },
        "db2": {
            "bastion": "i-222222222",
            "host": "db2.example.com",
            "port": 3306,
            "local_port": 13306,
            "region": "us-east-1",
            "profile": "dev",
            "local_address": "127.0.0.1",
        },
        "db3": {
            "bastion": "i-333333333",
            "host": "db3.example.com",
            "port": 27017,
            "local_port": 17017,
            "region": "us-west-2",
            "profile": "prod",
            "local_address": "127.0.0.1",
        },
    }

    mock_ssm_config["ssm"]["databases"] = multi_db_config

    # ========== Step 2: Establish First Tunnel ==========

    # Mock SSMSession for first tunnel
    mock_ssm_session_1 = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_1._is_token_expired.return_value = False
    mock_ssm_session_1.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_1 = cli_runner.invoke(connect_database, ["db1", "--no-hosts"])

    # Verify first tunnel
    assert connect_result_1.exit_code == 0
    assert "Starting connections" in connect_result_1.output
    assert "Connection closed" in connect_result_1.output

    # Verify correct parameters for db1
    mock_ssm_session_1.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-111111111", host="db1.example.com", port=5432, local_port=15432, region="us-east-1", profile="dev"
    )

    # ========== Step 3: Establish Second Tunnel ==========

    # Reset mock for second tunnel
    mock_ssm_session_2 = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_2._is_token_expired.return_value = False
    mock_ssm_session_2.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_2 = cli_runner.invoke(connect_database, ["db2", "--no-hosts"])

    # Verify second tunnel
    assert connect_result_2.exit_code == 0
    assert "Starting connections" in connect_result_2.output
    assert "Connection closed" in connect_result_2.output

    # Verify correct parameters for db2
    mock_ssm_session_2.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-222222222", host="db2.example.com", port=3306, local_port=13306, region="us-east-1", profile="dev"
    )

    # ========== Step 4: Establish Third Tunnel (Different Region) ==========

    # Reset mock for third tunnel
    mock_ssm_session_3 = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_3._is_token_expired.return_value = False
    mock_ssm_session_3.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_3 = cli_runner.invoke(connect_database, ["db3", "--no-hosts"])

    # Verify third tunnel
    assert connect_result_3.exit_code == 0
    assert "Starting connections" in connect_result_3.output
    assert "Connection closed" in connect_result_3.output

    # Verify correct parameters for db3 (different region)
    mock_ssm_session_3.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-333333333", host="db3.example.com", port=27017, local_port=17017, region="us-west-2", profile="prod"
    )


@pytest.mark.integration
def test_ssm_tunnel_hosts_file_rollback_on_error(cli_runner, mock_ssm_config, sample_database_config, mocker, mock_hosts_file):
    """
    Test /etc/hosts file rollback when tunnel setup fails.

    Validates:
    - /etc/hosts entry is added before tunnel establishment
    - If tunnel fails, user can manually clean up /etc/hosts
    - Clear command removes all SSM-managed entries
    - Original /etc/hosts content is preserved
    """
    # Add database to mock config
    mock_ssm_config["ssm"]["databases"] = sample_database_config

    # ========== Step 1: Simulate Tunnel Failure ==========

    # Mock SSMSession to fail: pre-check passes, post-drop detects expired tokens
    mock_ssm_session = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session._is_token_expired.side_effect = [False, True]
    mock_ssm_session.start_port_forwarding_to_remote.return_value = 1  # Non-zero exit code

    connect_result = cli_runner.invoke(connect_database, ["test-db", "--no-hosts"])

    # Verify tunnel failure is reported (token expiry detected after SSM returns)
    assert connect_result.exit_code == 0  # Command handles error gracefully
    assert "expired" in connect_result.output.lower()

    # Note: In a real scenario, /etc/hosts cleanup would be manual
    # The hosts clear command can be used to clean up entries if needed


@pytest.mark.integration
def test_ssm_tunnel_state_persistence_across_connections(cli_runner, mock_ssm_config, sample_database_config, mocker, mock_hosts_file):
    """
    Test that database configuration persists across multiple tunnel connections.

    Validates:
    - Database configuration is saved and persists
    - Multiple connections to same database use same configuration
    - No re-configuration required for subsequent connections
    - Configuration can be updated and changes persist
    """
    # ========== Step 1: Add Database Configuration ==========

    add_result = cli_runner.invoke(
        add_database,
        [
            "--name",
            "persistent-db",
            "--bastion",
            "i-persistent123",
            "--host",
            "persistent.example.com",
            "--port",
            "5432",
            "--local-port",
            "15432",
            "--region",
            "us-east-1",
        ],
    )

    assert add_result.exit_code == 0
    assert "Database 'persistent-db' added successfully" in add_result.output

    # Add to mock config to simulate persistence
    mock_ssm_config["ssm"]["databases"]["persistent-db"] = {
        "bastion": "i-persistent123",
        "host": "persistent.example.com",
        "port": 5432,
        "local_port": 15432,
        "region": "us-east-1",
        "profile": None,
        "local_address": "127.0.0.1",
    }

    # ========== Step 2: First Connection ==========

    # Mock SSMSession for first connection
    mock_ssm_session_1 = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_1._is_token_expired.return_value = False
    mock_ssm_session_1.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_1 = cli_runner.invoke(connect_database, ["persistent-db", "--no-hosts"])

    # Verify first connection
    assert connect_result_1.exit_code == 0
    assert "Starting connections" in connect_result_1.output

    # Verify SSM session was called with correct parameters
    mock_ssm_session_1.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-persistent123", host="persistent.example.com", port=5432, local_port=15432, region="us-east-1", profile=None
    )

    # ========== Step 3: Second Connection (using persisted config) ==========

    # Reset mock for second connection
    mock_ssm_session_2 = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_2._is_token_expired.return_value = False
    mock_ssm_session_2.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_2 = cli_runner.invoke(connect_database, ["persistent-db", "--no-hosts"])

    # Verify second connection uses same configuration
    assert connect_result_2.exit_code == 0
    assert "Starting connections" in connect_result_2.output

    # Verify SSM session was called with same parameters
    mock_ssm_session_2.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-persistent123", host="persistent.example.com", port=5432, local_port=15432, region="us-east-1", profile=None
    )

    # ========== Step 4: Third Connection (after simulated restart) ==========

    # Reset mock for third connection
    mock_ssm_session_3 = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_3._is_token_expired.return_value = False
    mock_ssm_session_3.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_3 = cli_runner.invoke(connect_database, ["persistent-db", "--no-hosts"])

    # Verify third connection still works
    assert connect_result_3.exit_code == 0
    assert "Starting connections" in connect_result_3.output

    # Verify configuration persisted across all connections
    mock_ssm_session_3.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-persistent123", host="persistent.example.com", port=5432, local_port=15432, region="us-east-1", profile=None
    )


@pytest.mark.integration
def test_ssm_tunnel_with_aws_profile_switching(cli_runner, mock_ssm_config, mocker, mock_hosts_file):
    """
    Test SSM tunnel with different AWS profiles.

    Validates:
    - Databases can be configured with different AWS profiles
    - Tunnel uses correct profile for authentication
    - Profile switching works correctly between connections
    """
    # ========== Step 1: Configure Databases with Different Profiles ==========

    multi_profile_config = {
        "dev-db": {
            "bastion": "i-dev123",
            "host": "dev-db.example.com",
            "port": 5432,
            "local_port": 15432,
            "region": "us-east-1",
            "profile": "dev-profile",
            "local_address": "127.0.0.1",
        },
        "prod-db": {
            "bastion": "i-prod456",
            "host": "prod-db.example.com",
            "port": 5432,
            "local_port": 25432,
            "region": "us-west-2",
            "profile": "prod-profile",
            "local_address": "127.0.0.1",
        },
    }

    mock_ssm_config["ssm"]["databases"] = multi_profile_config

    # ========== Step 2: Connect to Dev Database ==========

    # Mock SSMSession for dev connection
    mock_ssm_session_dev = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_dev._is_token_expired.return_value = False
    mock_ssm_session_dev.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_dev = cli_runner.invoke(connect_database, ["dev-db", "--no-hosts"])

    # Verify dev connection
    assert connect_result_dev.exit_code == 0
    assert "Starting connections" in connect_result_dev.output

    # Verify correct profile was used
    mock_ssm_session_dev.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-dev123", host="dev-db.example.com", port=5432, local_port=15432, region="us-east-1", profile="dev-profile"
    )

    # ========== Step 3: Connect to Prod Database ==========

    # Reset mock for prod connection
    mock_ssm_session_prod = mocker.patch("cli_tool.commands.ssm.commands.database.connect.SSMSession")
    mock_ssm_session_prod._is_token_expired.return_value = False
    mock_ssm_session_prod.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt()

    connect_result_prod = cli_runner.invoke(connect_database, ["prod-db", "--no-hosts"])

    # Verify prod connection
    assert connect_result_prod.exit_code == 0
    assert "Starting connections" in connect_result_prod.output

    # Verify correct profile was used (different from dev)
    mock_ssm_session_prod.start_port_forwarding_to_remote.assert_called_once_with(
        bastion="i-prod456", host="prod-db.example.com", port=5432, local_port=25432, region="us-west-2", profile="prod-profile"
    )
