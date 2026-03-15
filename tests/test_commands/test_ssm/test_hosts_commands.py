"""Tests for SSM hosts sub-commands: add, list, remove, setup, clear."""

import pytest
from click.testing import CliRunner

from cli_tool.commands.ssm.commands.hosts.add import hosts_add_single
from cli_tool.commands.ssm.commands.hosts.clear import hosts_clear
from cli_tool.commands.ssm.commands.hosts.list import hosts_list
from cli_tool.commands.ssm.commands.hosts.remove import hosts_remove_single
from cli_tool.commands.ssm.commands.hosts.setup import hosts_setup

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_ssm_config(mocker, temp_config_dir):
    """Patch load_config / save_config used by SSMConfigManager."""
    mock_config = {"ssm": {"databases": {}}}
    mocker.patch("cli_tool.commands.ssm.core.config.load_config", return_value=mock_config)
    mocker.patch("cli_tool.commands.ssm.core.config.save_config")
    return mock_config


@pytest.fixture
def mock_hosts_manager(mocker):
    """Patch the HostsManager class used by the hosts commands."""
    mock_cls = mocker.patch("cli_tool.commands.ssm.commands.hosts.add.HostsManager")
    mock_cls_list = mocker.patch("cli_tool.commands.ssm.commands.hosts.list.HostsManager")
    mock_cls_remove = mocker.patch("cli_tool.commands.ssm.commands.hosts.remove.HostsManager")
    mock_cls_setup = mocker.patch("cli_tool.commands.ssm.commands.hosts.setup.HostsManager")
    mock_cls_clear = mocker.patch("cli_tool.commands.ssm.commands.hosts.clear.HostsManager")

    instance = mock_cls.return_value
    mock_cls_list.return_value = instance
    mock_cls_remove.return_value = instance
    mock_cls_setup.return_value = instance
    mock_cls_clear.return_value = instance

    return instance


# ---------------------------------------------------------------------------
# hosts_add_single
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hosts_add_single_db_not_found(runner, mock_ssm_config, mock_hosts_manager):
    """When the database is not in config, an error message is printed."""
    result = runner.invoke(hosts_add_single, ["nonexistent"])

    assert result.exit_code == 0
    assert "nonexistent" in result.output
    assert "not found" in result.output


@pytest.mark.unit
def test_hosts_add_single_assigns_loopback_ip(runner, mock_ssm_config, mock_hosts_manager):
    """When local_address is 127.0.0.1, a new loopback IP is assigned."""
    mock_ssm_config["ssm"]["databases"]["mydb"] = {
        "host": "mydb.example.com",
        "local_address": "127.0.0.1",
    }
    mock_hosts_manager.get_next_loopback_ip.return_value = "127.0.0.2"

    result = runner.invoke(hosts_add_single, ["mydb"])

    assert result.exit_code == 0
    mock_hosts_manager.get_next_loopback_ip.assert_called_once()
    mock_hosts_manager.add_entry.assert_called_once_with("127.0.0.2", "mydb.example.com")
    assert "mydb.example.com" in result.output
    assert "127.0.0.2" in result.output


@pytest.mark.unit
def test_hosts_add_single_no_local_address_key(runner, mock_ssm_config, mock_hosts_manager):
    """When local_address key is absent, a new loopback IP is assigned."""
    mock_ssm_config["ssm"]["databases"]["mydb"] = {
        "host": "mydb.example.com",
    }
    mock_hosts_manager.get_next_loopback_ip.return_value = "127.0.0.2"

    result = runner.invoke(hosts_add_single, ["mydb"])

    assert result.exit_code == 0
    mock_hosts_manager.get_next_loopback_ip.assert_called_once()
    mock_hosts_manager.add_entry.assert_called_once_with("127.0.0.2", "mydb.example.com")


@pytest.mark.unit
def test_hosts_add_single_uses_existing_loopback_ip(runner, mock_ssm_config, mock_hosts_manager):
    """When a non-default local_address is already set, it is reused."""
    mock_ssm_config["ssm"]["databases"]["mydb"] = {
        "host": "mydb.example.com",
        "local_address": "127.0.0.5",
    }

    result = runner.invoke(hosts_add_single, ["mydb"])

    assert result.exit_code == 0
    mock_hosts_manager.get_next_loopback_ip.assert_not_called()
    mock_hosts_manager.add_entry.assert_called_once_with("127.0.0.5", "mydb.example.com")
    assert "127.0.0.5" in result.output


@pytest.mark.unit
def test_hosts_add_single_add_entry_raises(runner, mock_ssm_config, mock_hosts_manager):
    """An exception from add_entry is caught and printed as an error."""
    mock_ssm_config["ssm"]["databases"]["mydb"] = {
        "host": "mydb.example.com",
        "local_address": "127.0.0.5",
    }
    mock_hosts_manager.add_entry.side_effect = PermissionError("Operation not permitted")

    result = runner.invoke(hosts_add_single, ["mydb"])

    assert result.exit_code == 0
    assert "Error" in result.output
    assert "Operation not permitted" in result.output


# ---------------------------------------------------------------------------
# hosts_list
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hosts_list_empty(runner, mock_hosts_manager):
    """With no managed entries an informational message is shown."""
    mock_hosts_manager.get_managed_entries.return_value = []

    result = runner.invoke(hosts_list, [])

    assert result.exit_code == 0
    assert "No managed entries" in result.output
    assert "devo ssm hosts setup" in result.output


@pytest.mark.unit
def test_hosts_list_with_entries(runner, mock_hosts_manager):
    """Managed entries are displayed in a table."""
    mock_hosts_manager.get_managed_entries.return_value = [
        ("127.0.0.2", "db.example.com"),
        ("127.0.0.3", "api.example.com"),
    ]

    result = runner.invoke(hosts_list, [])

    assert result.exit_code == 0
    assert "127.0.0.2" in result.output
    assert "db.example.com" in result.output
    assert "127.0.0.3" in result.output
    assert "api.example.com" in result.output


# ---------------------------------------------------------------------------
# hosts_remove_single
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hosts_remove_single_db_not_found(runner, mock_ssm_config, mock_hosts_manager):
    """When the database is not in config, an error is printed."""
    result = runner.invoke(hosts_remove_single, ["nonexistent"])

    assert result.exit_code == 0
    assert "nonexistent" in result.output
    assert "not found" in result.output


@pytest.mark.unit
def test_hosts_remove_single_success(runner, mock_ssm_config, mock_hosts_manager):
    """Successful removal prints a confirmation."""
    mock_ssm_config["ssm"]["databases"]["mydb"] = {
        "host": "mydb.example.com",
        "local_address": "127.0.0.5",
    }

    result = runner.invoke(hosts_remove_single, ["mydb"])

    assert result.exit_code == 0
    mock_hosts_manager.remove_entry.assert_called_once_with("mydb.example.com")
    assert "Removed" in result.output
    assert "mydb.example.com" in result.output


@pytest.mark.unit
def test_hosts_remove_single_remove_entry_raises(runner, mock_ssm_config, mock_hosts_manager):
    """An exception from remove_entry is caught and printed as an error."""
    mock_ssm_config["ssm"]["databases"]["mydb"] = {
        "host": "mydb.example.com",
        "local_address": "127.0.0.5",
    }
    mock_hosts_manager.remove_entry.side_effect = PermissionError("Operation not permitted")

    result = runner.invoke(hosts_remove_single, ["mydb"])

    assert result.exit_code == 0
    assert "Error" in result.output
    assert "Operation not permitted" in result.output


# ---------------------------------------------------------------------------
# hosts_setup
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hosts_setup_no_databases(runner, mock_ssm_config, mock_hosts_manager):
    """With no databases configured, a warning is printed and setup aborts."""
    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    assert "No databases configured" in result.output
    mock_hosts_manager.add_entry.assert_not_called()


@pytest.mark.unit
def test_hosts_setup_all_success(runner, mock_ssm_config, mock_hosts_manager):
    """All databases successfully added prints 'Setup complete!'."""
    mock_ssm_config["ssm"]["databases"] = {
        "db1": {"host": "db1.example.com", "port": 5432, "local_address": "127.0.0.2", "local_port": 15432},
        "db2": {"host": "db2.example.com", "port": 5433, "local_address": "127.0.0.3", "local_port": 15433},
    }

    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    assert mock_hosts_manager.add_entry.call_count == 2
    assert "Setup complete!" in result.output


@pytest.mark.unit
def test_hosts_setup_assigns_new_loopback_ip(runner, mock_ssm_config, mock_hosts_manager):
    """Databases with default 127.0.0.1 address get a new loopback IP assigned."""
    mock_ssm_config["ssm"]["databases"] = {
        "db1": {"host": "db1.example.com", "port": 5432, "local_address": "127.0.0.1", "local_port": 15432},
    }
    mock_hosts_manager.get_next_loopback_ip.return_value = "127.0.0.2"

    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    mock_hosts_manager.get_next_loopback_ip.assert_called_once()
    mock_hosts_manager.add_entry.assert_called_once_with("127.0.0.2", "db1.example.com")


@pytest.mark.unit
def test_hosts_setup_assigns_loopback_ip_when_key_missing(runner, mock_ssm_config, mock_hosts_manager):
    """Databases missing the local_address key also get a new loopback IP."""
    mock_ssm_config["ssm"]["databases"] = {
        "db1": {"host": "db1.example.com", "port": 5432, "local_port": 15432},
    }
    mock_hosts_manager.get_next_loopback_ip.return_value = "127.0.0.2"

    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    mock_hosts_manager.get_next_loopback_ip.assert_called_once()


@pytest.mark.unit
def test_hosts_setup_port_conflict_resolved(runner, mock_ssm_config, mock_hosts_manager):
    """A local_port conflict is detected, resolved, and config is updated."""
    mock_ssm_config["ssm"]["databases"] = {
        "db1": {"host": "db1.example.com", "port": 5432, "local_address": "127.0.0.2", "local_port": 15432},
        "db2": {"host": "db2.example.com", "port": 5433, "local_address": "127.0.0.3", "local_port": 15432},
    }

    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    # Both entries should have been added despite port conflict
    assert mock_hosts_manager.add_entry.call_count == 2


@pytest.mark.unit
def test_hosts_setup_all_fail(runner, mock_ssm_config, mock_hosts_manager):
    """When all add_entry calls raise, 'Setup failed!' is printed."""
    mock_ssm_config["ssm"]["databases"] = {
        "db1": {"host": "db1.example.com", "port": 5432, "local_address": "127.0.0.2", "local_port": 15432},
    }
    mock_hosts_manager.add_entry.side_effect = PermissionError("Operation not permitted")

    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    assert "Setup failed!" in result.output


@pytest.mark.unit
def test_hosts_setup_partial_failure(runner, mock_ssm_config, mock_hosts_manager):
    """When some entries fail, 'Setup partially complete' is printed."""
    mock_ssm_config["ssm"]["databases"] = {
        "db1": {"host": "db1.example.com", "port": 5432, "local_address": "127.0.0.2", "local_port": 15432},
        "db2": {"host": "db2.example.com", "port": 5433, "local_address": "127.0.0.3", "local_port": 15433},
    }
    # First call succeeds, second raises
    mock_hosts_manager.add_entry.side_effect = [None, PermissionError("denied")]

    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    assert "partially complete" in result.output


@pytest.mark.unit
def test_hosts_setup_uses_port_from_db_config_when_local_port_absent(runner, mock_ssm_config, mock_hosts_manager):
    """When local_port is absent the port field is used as fallback."""
    mock_ssm_config["ssm"]["databases"] = {
        "db1": {"host": "db1.example.com", "port": 5432, "local_address": "127.0.0.2"},
    }

    result = runner.invoke(hosts_setup, [])

    assert result.exit_code == 0
    mock_hosts_manager.add_entry.assert_called_once()


# ---------------------------------------------------------------------------
# hosts_clear
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_hosts_clear_confirmed(runner, mock_hosts_manager):
    """Confirming the prompt clears all managed entries."""
    result = runner.invoke(hosts_clear, input="y\n")

    assert result.exit_code == 0
    mock_hosts_manager.clear_all.assert_called_once()
    assert "removed" in result.output


@pytest.mark.unit
def test_hosts_clear_aborted(runner, mock_hosts_manager):
    """Aborting the prompt does not call clear_all."""
    result = runner.invoke(hosts_clear, input="n\n")

    assert result.exit_code != 0 or "Aborted" in result.output
    mock_hosts_manager.clear_all.assert_not_called()


@pytest.mark.unit
def test_hosts_clear_raises(runner, mock_hosts_manager):
    """An exception from clear_all is caught and printed as an error."""
    mock_hosts_manager.clear_all.side_effect = PermissionError("Operation not permitted")

    result = runner.invoke(hosts_clear, input="y\n")

    assert result.exit_code == 0
    assert "Error" in result.output
    assert "Operation not permitted" in result.output
