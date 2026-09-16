"""Unit tests for cli_tool.sidecar.bootstrap module."""

import socket
from unittest.mock import MagicMock

import pytest

from cli_tool.sidecar.bootstrap import _bind_socket, run

# ---------------------------------------------------------------------------
# _bind_socket
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBindSocket:
    def test_returns_a_listening_socket(self):
        sock = _bind_socket("127.0.0.1", 0)
        try:
            port = sock.getsockname()[1]
            assert isinstance(port, int)
            assert port > 0

            # Already listening: a client can connect right away, with no
            # server loop running yet.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.settimeout(1)
                client.connect(("127.0.0.1", port))
        finally:
            sock.close()

    def test_binds_the_given_port(self):
        probe = _bind_socket("127.0.0.1", 0)
        free_port = probe.getsockname()[1]
        probe.close()

        sock = _bind_socket("127.0.0.1", free_port)
        try:
            assert sock.getsockname()[1] == free_port
        finally:
            sock.close()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRun:
    def _run_with_mocks(self, mocker):
        mock_server_instance = MagicMock()
        mock_server_class = mocker.patch("cli_tool.sidecar.bootstrap.uvicorn.Server", return_value=mock_server_instance)
        mock_config_class = mocker.patch("cli_tool.sidecar.bootstrap.uvicorn.Config")
        mock_create_app = mocker.patch("cli_tool.sidecar.bootstrap.create_app", return_value=MagicMock())
        return mock_server_class, mock_config_class, mock_server_instance, mock_create_app

    def _bound_sockets(self, mock_server_instance):
        _, kwargs = mock_server_instance.run.call_args
        return kwargs["sockets"]

    def test_binds_an_ephemeral_port_when_zero(self, mocker, capsys):
        _, _, mock_server_instance, _ = self._run_with_mocks(mocker)

        run(port=0)

        sockets = self._bound_sockets(mock_server_instance)
        assert len(sockets) == 1
        bound_port = sockets[0].getsockname()[1]
        assert bound_port > 0

        out = capsys.readouterr().out
        assert f"DEVO_SIDECAR_READY port={bound_port} " in out
        sockets[0].close()

    def test_prints_ready_line(self, mocker, capsys):
        _, _, mock_server_instance, _ = self._run_with_mocks(mocker)

        run(port=0)

        out = capsys.readouterr().out
        assert "DEVO_SIDECAR_READY port=" in out
        assert "token=" in out
        self._bound_sockets(mock_server_instance)[0].close()

    def test_ready_line_printed_before_server_run(self, mocker, capsys):
        """The whole point of binding early: READY must be observable before
        the (potentially slow) uvicorn server loop starts, and the socket it
        hands off must already be listening by then."""
        _, _, mock_server_instance, _ = self._run_with_mocks(mocker)

        run(port=0)

        out = capsys.readouterr().out
        assert "DEVO_SIDECAR_READY" in out
        mock_server_instance.run.assert_called_once()
        self._bound_sockets(mock_server_instance)[0].close()

    def test_token_in_app_state(self, mocker, capsys):
        _, _, mock_server_instance, mock_create_app = self._run_with_mocks(mocker)
        captured_states = []

        def fake_create_app(app_state):
            captured_states.append(app_state)
            return MagicMock()

        mock_create_app.side_effect = fake_create_app

        run(port=0)

        out = capsys.readouterr().out
        token_part = [part for part in out.split() if part.startswith("token=")][0]
        printed_token = token_part[len("token=") :]

        assert captured_states[0].token == printed_token
        self._bound_sockets(mock_server_instance)[0].close()

    def test_server_run_called_with_correct_log_level(self, mocker, capsys):
        mock_server_class, mock_config_class, mock_server_instance, _ = self._run_with_mocks(mocker)

        run(port=0, host="127.0.0.1", log_level="info")

        _, kwargs = mock_config_class.call_args
        assert kwargs["log_level"] == "warning"
        mock_server_class.assert_called_once_with(mock_config_class.return_value)
        self._bound_sockets(mock_server_instance)[0].close()
