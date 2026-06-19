from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.routers.connections import router
from cli_tool.sidecar.state import AppState, EventHub


def _make_client():
    app = FastAPI()
    app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
    app.state.app_state = app_state
    # Rate limit decorators need access to the limiter and middleware; mount
    # both here so per-router tests can exercise the limit decorators.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(router)
    return TestClient(app), app_state


AUTH = {"Authorization": "Bearer test-token"}


@pytest.mark.unit
class TestGetConnections:
    def test_returns_list(self, mocker):
        connections = [{"name": "mydb", "state": "connected", "local_port": 15432, "error": None}]
        mocker.patch(
            "cli_tool.sidecar.routers.connections.list_connections",
            return_value=connections,
        )
        client, _ = _make_client()
        response = client.get("/connections", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == connections


@pytest.mark.unit
class TestStartAll:
    def test_returns_202_list(self, mocker):
        results = [
            {"name": "db1", "local_port": 15432, "state": "starting"},
            {"name": "db2", "local_port": 15433, "state": "starting"},
        ]
        mocker.patch(
            "cli_tool.sidecar.routers.connections.start_all_connections",
            return_value=results,
        )
        client, _ = _make_client()
        response = client.post("/connections:start_all", headers=AUTH)
        assert response.status_code == 202
        assert response.json() == results


@pytest.mark.unit
class TestStopAll:
    def test_returns_204(self, mocker):
        mock_stop = mocker.patch(
            "cli_tool.sidecar.routers.connections.stop_all_connections",
            return_value=None,
        )
        client, _ = _make_client()
        response = client.delete("/connections", headers=AUTH)
        assert response.status_code == 204
        mock_stop.assert_called_once()


@pytest.mark.unit
class TestStartOne:
    def test_starts_connection_202(self, mocker):
        result = {"name": "mydb", "local_port": 15432, "state": "starting"}
        mocker.patch(
            "cli_tool.sidecar.routers.connections.start_connection",
            return_value=result,
        )
        client, _ = _make_client()
        response = client.post("/connections/mydb", headers=AUTH)
        assert response.status_code == 202
        assert response.json() == result

    def test_not_found_404(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.connections.start_connection",
            side_effect=KeyError("Database 'mydb' not configured"),
        )
        client, _ = _make_client()
        response = client.post("/connections/mydb", headers=AUTH)
        assert response.status_code == 404

    def test_conflict_409(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.connections.start_connection",
            side_effect=ValueError("Connection 'mydb' is already active"),
        )
        client, _ = _make_client()
        response = client.post("/connections/mydb", headers=AUTH)
        assert response.status_code == 409


@pytest.mark.unit
class TestStopOne:
    def test_stops_204(self, mocker):
        mock_stop = mocker.patch(
            "cli_tool.sidecar.routers.connections.stop_connection",
            return_value=None,
        )
        client, app_state = _make_client()
        app_state.registry.get = lambda name: {"name": name, "state": "connected"}
        response = client.delete("/connections/mydb", headers=AUTH)
        assert response.status_code == 204
        mock_stop.assert_called_once_with("mydb", app_state.registry)

    def test_not_found_404(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.connections.stop_connection",
            return_value=None,
        )
        client, app_state = _make_client()
        app_state.registry.get = lambda name: None
        response = client.delete("/connections/missing", headers=AUTH)
        assert response.status_code == 404
