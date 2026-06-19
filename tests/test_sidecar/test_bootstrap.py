"""Unit tests for cli_tool.sidecar.bootstrap module."""

import socket
from unittest.mock import MagicMock, call, patch

import pytest

from cli_tool.sidecar.bootstrap import _find_free_port, run

# ---------------------------------------------------------------------------
# _find_free_port
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindFreePort:
    def test_returns_integer(self):
        port = _find_free_port()
        assert isinstance(port, int)
        assert port > 0

    def test_port_is_bindable(self):
        port = _find_free_port()
        # the socket was released by the time we get here, so binding should succeed
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRun:
    def _run_with_mocks(self, mocker, **kwargs):
        mock_uvicorn = mocker.patch("cli_tool.sidecar.bootstrap.uvicorn.run")
        mock_create_app = mocker.patch("cli_tool.sidecar.bootstrap.create_app", return_value=MagicMock())
        return mock_uvicorn, mock_create_app

    def test_uses_given_port_when_nonzero(self, mocker, capsys):
        mock_uvicorn, _ = self._run_with_mocks(mocker)
        mock_find = mocker.patch("cli_tool.sidecar.bootstrap._find_free_port")

        run(port=9999)

        mock_find.assert_not_called()
        _, kwargs = mock_uvicorn.call_args
        assert kwargs["port"] == 9999

    def test_uses_free_port_when_zero(self, mocker, capsys):
        mock_uvicorn, _ = self._run_with_mocks(mocker)
        mocker.patch("cli_tool.sidecar.bootstrap._find_free_port", return_value=54321)

        run(port=0)

        _, kwargs = mock_uvicorn.call_args
        assert kwargs["port"] == 54321

    def test_prints_ready_line(self, mocker, capsys):
        self._run_with_mocks(mocker)

        run(port=8080)

        out = capsys.readouterr().out
        assert "DEVO_SIDECAR_READY port=" in out
        assert "token=" in out

    def test_token_in_app_state(self, mocker, capsys):
        mock_uvicorn = mocker.patch("cli_tool.sidecar.bootstrap.uvicorn.run")
        captured_states = []

        def fake_create_app(app_state):
            captured_states.append(app_state)
            return MagicMock()

        mocker.patch("cli_tool.sidecar.bootstrap.create_app", side_effect=fake_create_app)

        run(port=7777)

        out = capsys.readouterr().out
        # extract token from the READY line
        token_part = [part for part in out.split() if part.startswith("token=")][0]
        printed_token = token_part[len("token=") :]

        assert captured_states[0].token == printed_token

    def test_uvicorn_called_with_correct_host_and_log_level(self, mocker, capsys):
        mock_uvicorn, _ = self._run_with_mocks(mocker)

        run(port=1234, host="0.0.0.0", log_level="info")

        _, kwargs = mock_uvicorn.call_args
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["log_level"] == "info"
