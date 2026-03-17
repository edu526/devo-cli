"""Unit tests for SSM database connect command module."""

from unittest.mock import MagicMock, patch

import click
import pytest

from cli_tool.commands.ssm.commands.database.connect import (
    ForwarderRegistry,
    _connect_databases,
    _find_free_port,
    _is_port_bindable,
    _process_db_for_table,
    _run_attempt,
    _run_connection_loop,
    _show_database_selection,
    _validate_tokens,
    _wait_before_reconnect,
    connect_database,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIND_FREE_PORT = "cli_tool.commands.ssm.commands.database.connect._find_free_port"
_MODULE = "cli_tool.commands.ssm.commands.database.connect"


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
# ForwarderRegistry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestForwarderRegistry:
    def test_add_and_stop_all(self):
        """stop_all calls stop_all on all registered forwarders."""
        registry = ForwarderRegistry()
        pf1, pf2 = MagicMock(), MagicMock()
        registry.add(pf1)
        registry.add(pf2)
        registry.stop_all()
        pf1.stop_all.assert_called_once()
        pf2.stop_all.assert_called_once()

    def test_remove_unregisters_forwarder(self):
        """remove prevents stop_all from calling stop_all on removed forwarder."""
        registry = ForwarderRegistry()
        pf = MagicMock()
        registry.add(pf)
        registry.remove(pf)
        registry.stop_all()
        pf.stop_all.assert_not_called()

    def test_remove_nonexistent_is_noop(self):
        """Removing a forwarder not in registry does not raise."""
        registry = ForwarderRegistry()
        pf = MagicMock()
        registry.remove(pf)  # should not raise


# ---------------------------------------------------------------------------
# _is_port_bindable
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsPortBindable:
    def test_returns_true_when_port_is_free(self):
        with patch(f"{_MODULE}.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_sock.bind.return_value = None
            assert _is_port_bindable("127.0.0.2", 5432) is True

    def test_returns_false_when_port_is_occupied(self):
        with patch(f"{_MODULE}.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_sock.bind.side_effect = OSError("address already in use")
            assert _is_port_bindable("127.0.0.2", 5432) is False


# ---------------------------------------------------------------------------
# _find_free_port
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindFreePort:
    def test_returns_preferred_port_when_free(self):
        with patch(f"{_MODULE}.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_sock.bind.return_value = None
            result = _find_free_port(15432)
        assert result == 15432

    def test_increments_to_next_port_when_occupied(self):
        bind_calls = []

        def bind_side_effect(addr):
            bind_calls.append(addr[1])
            if addr[1] == 15432:
                raise OSError("address already in use")

        with patch(f"{_MODULE}.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.bind.side_effect = bind_side_effect
            mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _find_free_port(15432)
        assert result == 15433
        assert 15432 in bind_calls
        assert 15433 in bind_calls

    def test_skips_multiple_occupied_ports(self):
        def bind_side_effect(addr):
            if addr[1] in (15432, 15433, 15434):
                raise OSError("in use")

        with patch(f"{_MODULE}.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.bind.side_effect = bind_side_effect
            mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _find_free_port(15432)
        assert result == 15435


# ---------------------------------------------------------------------------
# _validate_tokens
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateTokens:
    def test_returns_true_when_all_tokens_valid(self):
        databases = {"db1": _make_db_config(profile="a"), "db2": _make_db_config(profile="b")}
        with patch(f"{_MODULE}.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = False
            result = _validate_tokens(databases)
        assert result is True
        assert mock_session._is_token_expired.call_count == 2

    def test_returns_false_and_prints_error_when_expired(self):
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = True
            with patch(f"{_MODULE}.console") as mock_console:
                result = _validate_tokens(databases)
        assert result is False
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "expired" in output.lower()

    def test_deduplicates_profile_region_pairs(self):
        """Same (profile, region) is checked only once."""
        databases = {
            "db1": _make_db_config(profile="a", region="us-east-1"),
            "db2": _make_db_config(profile="a", region="us-east-1"),
            "db3": _make_db_config(profile="b", region="eu-west-1"),
        }
        with patch(f"{_MODULE}.SSMSession") as mock_session:
            mock_session._is_token_expired.return_value = False
            _validate_tokens(databases)
        assert mock_session._is_token_expired.call_count == 2


# ---------------------------------------------------------------------------
# _wait_before_reconnect
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWaitBeforeReconnect:
    def test_returns_true_and_prints_reconnect_message(self):
        """Returns True and prints reconnecting message after sleep."""
        with patch(f"{_MODULE}.time.sleep"):
            with patch(f"{_MODULE}.console") as mock_console:
                result = _wait_before_reconnect("mydb")
        assert result is True
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Reconnecting" in output

    def test_returns_false_on_keyboard_interrupt(self):
        """Returns False when Ctrl+C is pressed during sleep."""
        with patch(f"{_MODULE}.time.sleep", side_effect=KeyboardInterrupt):
            result = _wait_before_reconnect("mydb")
        assert result is False


# ---------------------------------------------------------------------------
# _run_attempt
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunAttempt:
    def test_returns_exit_code_from_ssm(self):
        db_config = _make_db_config()
        with patch(f"{_MODULE}.SSMSession") as mock_session:
            mock_session.start_port_forwarding_to_remote.return_value = 0
            result = _run_attempt(db_config, 15432, use_hostname_forwarding=False)
        assert result == 0

    def test_starts_port_forwarder_when_hostname_forwarding(self):
        db_config = _make_db_config(local_address="127.0.0.2")
        with patch(f"{_MODULE}.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 0
                _run_attempt(db_config, 15432, use_hostname_forwarding=True)
        mock_pf.start_forward.assert_called_once_with("127.0.0.2", 5432, 15432)
        mock_pf.stop_all.assert_called_once()

    def test_skips_port_forwarder_without_hostname_forwarding(self):
        db_config = _make_db_config()
        with patch(f"{_MODULE}.PortForwarder") as mock_pf_cls:
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 0
                _run_attempt(db_config, 15432, use_hostname_forwarding=False)
        mock_pf_cls.assert_not_called()

    def test_stop_all_called_even_on_exception(self):
        """finally block ensures stop_all is called even when SSM raises."""
        db_config = _make_db_config(local_address="127.0.0.2")
        with patch(f"{_MODULE}.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt
                with pytest.raises(KeyboardInterrupt):
                    _run_attempt(db_config, 15432, use_hostname_forwarding=True)
        mock_pf.stop_all.assert_called_once()

    def test_registers_and_removes_forwarder_in_registry(self):
        db_config = _make_db_config(local_address="127.0.0.2")
        registry = ForwarderRegistry()
        with patch(f"{_MODULE}.PortForwarder") as mock_pf_cls:
            mock_pf = MagicMock()
            mock_pf_cls.return_value = mock_pf
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session.start_port_forwarding_to_remote.return_value = 0
                _run_attempt(db_config, 15432, use_hostname_forwarding=True, registry=registry)
        assert mock_pf not in registry._forwarders


# ---------------------------------------------------------------------------
# _process_db_for_table
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProcessDbForTable:
    def test_host_not_in_managed_returns_none_port(self):
        db_config = _make_db_config(local_address="127.0.0.2")
        row, port, _ = _process_db_for_table("mydb", db_config, False, set(), lambda p: p)
        assert port is None
        assert "Not in /etc/hosts" in row[5]

    def test_no_hostname_forwarding_returns_none_when_no_flag(self):
        """When local_address is 127.0.0.1 and --no-hosts not passed, skips connection."""
        db_config = _make_db_config(local_address="127.0.0.1", local_port=15432)
        row, port, _ = _process_db_for_table("mydb", db_config, False, set(), lambda p: p)
        assert port is None
        assert "No hostname forwarding" in row[5]

    def test_no_hosts_flag_connects_via_localhost(self):
        """--no-hosts skips socat and connects directly via 127.0.0.1."""
        db_config = _make_db_config(local_address="127.0.0.2", local_port=15432)
        managed = {"db.example.com"}
        row, port, use_hf = _process_db_for_table("mydb", db_config, True, managed, lambda p: p)
        assert port == 15432
        assert use_hf is False
        assert "127.0.0.1" in row[1]

    def test_no_hosts_flag_with_default_address_connects_via_localhost(self):
        """--no-hosts also works when local_address is 127.0.0.1 (not configured for forwarding)."""
        db_config = _make_db_config(local_address="127.0.0.1", local_port=15432)
        row, port, use_hf = _process_db_for_table("mydb", db_config, True, set(), lambda p: p)
        assert port == 15432
        assert use_hf is False
        assert "127.0.0.1" in row[1]

    def test_connected_returns_actual_port(self):
        db_config = _make_db_config(local_address="127.0.0.2", local_port=15432)
        managed = {"db.example.com"}
        with patch(f"{_MODULE}._is_port_bindable", return_value=True):
            row, port, use_hf = _process_db_for_table("mydb", db_config, False, managed, lambda p: p)
        assert port == 15432
        assert use_hf is True
        assert "Connected" in row[5]

    def test_port_conflict_shows_warning_status(self):
        db_config = _make_db_config(local_address="127.0.0.2", local_port=15432)
        managed = {"db.example.com"}
        with patch(f"{_MODULE}._is_port_bindable", return_value=True):
            with patch(f"{_MODULE}.console"):
                row, port, _ = _process_db_for_table("mydb", db_config, False, managed, lambda p: 15433)
        assert port == 15433
        assert "15433" in row[5]

    def test_socat_port_occupied_returns_error_row(self):
        """When local_address:port is already bound, returns error row and None port."""
        db_config = _make_db_config(local_address="127.0.0.2", local_port=15432)
        managed = {"db.example.com"}
        with patch(f"{_MODULE}._is_port_bindable", return_value=False):
            with patch(f"{_MODULE}.console"):
                row, port, _ = _process_db_for_table("mydb", db_config, False, managed, lambda p: p)
        assert port is None
        assert "occupied" in row[5].lower() or "Port" in row[5]


# ---------------------------------------------------------------------------
# _run_connection_loop
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunConnectionLoop:
    def test_exit_code_zero_triggers_reconnect(self):
        """Exit code 0 (session ended) should trigger reconnect, not stop."""
        db_config = _make_db_config()
        wait_calls = []
        with patch(f"{_MODULE}._run_attempt", side_effect=[0, KeyboardInterrupt]):
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session._is_token_expired.return_value = False
                with patch(f"{_MODULE}._wait_before_reconnect", side_effect=lambda n: wait_calls.append(n) or True):
                    _run_connection_loop("mydb", db_config, 15432, use_hostname_forwarding=False)
        assert len(wait_calls) == 1  # reconnect was attempted

    def test_keyboard_interrupt_returns_cleanly(self):
        db_config = _make_db_config()
        with patch(f"{_MODULE}._run_attempt", side_effect=KeyboardInterrupt):
            _run_connection_loop("mydb", db_config, 15432, use_hostname_forwarding=False)

    def test_exception_prints_error_and_returns(self):
        db_config = _make_db_config()
        with patch(f"{_MODULE}._run_attempt", side_effect=RuntimeError("refused")):
            with patch(f"{_MODULE}.console") as mock_console:
                _run_connection_loop("mydb", db_config, 15432, use_hostname_forwarding=False)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "refused" in output

    def test_expired_tokens_after_disconnect_stops_reconnect(self):
        db_config = _make_db_config()
        with patch(f"{_MODULE}._run_attempt", return_value=1):
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session._is_token_expired.return_value = True
                with patch(f"{_MODULE}.console") as mock_console:
                    _run_connection_loop("mydb", db_config, 15432, use_hostname_forwarding=False)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "expired" in output.lower()

    def test_reconnects_when_tokens_valid(self):
        db_config = _make_db_config()
        with patch(f"{_MODULE}._run_attempt", side_effect=[1, KeyboardInterrupt]):
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session._is_token_expired.return_value = False
                with patch(f"{_MODULE}._wait_before_reconnect", return_value=True):
                    with patch(f"{_MODULE}.console") as mock_console:
                        _run_connection_loop("mydb", db_config, 15432, use_hostname_forwarding=False)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Reconnected to mydb" in output

    def test_ctrl_c_during_reconnect_delay_cancels(self):
        db_config = _make_db_config()
        with patch(f"{_MODULE}._run_attempt", return_value=1):
            with patch(f"{_MODULE}.SSMSession") as mock_session:
                mock_session._is_token_expired.return_value = False
                with patch(f"{_MODULE}._wait_before_reconnect", return_value=False):
                    _run_connection_loop("mydb", db_config, 15432, use_hostname_forwarding=False)


# ---------------------------------------------------------------------------
# _connect_databases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectDatabases:
    def test_expired_tokens_aborts(self):
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}._validate_tokens", return_value=False):
            with patch(f"{_MODULE}.HostsManager"):
                with patch(f"{_MODULE}.threading.Thread") as mock_thread:
                    _connect_databases(databases, no_hosts=False)
        mock_thread.assert_not_called()

    def test_no_hostname_forwarding_prints_no_connect_message(self):
        databases = {"db1": _make_db_config()}  # local_address=127.0.0.1
        with patch(f"{_MODULE}._validate_tokens", return_value=True):
            with patch(f"{_MODULE}.HostsManager") as mock_hm_cls:
                mock_hm_cls.return_value.get_managed_entries.return_value = []
                with patch(f"{_MODULE}.console") as mock_console:
                    _connect_databases(databases, no_hosts=False)
        calls_str = str(mock_console.print.call_args_list)
        assert "No databases" in calls_str

    def test_host_not_in_etc_hosts_skips_connection(self):
        databases = {"db1": _make_db_config(local_address="127.0.0.2")}
        with patch(f"{_MODULE}._validate_tokens", return_value=True):
            with patch(f"{_MODULE}.HostsManager") as mock_hm_cls:
                mock_hm_cls.return_value.get_managed_entries.return_value = []
                with patch(f"{_MODULE}.console") as mock_console:
                    _connect_databases(databases, no_hosts=False)
        calls_str = str(mock_console.print.call_args_list)
        assert "No databases" in calls_str

    def test_single_db_starts_one_thread(self):
        databases = {"db1": _make_db_config(local_address="127.0.0.2")}
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False

        with patch(f"{_MODULE}._validate_tokens", return_value=True):
            with patch(f"{_MODULE}.HostsManager") as mock_hm_cls:
                mock_hm_cls.return_value.get_managed_entries.return_value = [("127.0.0.2", "db.example.com")]
                with patch(f"{_MODULE}._is_port_bindable", return_value=True):
                    with patch(f"{_MODULE}.threading.Thread", return_value=mock_thread):
                        with patch(_FIND_FREE_PORT, return_value=15432):
                            with patch(f"{_MODULE}.time.sleep"):
                                _connect_databases(databases, no_hosts=False)

        mock_thread.start.assert_called_once()

    def test_keyboard_interrupt_calls_registry_stop_all(self):
        databases = {"db1": _make_db_config(local_address="127.0.0.2")}
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_registry = MagicMock()

        with patch(f"{_MODULE}._validate_tokens", return_value=True):
            with patch(f"{_MODULE}.HostsManager") as mock_hm_cls:
                mock_hm_cls.return_value.get_managed_entries.return_value = [("127.0.0.2", "db.example.com")]
                with patch(f"{_MODULE}._is_port_bindable", return_value=True):
                    with patch(f"{_MODULE}.threading.Thread", return_value=mock_thread):
                        with patch(_FIND_FREE_PORT, return_value=15432):
                            with patch(f"{_MODULE}.ForwarderRegistry", return_value=mock_registry):
                                with patch(f"{_MODULE}.time.sleep", side_effect=[None, KeyboardInterrupt]):
                                    _connect_databases(databases, no_hosts=False)

        mock_registry.stop_all.assert_called_once()

    def test_unique_ports_assigned_to_each_db(self):
        databases = {
            "db1": _make_db_config(local_address="127.0.0.2", local_port=15432),
            "db2": _make_db_config(local_address="127.0.0.3", local_port=15432, host="other.com"),
        }
        thread_args = []

        def capture_thread(**kwargs):
            thread_args.append(kwargs.get("args", ()))
            mock_t = MagicMock()
            mock_t.is_alive.return_value = False
            return mock_t

        with patch(f"{_MODULE}._validate_tokens", return_value=True):
            with patch(f"{_MODULE}.HostsManager") as mock_hm_cls:
                mock_hm_cls.return_value.get_managed_entries.return_value = [
                    ("127.0.0.2", "db.example.com"),
                    ("127.0.0.3", "other.com"),
                ]
                with patch(f"{_MODULE}._is_port_bindable", return_value=True):
                    with patch(f"{_MODULE}.threading.Thread", side_effect=capture_thread):
                        with patch(_FIND_FREE_PORT, side_effect=lambda p: p):
                            with patch(f"{_MODULE}.time.sleep"):
                                _connect_databases(databases, no_hosts=False)

        assert len(thread_args) == 2
        assert thread_args[0][2] != thread_args[1][2]  # actual_local_port differs

    def test_port_conflict_warning_printed(self):
        databases = {
            "db1": _make_db_config(local_address="127.0.0.2", local_port=15432),
            "db2": _make_db_config(local_address="127.0.0.3", local_port=15432, host="other.com"),
        }
        with patch(f"{_MODULE}._validate_tokens", return_value=True):
            with patch(f"{_MODULE}.HostsManager") as mock_hm_cls:
                mock_hm_cls.return_value.get_managed_entries.return_value = [
                    ("127.0.0.2", "db.example.com"),
                    ("127.0.0.3", "other.com"),
                ]
                with patch(f"{_MODULE}._is_port_bindable", return_value=True):
                    with patch(f"{_MODULE}.threading.Thread") as mock_thread_cls:
                        mock_thread_cls.return_value.is_alive.return_value = False
                        with patch(_FIND_FREE_PORT, side_effect=lambda p: p):
                            with patch(f"{_MODULE}.time.sleep"):
                                with patch(f"{_MODULE}.console") as mock_console:
                                    _connect_databases(databases, no_hosts=False)

        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "in use" in output.lower()


# ---------------------------------------------------------------------------
# _show_database_selection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShowDatabaseSelection:
    def test_select_first_database(self):
        databases = {"db1": _make_db_config(), "db2": _make_db_config(host="other.com")}
        with patch(f"{_MODULE}.click.prompt", return_value=1):
            result = _show_database_selection(databases)
        assert result == "db1"

    def test_select_all_databases(self):
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.click.prompt", return_value=2):
            result = _show_database_selection(databases)
        assert result == "ALL"

    def test_invalid_selection_returns_none(self):
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.click.prompt", return_value=99):
            result = _show_database_selection(databases)
        assert result is None

    def test_keyboard_interrupt_returns_none(self):
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.click.prompt", side_effect=KeyboardInterrupt):
            result = _show_database_selection(databases)
        assert result is None

    def test_click_abort_returns_none(self):
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.click.prompt", side_effect=click.Abort):
            result = _show_database_selection(databases)
        assert result is None

    def test_select_second_database(self):
        databases = {"db1": _make_db_config(), "db2": _make_db_config(host="other.com")}
        with patch(f"{_MODULE}.click.prompt", return_value=2):
            result = _show_database_selection(databases)
        assert result == "db2"

    def test_selection_zero_invalid(self):
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.click.prompt", return_value=0):
            result = _show_database_selection(databases)
        assert result is None


# ---------------------------------------------------------------------------
# connect_database click command
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectDatabaseCommand:
    def test_no_databases_configured(self):
        from click.testing import CliRunner

        runner = CliRunner()
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm_cls.return_value.list_databases.return_value = {}
            result = runner.invoke(connect_database, [])
        assert "No databases configured" in result.output

    def test_database_not_found_by_name(self):
        from click.testing import CliRunner

        runner = CliRunner()
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm = mock_cm_cls.return_value
            mock_cm.list_databases.return_value = {"db1": _make_db_config()}
            mock_cm.get_database.return_value = None
            result = runner.invoke(connect_database, ["nonexistent"])
        assert "not found" in result.output

    def test_user_cancels_selection(self):
        from click.testing import CliRunner

        runner = CliRunner()
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm_cls.return_value.list_databases.return_value = {"db1": _make_db_config()}
            with patch(f"{_MODULE}._show_database_selection", return_value=None):
                result = runner.invoke(connect_database, [])
        assert result.exit_code == 0

    def test_select_all_from_menu(self):
        from click.testing import CliRunner

        runner = CliRunner()
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm_cls.return_value.list_databases.return_value = databases
            with patch(f"{_MODULE}._show_database_selection", return_value="ALL"):
                with patch(f"{_MODULE}._connect_databases") as mock_conn:
                    runner.invoke(connect_database, [])
        mock_conn.assert_called_once_with(databases, False)

    def test_connect_all_flag_skips_menu(self):
        from click.testing import CliRunner

        runner = CliRunner()
        databases = {"db1": _make_db_config(), "db2": _make_db_config(host="other.com")}
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm_cls.return_value.list_databases.return_value = databases
            with patch(f"{_MODULE}._connect_databases") as mock_conn:
                with patch(f"{_MODULE}._show_database_selection") as mock_sel:
                    runner.invoke(connect_database, ["--all"])
        mock_conn.assert_called_once_with(databases, False)
        mock_sel.assert_not_called()

    def test_connect_all_flag_with_no_hosts(self):
        from click.testing import CliRunner

        runner = CliRunner()
        databases = {"db1": _make_db_config()}
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm_cls.return_value.list_databases.return_value = databases
            with patch(f"{_MODULE}._connect_databases") as mock_conn:
                runner.invoke(connect_database, ["--all", "--no-hosts"])
        mock_conn.assert_called_once_with(databases, True)

    def test_single_db_by_name_calls_connect_databases_with_one_item(self):
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm = mock_cm_cls.return_value
            mock_cm.list_databases.return_value = {"db1": db_config}
            mock_cm.get_database.return_value = db_config
            with patch(f"{_MODULE}._connect_databases") as mock_conn:
                runner.invoke(connect_database, ["db1"])
        mock_conn.assert_called_once_with({"db1": db_config}, False)

    def test_no_hosts_flag_passed_for_single_db(self):
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm = mock_cm_cls.return_value
            mock_cm.list_databases.return_value = {"db1": db_config}
            mock_cm.get_database.return_value = db_config
            with patch(f"{_MODULE}._connect_databases") as mock_conn:
                runner.invoke(connect_database, ["db1", "--no-hosts"])
        mock_conn.assert_called_once_with({"db1": db_config}, True)

    def test_selection_name_used_for_db_lookup(self):
        from click.testing import CliRunner

        runner = CliRunner()
        db_config = _make_db_config()
        with patch(f"{_MODULE}.SSMConfigManager") as mock_cm_cls:
            mock_cm = mock_cm_cls.return_value
            mock_cm.list_databases.return_value = {"selected-db": db_config}
            mock_cm.get_database.return_value = db_config
            with patch(f"{_MODULE}._show_database_selection", return_value="selected-db"):
                with patch(f"{_MODULE}._connect_databases"):
                    runner.invoke(connect_database, [])
        mock_cm.get_database.assert_called_once_with("selected-db")
