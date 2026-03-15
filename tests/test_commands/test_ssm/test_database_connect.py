"""Unit tests for SSM database connect command module."""

import threading
from unittest.mock import MagicMock, call, patch

import click
import pytest

from cli_tool.commands.ssm.commands.database.connect import (
    _check_hostname_in_hosts,
    _connect_all_databases,
    _connect_with_hostname_forwarding,
    _connect_without_hostname_forwarding,
    _process_database_connection,
    _resolve_hostname_forwarding,
    _show_database_selection,
    connect_database,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_config(**overrides):
    """Return a minimal database config dict."""
    defaults = {
        "host": "db.example.com",
        "port": 5432,
        "local_port": 15432,
        "bastion": "i-12345678",
        "region": "us-east-1",
        "profile": "dev",
        "local_address": "127.0.0.1",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# _check_hostname_in_hosts
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCheckHostnameInHosts:
    def test_host_found_in_managed_entries(self):
        db_config = _make_db_config(host="db.example.com")
        with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
            mock_hm = MagicMock()
            mock_hm.get_managed_entries.return_value = [("127.0.0.1", "db.example.com")]
            mock_hm_cls.return_value = mock_hm
            result = _check_hostname_in_hosts(db_config)
        assert result is True

    def test_host_not_found_in_managed_entries(self):
        db_config = _make_db_config(host="other.example.com")
        with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
            mock_hm = MagicMock()
            mock_hm.get_managed_entries.return_value = [("127.0.0.1", "db.example.com")]
            mock_hm_cls.return_value = mock_hm
            result = _check_hostname_in_hosts(db_config)
        assert result is False

    def test_empty_managed_entries(self):
        db_config = _make_db_config(host="db.example.com")
        with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
            mock_hm = MagicMock()
            mock_hm.get_managed_entries.return_value = []
            mock_hm_cls.return_value = mock_hm
            result = _check_hostname_in_hosts(db_config)
        assert result is False


# ---------------------------------------------------------------------------
# _resolve_hostname_forwarding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResolveHostnameForwarding:
    def test_localhost_returns_false(self):
        db_config = _make_db_config(local_address="127.0.0.1")
        result = _resolve_hostname_forwarding(db_config, no_hosts=False)
        assert result is False

    def test_no_hosts_flag_returns_false(self):
        db_config = _make_db_config(local_address="10.0.0.1")
        result = _resolve_hostname_forwarding(db_config, no_hosts=True)
        assert result is False

    def test_host_in_hosts_file_returns_true(self):
        db_config = _make_db_config(local_address="10.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect._check_hostname_in_hosts", return_value=True):
            result = _resolve_hostname_forwarding(db_config, no_hosts=False)
        assert result is True

    def test_host_not_in_hosts_user_confirms_localhost(self):
        db_config = _make_db_config(local_address="10.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect._check_hostname_in_hosts", return_value=False):
            with patch("cli_tool.commands.ssm.commands.database.connect.click.confirm", return_value=True):
                result = _resolve_hostname_forwarding(db_config, no_hosts=False)
        assert result is False

    def test_host_not_in_hosts_user_cancels(self):
        db_config = _make_db_config(local_address="10.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect._check_hostname_in_hosts", return_value=False):
            with patch("cli_tool.commands.ssm.commands.database.connect.click.confirm", return_value=False):
                result = _resolve_hostname_forwarding(db_config, no_hosts=False)
        assert result is None


# ---------------------------------------------------------------------------
# _show_database_selection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShowDatabaseSelection:
    def test_select_first_database(self):
        databases = {"db1": _make_db_config(), "db2": _make_db_config(host="other.com")}
        with patch("cli_tool.commands.ssm.commands.database.connect.click.prompt", return_value=1):
            result = _show_database_selection(databases)
        assert result == "db1"

    def test_select_all_databases(self):
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.click.prompt", return_value=2):
            result = _show_database_selection(databases)
        assert result == "ALL"

    def test_invalid_selection_returns_none(self):
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.click.prompt", return_value=99):
            result = _show_database_selection(databases)
        assert result is None

    def test_keyboard_interrupt_returns_none(self):
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.click.prompt", side_effect=KeyboardInterrupt):
            result = _show_database_selection(databases)
        assert result is None

    def test_click_abort_returns_none(self):
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.click.prompt", side_effect=click.Abort):
            result = _show_database_selection(databases)
        assert result is None

    def test_select_second_database(self):
        databases = {"db1": _make_db_config(), "db2": _make_db_config(host="other.com")}
        with patch("cli_tool.commands.ssm.commands.database.connect.click.prompt", return_value=2):
            result = _show_database_selection(databases)
        assert result == "db2"

    def test_selection_zero_invalid(self):
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.click.prompt", return_value=0):
            result = _show_database_selection(databases)
        assert result is None


# ---------------------------------------------------------------------------
# _process_database_connection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProcessDatabaseConnection:
    def _make_table(self):
        from rich.table import Table

        t = Table()
        t.add_column("Database")
        t.add_column("Connect To")
        t.add_column("Local Port")
        t.add_column("Remote")
        t.add_column("Profile")
        t.add_column("Status")
        return t

    def test_hostname_forwarding_host_not_in_managed(self):
        table = self._make_table()
        threads = []
        db_config = _make_db_config(local_address="10.0.0.1")
        managed_hosts = set()  # host NOT in managed
        mock_port_forwarder = MagicMock()

        _process_database_connection("mydb", db_config, False, managed_hosts, mock_port_forwarder, table, threads, lambda p: p, lambda n, c, lp: None)
        # Should add warning row, not start thread
        assert len(threads) == 0

    def test_no_hostname_forwarding_localhost(self):
        table = self._make_table()
        threads = []
        db_config = _make_db_config(local_address="127.0.0.1")
        managed_hosts = set()
        mock_port_forwarder = MagicMock()

        _process_database_connection("mydb", db_config, False, managed_hosts, mock_port_forwarder, table, threads, lambda p: p, lambda n, c, lp: None)
        # local_address is 127.0.0.1, so no hostname forwarding
        assert len(threads) == 0

    def test_no_hosts_flag_disables_hostname_forwarding(self):
        table = self._make_table()
        threads = []
        db_config = _make_db_config(local_address="10.0.0.1")
        managed_hosts = {"db.example.com"}
        mock_port_forwarder = MagicMock()

        _process_database_connection("mydb", db_config, True, managed_hosts, mock_port_forwarder, table, threads, lambda p: p, lambda n, c, lp: None)
        # no_hosts=True → no hostname forwarding
        assert len(threads) == 0

    def test_successful_connection_starts_thread(self):
        table = self._make_table()
        threads = []
        db_config = _make_db_config(local_address="10.0.0.1")
        managed_hosts = {"db.example.com"}
        mock_port_forwarder = MagicMock()

        with patch("time.sleep"):
            _process_database_connection(
                "mydb", db_config, False, managed_hosts, mock_port_forwarder, table, threads, lambda p: p, lambda n, c, lp: None
            )
        assert len(threads) == 1
        assert threads[0][0] == "mydb"

    def test_port_forwarder_exception_handled(self):
        table = self._make_table()
        threads = []
        db_config = _make_db_config(local_address="10.0.0.1")
        managed_hosts = {"db.example.com"}
        mock_port_forwarder = MagicMock()
        mock_port_forwarder.start_forward.side_effect = Exception("port in use")

        with patch("time.sleep"):
            _process_database_connection(
                "mydb", db_config, False, managed_hosts, mock_port_forwarder, table, threads, lambda p: p, lambda n, c, lp: None
            )
        assert len(threads) == 0

    def test_port_conflict_uses_next_available_port(self):
        """get_unique_local_port should return a different port when preferred is taken."""
        table = self._make_table()
        threads = []
        db_config = _make_db_config(local_address="10.0.0.1", port=5432, local_port=5432)
        managed_hosts = {"db.example.com"}
        mock_port_forwarder = MagicMock()
        used_ports = {5432}

        def get_unique_port(preferred):
            if preferred not in used_ports:
                used_ports.add(preferred)
                return preferred
            alt = 15433
            used_ports.add(alt)
            return alt

        with patch("time.sleep"):
            _process_database_connection(
                "mydb", db_config, False, managed_hosts, mock_port_forwarder, table, threads, get_unique_port, lambda n, c, lp: None
            )
        assert len(threads) == 1


# ---------------------------------------------------------------------------
# _connect_with_hostname_forwarding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectWithHostnameForwarding:
    def test_successful_connection(self):
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 0
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()

    def test_nonzero_exit_code_prints_error(self):
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 1
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()

    def test_keyboard_interrupt_handled(self):
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()

    def test_exception_returns_after_stop(self):
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.side_effect = Exception("connection refused")
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()

    def test_no_profile_in_config(self):
        db_config = _make_db_config()
        del db_config["profile"]
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 0
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()


# ---------------------------------------------------------------------------
# _connect_without_hostname_forwarding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectWithoutHostnameForwarding:
    def test_successful_connection_localhost(self):
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.return_value = 0
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        mock_session.start_port_forwarding_to_remote.assert_called_once()

    def test_nonzero_exit_code_prints_error(self):
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.return_value = 1
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        mock_session.start_port_forwarding_to_remote.assert_called_once()

    def test_keyboard_interrupt_handled(self):
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        mock_session.start_port_forwarding_to_remote.assert_called_once()

    def test_no_hosts_flag_with_non_localhost(self):
        db_config = _make_db_config(local_address="10.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.return_value = 0
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=True)
        mock_session.start_port_forwarding_to_remote.assert_called_once()


# ---------------------------------------------------------------------------
# connect_database click command
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectDatabaseCommand:
    def test_no_databases_configured(self):
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {}
            mock_cm_cls.return_value = mock_cm
            result = runner.invoke(connect_database, [])
        assert "No databases configured" in result.output

    def test_database_not_found_by_name(self):
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {"db1": _make_db_config()}
            mock_cm.get_database.return_value = None
            mock_cm_cls.return_value = mock_cm
            result = runner.invoke(connect_database, ["nonexistent"])
        assert "not found" in result.output

    def test_user_cancels_selection(self):
        from click.testing import CliRunner

        runner = CliRunner()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {"db1": _make_db_config()}
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._show_database_selection", return_value=None):
                result = runner.invoke(connect_database, [])
        assert result.exit_code == 0

    def test_select_all_databases(self):
        from click.testing import CliRunner

        runner = CliRunner()
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = databases
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._show_database_selection", return_value="ALL"):
                with patch("cli_tool.commands.ssm.commands.database.connect._connect_all_databases") as mock_all:
                    runner.invoke(connect_database, [])
        mock_all.assert_called_once_with(databases, False)

    def test_connect_with_hostname_forwarding(self):
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {"db1": db_config}
            mock_cm.get_database.return_value = db_config
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._resolve_hostname_forwarding", return_value=True):
                with patch("cli_tool.commands.ssm.commands.database.connect._connect_with_hostname_forwarding") as mock_conn:
                    runner.invoke(connect_database, ["db1"])
        mock_conn.assert_called_once_with("db1", db_config)

    def test_connect_without_hostname_forwarding(self):
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {"db1": db_config}
            mock_cm.get_database.return_value = db_config
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._resolve_hostname_forwarding", return_value=False):
                with patch("cli_tool.commands.ssm.commands.database.connect._connect_without_hostname_forwarding") as mock_conn:
                    runner.invoke(connect_database, ["db1"])
        mock_conn.assert_called_once_with("db1", db_config, False)

    def test_resolve_returns_none_aborts(self):
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {"db1": db_config}
            mock_cm.get_database.return_value = db_config
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._resolve_hostname_forwarding", return_value=None):
                with patch("cli_tool.commands.ssm.commands.database.connect._connect_with_hostname_forwarding") as mock_conn:
                    runner.invoke(connect_database, ["db1"])
        mock_conn.assert_not_called()

    def test_no_hosts_flag_passed(self):
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {"db1": db_config}
            mock_cm.get_database.return_value = db_config
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._resolve_hostname_forwarding", return_value=False) as mock_resolve:
                with patch("cli_tool.commands.ssm.commands.database.connect._connect_without_hostname_forwarding"):
                    runner.invoke(connect_database, ["db1", "--no-hosts"])
        mock_resolve.assert_called_once_with(db_config, True)


# ---------------------------------------------------------------------------
# _connect_all_databases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectAllDatabases:
    def test_no_databases_to_connect(self):
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
            mock_hm = MagicMock()
            mock_hm.get_managed_entries.return_value = []
            mock_hm_cls.return_value = mock_hm
            with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder"):
                with patch("cli_tool.commands.ssm.commands.database.connect._process_database_connection"):
                    # All threads list remains empty → should print "No databases to connect"
                    with patch("cli_tool.commands.ssm.commands.database.connect.console") as mock_console:
                        _connect_all_databases(databases, no_hosts=False)
                    # Verify that the "No databases to connect" message was printed
                    calls_str = str(mock_console.print.call_args_list)
                    assert "No databases" in calls_str or "No databases to connect" in calls_str

    def test_threads_run_until_keyboard_interrupt(self):
        databases = {"db1": _make_db_config(local_address="10.0.0.1")}

        mock_thread = MagicMock()
        mock_thread.is_alive.side_effect = [True, KeyboardInterrupt]

        with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
            mock_hm = MagicMock()
            mock_hm.get_managed_entries.return_value = [("10.0.0.1", "db.example.com")]
            mock_hm_cls.return_value = mock_hm
            with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
                mock_pf = MagicMock()
                mock_pf_cls.return_value = mock_pf
                with patch("cli_tool.commands.ssm.commands.database.connect.threading.Thread", return_value=mock_thread):
                    with patch("time.sleep", side_effect=KeyboardInterrupt):
                        with patch("cli_tool.commands.ssm.commands.database.connect._process_database_connection") as mock_proc:

                            def add_thread(name, db_config, no_hosts, managed_hosts, pf, table, threads, get_port, start_conn):
                                threads.append(("db1", mock_thread))

                            mock_proc.side_effect = add_thread
                            _connect_all_databases(databases, no_hosts=False)
                mock_pf.stop_all.assert_called_once()
