"""Integration tests for the /api/v1/preflight endpoint.

Covers the F4.2 plan item: "mock subprocess con aws/socat/sm-plugin
presentes y ausentes". The endpoint runs four checks:

  - aws_cli          (subprocess `aws --version`)
  - session_manager_plugin (subprocess `session-manager-plugin`)
  - socat            (subprocess `socat -V`; Windows reports n/a)
  - sso_configured   (read ~/.aws/config via list_aws_profiles)
  - config_exists    (~/.devo/config.json)

Each test patches the subprocess layer to simulate the binary being
present, absent, hanging, or returning a malformed version line.
"""

import platform
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}


def _make_app() -> TestClient:
    app_state = AppState(token="test-token", event_hub=EventHub())
    app = create_app(app_state)
    return TestClient(app), app_state


def _mock_run(aws_out="aws-cli/2.17.0 Python/3.12", sm_ok=True, socat_out="socat version 1.7.4.4"):
    """Build a side_effect for subprocess.run that returns the given
    canned output for each command.
    """

    def fake_run(cmd, *args, **kwargs):
        binary = cmd[0] if cmd else ""
        if binary == "aws":
            return MagicMock(stdout=aws_out, stderr="", returncode=0)
        if binary == "session-manager-plugin":
            return MagicMock(
                stdout=sm_ok and "sm-plugin" or "",
                stderr="",
                returncode=0 if sm_ok else 1,
            )
        if binary == "socat":
            return MagicMock(stdout=socat_out, stderr="", returncode=0)
        return MagicMock(stdout="", stderr="", returncode=0)

    return fake_run


@pytest.mark.unit
class TestPreflightAllPresent:
    def test_reports_all_tools_installed(self):
        client, _ = _make_app()
        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=_mock_run()):
            r = client.get("/api/v1/preflight")
        assert r.status_code == 200
        body = r.json()
        assert body["aws_cli"]["ok"] is True
        assert body["aws_cli"]["version"] == "2.17.0"
        assert body["session_manager_plugin"]["ok"] is True
        assert body["socat"]["ok"] is True
        if platform.system() == "Windows":
            assert body["socat"]["version"] == "n/a (Windows uses netsh)"
        else:
            assert body["socat"]["version"] == "1.7.4.4"

    def test_does_not_require_bearer(self):
        client, _ = _make_app()
        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=_mock_run()):
            r = client.get("/api/v1/preflight")  # no Authorization header
        assert r.status_code == 200


@pytest.mark.unit
class TestPreflightMissingTools:
    def test_aws_cli_missing(self):
        client, _ = _make_app()

        def fake_run(cmd, *args, **kwargs):
            raise FileNotFoundError("aws not found")

        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=fake_run):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["aws_cli"]["ok"] is False
        assert body["aws_cli"]["version"] is None

    def test_session_manager_plugin_missing(self):
        client, _ = _make_app()

        def fake_run(cmd, *args, **kwargs):
            if cmd[0] == "session-manager-plugin":
                raise FileNotFoundError
            return _mock_run()(cmd, *args, **kwargs)

        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=fake_run):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["session_manager_plugin"]["ok"] is False
        assert "install_url" in body["session_manager_plugin"]

    def test_socat_missing(self):
        if platform.system() == "Windows":
            pytest.skip("socat is reported as n/a on Windows")

        client, _ = _make_app()

        def fake_run(cmd, *args, **kwargs):
            if cmd[0] == "socat":
                raise FileNotFoundError
            return _mock_run()(cmd, *args, **kwargs)

        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=fake_run):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["socat"]["ok"] is False
        assert body["socat"]["version"] is None

    def test_subprocess_timeout_is_caught(self):
        import subprocess

        client, _ = _make_app()

        def fake_run(cmd, *args, **kwargs):
            raise subprocess.TimeoutExpired(cmd, timeout=2)

        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=fake_run):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["aws_cli"]["ok"] is False


@pytest.mark.unit
class TestPreflightVersionParsing:
    def test_unparseable_aws_version(self):
        client, _ = _make_app()
        with patch(
            "cli_tool.sidecar.services.preflight_service.subprocess.run",
            side_effect=_mock_run(aws_out="weird output format"),
        ):
            r = client.get("/api/v1/preflight")
        body = r.json()
        # ok=True (subprocess succeeded) but version is None
        assert body["aws_cli"]["ok"] is True
        assert body["aws_cli"]["version"] is None

    def test_socat_no_version_line(self):
        if platform.system() == "Windows":
            pytest.skip("socat is reported as n/a on Windows")

        client, _ = _make_app()
        with patch(
            "cli_tool.sidecar.services.preflight_service.subprocess.run",
            side_effect=_mock_run(socat_out="socat by Gerhard Rieger"),
        ):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["socat"]["ok"] is True
        assert body["socat"]["version"] is None


@pytest.mark.unit
class TestPreflightSsoAndConfig:
    def test_sso_configured(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.list_aws_profiles",
            return_value=[("default", "credentials"), ("dev", "sso"), ("prod", "sso")],
        )
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.get_config_file",
            return_value=MagicMock(exists=MagicMock(return_value=True), __str__=MagicMock(return_value="/home/x/.devo/config.json")),
        )

        client, _ = _make_app()
        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=_mock_run()):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["sso_configured"]["ok"] is True
        assert body["sso_configured"]["profiles"] == 2
        assert body["config_exists"]["ok"] is True

    def test_sso_profiles_load_fails(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.list_aws_profiles",
            side_effect=Exception("aws config corrupt"),
        )
        mocker.patch(
            "cli_tool.sidecar.services.preflight_service.get_config_file",
            return_value=MagicMock(exists=MagicMock(return_value=False), __str__=MagicMock(return_value="/home/x/.devo/config.json")),
        )

        client, _ = _make_app()
        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=_mock_run()):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["sso_configured"]["ok"] is False
        assert body["sso_configured"]["profiles"] == 0
        assert body["config_exists"]["ok"] is False


@pytest.mark.unit
class TestPreflightWindowsSocat:
    def test_socat_reported_as_na_on_windows(self, mocker):
        mocker.patch("cli_tool.sidecar.services.preflight_service.platform.system", return_value="Windows")

        client, _ = _make_app()
        with patch("cli_tool.sidecar.services.preflight_service.subprocess.run", side_effect=_mock_run()):
            r = client.get("/api/v1/preflight")
        body = r.json()
        assert body["socat"]["ok"] is True
        assert "n/a" in (body["socat"].get("version") or "")
        # subprocess.run must not have been called for `socat` on Windows;
        # we can't easily prove that from the response alone, but the
        # version string proves the codepath branched correctly.
