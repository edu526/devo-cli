"""Unit/integration tests for SSM forward and shortcuts commands.

Covers:
- cli_tool/commands/ssm/commands/forward.py lines 27-39, 44
- cli_tool/commands/ssm/commands/shortcuts.py lines 8-11, 23-25, 32-34
"""

import threading
import time

import click
import pytest
from click.testing import CliRunner

from cli_tool.commands.ssm.commands.forward import forward_command, register_forward_command
from cli_tool.commands.ssm.commands.shortcuts import _find_subcommand, register_shortcuts

# ---------------------------------------------------------------------------
# Helpers: build a minimal test group with the forward command registered
# ---------------------------------------------------------------------------


def _make_forward_group():
    """Return a fresh Click group with the forward command registered."""

    @click.group()
    def grp():
        pass

    register_forward_command(grp)
    return grp


# ---------------------------------------------------------------------------
# forward.py – forward_command() factory (line 44)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestForwardCommandFactory:
    def test_forward_command_returns_register_function(self):
        """forward_command() returns the register_forward_command callable (line 44)."""
        result = forward_command()
        assert result is register_forward_command


# ---------------------------------------------------------------------------
# forward.py – forward_manual command
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestForwardManualCommand:
    def test_expired_tokens_aborts_before_connecting(self, mocker):
        """Pre-check: expired tokens abort before any connection attempt."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session._is_token_expired.return_value = True
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(grp, ["forward", "--bastion", "i-123", "--host", "db.example.com"])

        assert result.exit_code == 0
        assert "expired" in result.output.lower()
        mock_session.start_port_forwarding_to_remote.assert_not_called()

    def test_forward_without_local_port_uses_remote_port(self, mocker):
        """local_port defaults to port when not supplied."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session._is_token_expired.return_value = False
        mock_session.start_port_forwarding_to_remote.return_value = 0
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(
            grp,
            ["forward", "--bastion", "i-123", "--host", "db.example.com", "--port", "5432"],
        )

        assert result.exit_code == 0
        mock_session.start_port_forwarding_to_remote.assert_called_once()
        call_kwargs = mock_session.start_port_forwarding_to_remote.call_args[1]
        assert call_kwargs["local_port"] == 5432

    def test_forward_with_profile_prints_profile(self, mocker):
        """Profile is printed when --profile is supplied."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session._is_token_expired.return_value = False
        mock_session.start_port_forwarding_to_remote.return_value = 0
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(
            grp,
            ["forward", "--bastion", "i-123", "--host", "db.example.com", "--profile", "my-profile"],
        )

        assert result.exit_code == 0
        assert "my-profile" in result.output

    def test_forward_keyboard_interrupt_closes_gracefully(self, mocker):
        """KeyboardInterrupt is caught and a close message is printed."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session._is_token_expired.return_value = False
        mock_session.start_port_forwarding_to_remote.side_effect = KeyboardInterrupt
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(
            grp,
            ["forward", "--bastion", "i-123", "--host", "db.example.com"],
        )

        assert result.exit_code == 0
        assert "closed" in result.output.lower() or "connection" in result.output.lower()

    def test_forward_with_local_port_uses_supplied_value(self, mocker):
        """When --local-port is given it is passed through unchanged."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session._is_token_expired.return_value = False
        mock_session.start_port_forwarding_to_remote.return_value = 0
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(
            grp,
            ["forward", "--bastion", "i-123", "--host", "db.example.com", "--port", "5432", "--local-port", "15432"],
        )

        assert result.exit_code == 0
        call_kwargs = mock_session.start_port_forwarding_to_remote.call_args[1]
        assert call_kwargs["local_port"] == 15432

    def test_forward_expired_tokens_shows_error(self, mocker):
        """When connection drops and tokens are expired, an error is shown."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session.start_port_forwarding_to_remote.return_value = 1
        # pre-check passes, post-drop check detects expiry
        mock_session._is_token_expired.side_effect = [False, True]
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(
            grp,
            ["forward", "--bastion", "i-123", "--host", "db.example.com"],
        )

        assert result.exit_code == 0
        assert "expired" in result.output.lower()
        assert "aws-login" in result.output.lower()
        mock_session.start_port_forwarding_to_remote.assert_called_once()

    def test_forward_reconnects_when_tokens_valid(self, mocker):
        """When connection drops and tokens are valid, reconnect is attempted."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session.start_port_forwarding_to_remote.side_effect = [1, 0]
        mock_session._is_token_expired.return_value = False
        mocker.patch("cli_tool.commands.ssm.commands.forward.time.sleep")
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(
            grp,
            ["forward", "--bastion", "i-123", "--host", "db.example.com"],
        )

        assert result.exit_code == 0
        assert "Reconnecting" in result.output
        assert mock_session.start_port_forwarding_to_remote.call_count == 2

    def test_forward_ctrl_c_during_reconnect_delay_cancels(self, mocker):
        """Ctrl+C during reconnect countdown cancels the reconnect."""
        mock_session = mocker.patch("cli_tool.commands.ssm.commands.forward.SSMSession")
        mock_session.start_port_forwarding_to_remote.return_value = 1
        mock_session._is_token_expired.return_value = False
        mocker.patch("cli_tool.commands.ssm.commands.forward.time.sleep", side_effect=KeyboardInterrupt)
        grp = _make_forward_group()
        runner = CliRunner()

        result = runner.invoke(
            grp,
            ["forward", "--bastion", "i-123", "--host", "db.example.com"],
        )

        assert result.exit_code == 0
        assert "Connection closed" in result.output
        mock_session.start_port_forwarding_to_remote.assert_called_once()


# ---------------------------------------------------------------------------
# shortcuts.py – _find_subcommand (lines 8-11)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindSubcommand:
    def _make_nested_group(self):
        """Build a group that contains a sub-group with a command."""

        @click.group()
        def root():
            pass

        @click.group("database")
        def db_group():
            pass

        @db_group.command("connect")
        def connect():
            pass

        root.add_command(db_group)
        return root, connect

    def test_find_subcommand_existing_group_and_command(self):
        """Returns the command when both group and command exist (lines 8-10)."""
        root, connect_cmd = self._make_nested_group()
        result = _find_subcommand(root, "database", "connect")
        assert result is connect_cmd

    def test_find_subcommand_missing_group_returns_none(self):
        """Returns None when the named group does not exist (line 11)."""

        @click.group()
        def root():
            pass

        result = _find_subcommand(root, "nonexistent", "connect")
        assert result is None

    def test_find_subcommand_group_exists_command_missing(self):
        """Returns None when the group exists but the command does not."""
        root, _ = self._make_nested_group()
        result = _find_subcommand(root, "database", "nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# shortcuts.py – connect_shortcut (lines 23-25)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectShortcut:
    def test_connect_shortcut_invokes_connect_cmd(self, mocker):
        """Covers lines 23-25: connect shortcut delegates to database connect."""
        # Build a group that has a real 'database connect' sub-command so
        # _find_subcommand succeeds, but mock out the actual work.
        from cli_tool.commands.ssm import ssm

        # Patch the underlying database connect command's callback so it does
        # nothing, while still being a real Click command that ctx.invoke can call.
        db_connect = ssm.commands["database"].commands["connect"]
        mocker.patch.object(db_connect, "callback", return_value=None)

        runner = CliRunner()
        # "connect" is the shortcut registered by register_shortcuts(ssm)
        result = runner.invoke(ssm, ["connect"])

        # The shortcut itself should succeed (exit 0).
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# shortcuts.py – shell_shortcut (lines 32-34)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShellShortcut:
    def test_shell_shortcut_invokes_shell_cmd(self, mocker):
        """Covers lines 32-34: shell shortcut delegates to instance shell."""
        from cli_tool.commands.ssm import ssm

        instance_shell = ssm.commands["instance"].commands["shell"]
        mocker.patch.object(instance_shell, "callback", return_value=None)

        runner = CliRunner()
        result = runner.invoke(ssm, ["shell", "my-instance"])

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# connection_runner.py – _probe_then_emit_connected state guard
# (regression: probe thread must not flip state to 'connected' after the
#  main loop has declared 'expired_credentials' / 'error' / 'stopped')
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProbeStateGuard:
    def test_probe_does_not_overwrite_expired_credentials_state(self, mocker):
        """After the main loop emits 'expired_credentials', the background
        probe thread's timeout fallback must NOT emit 'connected' on top of
        it. Covers connection_runner.py:330-345."""
        from cli_tool.commands.ssm.core.connection_runner import (
            ConnectionRecord,
            ForwarderRegistry,
            _run_connection_loop,
        )
        from cli_tool.commands.ssm.core.session import SSMSession
        from cli_tool.commands.ssm.core.states import (
            CONNECTED,
            EXPIRED_CREDENTIALS,
            STOPPED,
        )

        record = ConnectionRecord(name="x")
        registry = ForwarderRegistry()
        main_finished = threading.Event()

        # SSM subprocess dies fast and returns cleanly (no exception raised)
        mocker.patch("cli_tool.commands.ssm.core.connection_runner._run_attempt")
        # Post-mortem token check sees expired creds
        mocker.patch.object(SSMSession, "_is_token_expired", staticmethod=lambda **kw: True)
        # Local port is never ready (refused)
        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.socket.create_connection",
            side_effect=OSError("refused"),
        )

        # Block the probe on the main thread finishing, so when the probe
        # reaches the timeout branch the state-guard sees the final state.
        def fake_sleep(seconds):
            if seconds == 0.5:
                main_finished.wait(timeout=2.0)

        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.time.sleep",
            side_effect=fake_sleep,
        )

        # Return a monotonically increasing counter so the probe's deadline
        # is eventually exceeded regardless of which thread calls first
        # (the metrics thread also calls time.monotonic once for uptime).
        counter = {"n": 0}

        def fake_monotonic():
            counter["n"] += 1
            return float(counter["n"])

        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.time.monotonic",
            side_effect=fake_monotonic,
        )

        def run_and_signal():
            _run_connection_loop(
                name="x",
                db_config={"region": "us-east-1", "profile": "p"},
                actual_local_port=1,
                use_hostname_forwarding=False,
                registry=registry,
                record=record,
            )
            main_finished.set()

        t = threading.Thread(target=run_and_signal, daemon=True)
        t.start()
        t.join(timeout=2.0)
        # Give the probe a moment to finish its state-guard check.
        time.sleep(0.2)

        assert record.state == EXPIRED_CREDENTIALS

    def test_probe_does_not_emit_connected_after_stop_event(self, mocker):
        """After record.stop_event is set, the probe must not emit 'connected'
        even if the port is reachable and the main thread hasn't yet emitted
        'stopped'. Covers connection_runner.py:337-340."""
        from cli_tool.commands.ssm.core.connection_runner import (
            ConnectionRecord,
            ForwarderRegistry,
            _run_connection_loop,
        )
        from cli_tool.commands.ssm.core.session import SSMSession
        from cli_tool.commands.ssm.core.states import (
            CONNECTED,
            EXPIRED_CREDENTIALS,
            STOPPED,
        )

        record = ConnectionRecord(name="x")
        registry = ForwarderRegistry()
        state_changes: list = []
        registry.add_observer(lambda e, p: state_changes.append(p.get("state")) if e == "connection.state_changed" else None)
        probe_in_body = threading.Event()
        stop_clicked = threading.Event()
        probe_done = threading.Event()
        main_finished = threading.Event()

        class _FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                probe_done.set()
                return False

        # SSM attempt blocks until both the probe is in the with-block AND
        # stop has been clicked, then waits for the probe to finish its
        # state-guard check before returning. This guarantees the probe
        # evaluates the state-guard before the main thread emits 'stopped'.
        def fake_run_attempt(*args, **kwargs):
            probe_in_body.wait(timeout=2.0)
            stop_clicked.wait(timeout=2.0)
            probe_done.wait(timeout=2.0)
            return 0

        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner._run_attempt",
            side_effect=fake_run_attempt,
        )
        mocker.patch.object(SSMSession, "_is_token_expired", staticmethod(lambda **kw: False))

        # Port is reachable, but the mock blocks until stop is clicked so
        # the probe is sitting inside the with-block when the event is set.
        def fake_create_connection(*args, **kwargs):
            probe_in_body.set()
            stop_clicked.wait(timeout=2.0)
            return _FakeSocket()

        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.socket.create_connection",
            side_effect=fake_create_connection,
        )
        mocker.patch("cli_tool.commands.ssm.core.connection_runner.time.sleep")
        counter = {"n": 0}

        def fake_monotonic():
            counter["n"] += 1
            return float(counter["n"])

        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.time.monotonic",
            side_effect=fake_monotonic,
        )

        def run_and_signal():
            _run_connection_loop(
                name="x",
                db_config={"region": "us-east-1", "profile": "p"},
                actual_local_port=1,
                use_hostname_forwarding=False,
                registry=registry,
                record=record,
            )
            main_finished.set()

        t = threading.Thread(target=run_and_signal, daemon=True)
        t.start()

        probe_in_body.wait(timeout=2.0)
        record.stop_event.set()
        stop_clicked.set()
        main_finished.wait(timeout=2.0)
        time.sleep(0.1)

        assert CONNECTED not in state_changes, f"probe emitted 'connected' after stop_event was set: {state_changes}"
        assert record.state == STOPPED

    def test_probe_does_not_overwrite_error_state(self, mocker):
        """After the main loop emits 'error' (from a generic exception in
        _run_attempt), the background probe thread's timeout fallback must
        NOT emit 'connected' on top of it. Covers connection_runner.py:340-355.
        """
        from cli_tool.commands.ssm.core.connection_runner import (
            ConnectionRecord,
            ForwarderRegistry,
            _run_connection_loop,
        )
        from cli_tool.commands.ssm.core.session import SSMSession
        from cli_tool.commands.ssm.core.states import (
            CONNECTED,
            ERROR,
            STOPPED,
        )

        record = ConnectionRecord(name="x")
        registry = ForwarderRegistry()
        main_finished = threading.Event()

        # SSM subprocess raises a generic error (not an expired-credential case)
        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner._run_attempt",
            side_effect=RuntimeError("ssm crashed"),
        )
        # Local port is never ready (refused) — forces probe into timeout branch
        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.socket.create_connection",
            side_effect=OSError("refused"),
        )

        # Block the probe on the main thread finishing, so when the probe
        # reaches the timeout branch the state-guard sees the final state.
        def fake_sleep(seconds):
            if seconds == 0.5:
                main_finished.wait(timeout=2.0)

        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.time.sleep",
            side_effect=fake_sleep,
        )

        # Return a monotonically increasing counter so the probe's deadline
        # is eventually exceeded regardless of which thread calls first
        # (the metrics thread also calls time.monotonic once for uptime).
        counter = {"n": 0}

        def fake_monotonic():
            counter["n"] += 1
            return float(counter["n"])

        mocker.patch(
            "cli_tool.commands.ssm.core.connection_runner.time.monotonic",
            side_effect=fake_monotonic,
        )

        def run_and_signal():
            _run_connection_loop(
                name="x",
                db_config={"region": "us-east-1", "profile": "p"},
                actual_local_port=1,
                use_hostname_forwarding=False,
                registry=registry,
                record=record,
            )
            main_finished.set()

        t = threading.Thread(target=run_and_signal, daemon=True)
        t.start()
        t.join(timeout=2.0)
        # Give the probe a moment to finish its state-guard check.
        time.sleep(0.2)

        assert record.state == ERROR
        assert record.error is not None and "ssm crashed" in record.error
