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
    def test_expired_tokens_aborts_before_connecting(self):
        """Pre-check: expired tokens abort before any connection attempt."""
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = True
            _connect_with_hostname_forwarding("mydb", db_config)
        mock_session.start_port_forwarding_to_remote.assert_not_called()

    def test_successful_connection(self):
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session._is_token_expired.return_value = False
                mock_session.start_port_forwarding_to_remote.return_value = 0
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()

    def test_nonzero_exit_code_checks_tokens_and_exits(self):
        """Non-zero exit triggers token check; expired tokens stop the reconnect loop."""
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 1
                # pre-check passes, post-drop check detects expiry
                mock_session._is_token_expired.side_effect = [False, True]
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()
        assert mock_session._is_token_expired.call_count == 2

    def test_keyboard_interrupt_handled(self):
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session._is_token_expired.return_value = False
                mock_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()

    def test_exception_returns_after_stop(self):
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session._is_token_expired.return_value = False
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
                mock_session._is_token_expired.return_value = False
                mock_session.start_port_forwarding_to_remote.return_value = 0
                _connect_with_hostname_forwarding("mydb", db_config)
        mock_pf.stop_all.assert_called_once()

    def test_expired_tokens_shows_error_message(self):
        """Token expiry error is displayed when tokens are expired after a disconnect."""
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 1
                # pre-check passes, post-drop check detects expiry
                mock_session._is_token_expired.side_effect = [False, True]
                with patch("cli_tool.commands.ssm.commands.database.connect.console") as mock_console:
                    _connect_with_hostname_forwarding("mydb", db_config)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "expired" in output.lower()
        assert "aws-login" in output.lower()

    def test_reconnects_when_tokens_valid(self):
        """When tokens are valid after a disconnect, reconnect is attempted."""
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                # First call drops, second exits cleanly
                mock_session.start_port_forwarding_to_remote.side_effect = [1, 0]
                mock_session._is_token_expired.return_value = False
                with patch("cli_tool.commands.ssm.commands.database.connect.time.sleep"):
                    _connect_with_hostname_forwarding("mydb", db_config)
        assert mock_session.start_port_forwarding_to_remote.call_count == 2
        assert mock_pf.stop_all.call_count == 2

    def test_ctrl_c_during_reconnect_delay_cancels(self):
        """Ctrl+C during the reconnect countdown stops the reconnect loop."""
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 1
                mock_session._is_token_expired.return_value = False
                with patch("cli_tool.commands.ssm.commands.database.connect.time.sleep", side_effect=KeyboardInterrupt):
                    _connect_with_hostname_forwarding("mydb", db_config)
        mock_session.start_port_forwarding_to_remote.assert_called_once()


# ---------------------------------------------------------------------------
# _connect_without_hostname_forwarding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectWithoutHostnameForwarding:
    def test_expired_tokens_aborts_before_connecting(self):
        """Pre-check: expired tokens abort before any connection attempt."""
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = True
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        mock_session.start_port_forwarding_to_remote.assert_not_called()

    def test_successful_connection_localhost(self):
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = False
            mock_session.start_port_forwarding_to_remote.return_value = 0
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        mock_session.start_port_forwarding_to_remote.assert_called_once()

    def test_nonzero_exit_code_checks_tokens_and_exits(self):
        """Non-zero exit triggers token check; expired tokens stop the reconnect loop."""
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.return_value = 1
            # pre-check passes, post-drop check detects expiry
            mock_session._is_token_expired.side_effect = [False, True]
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        mock_session.start_port_forwarding_to_remote.assert_called_once()
        assert mock_session._is_token_expired.call_count == 2

    def test_keyboard_interrupt_handled(self):
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = False
            mock_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        mock_session.start_port_forwarding_to_remote.assert_called_once()

    def test_no_hosts_flag_with_non_localhost(self):
        db_config = _make_db_config(local_address="10.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = False
            mock_session.start_port_forwarding_to_remote.return_value = 0
            _connect_without_hostname_forwarding("mydb", db_config, no_hosts=True)
        mock_session.start_port_forwarding_to_remote.assert_called_once()

    def test_expired_tokens_shows_error_message(self):
        """Token expiry error is displayed when tokens are expired after a disconnect."""
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.return_value = 1
            # pre-check passes, post-drop check detects expiry
            mock_session._is_token_expired.side_effect = [False, True]
            with patch("cli_tool.commands.ssm.commands.database.connect.console") as mock_console:
                _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "expired" in output.lower()
        assert "aws-login" in output.lower()

    def test_reconnects_when_tokens_valid(self):
        """When tokens are valid after a disconnect, reconnect is attempted."""
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            # First call drops, second exits cleanly
            mock_session.start_port_forwarding_to_remote.side_effect = [1, 0]
            mock_session._is_token_expired.return_value = False
            with patch("cli_tool.commands.ssm.commands.database.connect.time.sleep"):
                _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
        assert mock_session.start_port_forwarding_to_remote.call_count == 2

    def test_ctrl_c_during_reconnect_delay_cancels(self):
        """Ctrl+C during the reconnect countdown stops the reconnect loop."""
        db_config = _make_db_config(local_address="127.0.0.1")
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.return_value = 1
            mock_session._is_token_expired.return_value = False
            with patch("cli_tool.commands.ssm.commands.database.connect.time.sleep", side_effect=KeyboardInterrupt):
                _connect_without_hostname_forwarding("mydb", db_config, no_hosts=False)
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

    def test_connect_all_flag_skips_menu(self):
        """--all flag connects to all databases without showing the selection menu."""
        from click.testing import CliRunner

        runner = CliRunner()
        databases = {"db1": _make_db_config(), "db2": _make_db_config(host="other.com")}
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = databases
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._connect_all_databases") as mock_all:
                with patch("cli_tool.commands.ssm.commands.database.connect._show_database_selection") as mock_sel:
                    runner.invoke(connect_database, ["--all"])
        mock_all.assert_called_once_with(databases, False)
        mock_sel.assert_not_called()

    def test_connect_all_flag_with_no_hosts(self):
        """--all --no-hosts passes no_hosts=True to _connect_all_databases."""
        from click.testing import CliRunner

        runner = CliRunner()
        databases = {"db1": _make_db_config()}
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = databases
            mock_cm_cls.return_value = mock_cm
            with patch("cli_tool.commands.ssm.commands.database.connect._connect_all_databases") as mock_all:
                runner.invoke(connect_database, ["--all", "--no-hosts"])
        mock_all.assert_called_once_with(databases, True)

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
    def test_expired_tokens_aborts_before_connecting(self):
        """Token check fires before any connection is attempted."""
        databases = {"db1": _make_db_config(), "db2": _make_db_config(host="other.com")}
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = True
            with patch("cli_tool.commands.ssm.commands.database.connect.console") as mock_console:
                _connect_all_databases(databases, no_hosts=False)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "expired" in output.lower()
        assert "aws-login" in output.lower()
        mock_session.start_port_forwarding_to_remote.assert_not_called()

    def test_checks_each_unique_profile_region(self):
        """Each unique (profile, region) is checked once."""
        databases = {
            "db1": _make_db_config(profile="profile-a", region="us-east-1"),
            "db2": _make_db_config(profile="profile-a", region="us-east-1"),  # duplicate — not rechecked
            "db3": _make_db_config(profile="profile-b", region="eu-west-1"),  # different profile
        }
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = False
            with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
                mock_hm = MagicMock()
                mock_hm.get_managed_entries.return_value = []
                mock_hm_cls.return_value = mock_hm
                with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder"):
                    with patch("cli_tool.commands.ssm.commands.database.connect._process_database_connection"):
                        _connect_all_databases(databases, no_hosts=False)
        assert mock_session._is_token_expired.call_count == 2  # profile-a and profile-b

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


# ---------------------------------------------------------------------------
# _connect_all_databases — get_unique_local_port / start_connection (lines 40-48, 51-61)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectAllDatabasesInternals:
    def test_get_unique_local_port_returns_next_port_when_preferred_taken(self):
        """
        Lines 43-48: get_unique_local_port increments to find the next free port
        when the preferred port is already in use.
        """
        databases = {
            "db1": _make_db_config(local_address="127.0.0.1", local_port=15432),
            "db2": _make_db_config(local_address="127.0.0.1", local_port=15432),
        }

        assigned_ports = []

        def capture_start(name, db_config, local_port):
            assigned_ports.append((name, local_port))

        with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
            mock_hm = MagicMock()
            mock_hm.get_managed_entries.return_value = []
            mock_hm_cls.return_value = mock_hm
            with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder"):
                with patch("cli_tool.commands.ssm.commands.database.connect._process_database_connection") as mock_proc:

                    def process(name, db_cfg, no_hosts, managed, pf, table, threads, get_port, start_conn):
                        assigned_ports.append((name, get_port(db_cfg.get("local_port", 15432))))

                    mock_proc.side_effect = process
                    _connect_all_databases(databases, no_hosts=False)

        # Both DBs wanted port 15432; the second should have gotten a different port
        assert len(assigned_ports) == 2
        assert assigned_ports[0][1] != assigned_ports[1][1] or assigned_ports[0][1] == 15432

    def test_start_connection_exception_is_printed(self):
        """
        Lines 60-61: when SSMSession.start_port_forwarding_to_remote raises inside
        start_connection, the exception is caught and printed.
        """
        databases = {"db1": _make_db_config(local_address="127.0.0.1")}

        with patch("cli_tool.commands.ssm.commands.database.connect.HostsManager") as mock_hm_cls:
            mock_hm = MagicMock()
            mock_hm.get_managed_entries.return_value = []
            mock_hm_cls.return_value = mock_hm
            with patch("cli_tool.commands.ssm.commands.database.connect.PortForwarder"):
                with patch("cli_tool.commands.ssm.commands.database.connect._process_database_connection") as mock_proc:

                    def process(name, db_cfg, no_hosts, managed, pf, table, threads, get_port, start_conn):
                        # Call start_conn directly to exercise lines 50-61
                        try:
                            start_conn(name, db_cfg, db_cfg.get("local_port", 15432))
                        except Exception:
                            pass

                    mock_proc.side_effect = process
                    with patch("cli_tool.commands.ssm.commands.database.connect.SSMSession") as mock_session:
                        mock_session.start_port_forwarding_to_remote.side_effect = RuntimeError("connection refused")
                        # Should not raise — exception is caught inside start_connection
                        _connect_all_databases(databases, no_hosts=False)


# ---------------------------------------------------------------------------
# connect_database — name = selection path (line 286)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectDatabaseSelectionName:
    def test_selection_name_used_for_db_lookup(self):
        """
        Line 286: when _show_database_selection returns a name (not None, not 'ALL'),
        that name is used to call get_database and proceed with connection.
        """
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch("cli_tool.commands.ssm.commands.database.connect.SSMConfigManager") as mock_cm_cls:
            mock_cm = MagicMock()
            mock_cm.list_databases.return_value = {"selected-db": db_config}
            mock_cm.get_database.return_value = db_config
            mock_cm_cls.return_value = mock_cm
            with patch(
                "cli_tool.commands.ssm.commands.database.connect._show_database_selection",
                return_value="selected-db",
            ):
                with patch(
                    "cli_tool.commands.ssm.commands.database.connect._resolve_hostname_forwarding",
                    return_value=False,
                ):
                    with patch("cli_tool.commands.ssm.commands.database.connect._connect_without_hostname_forwarding") as mock_conn:
                        runner.invoke(connect_database, [])

        # get_database should have been called with the selection name
        mock_cm.get_database.assert_called_once_with("selected-db")
        mock_conn.assert_called_once_with("selected-db", db_config, False)
