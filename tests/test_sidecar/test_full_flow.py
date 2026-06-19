"""End-to-end flow tests for the sidecar: create a database, start a
connection, verify state via WebSocket, stop.

These tests run against the in-process FastAPI app (via TestClient) and
the real services (no mocks for the connection_runner). The SSM
subprocess is replaced with a stub that immediately reports 'connected'
so the loop transitions to a steady state.
"""

import asyncio
import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from cli_tool.commands.ssm.core.connection_runner import (
    ConnectionRecord,
    ForwarderRegistry,
)
from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.routers import (
    audit,
    auth,
    config,
    connections,
    databases,
    hosts,
    instances,
    log_router,
    preflight,
    profiles,
    version,
    ws,
)
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}


def _make_app() -> tuple[FastAPI, AppState]:
    """Create a sidecar FastAPI app with the slowapi shim enabled for tests."""
    app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
    app = FastAPI()
    app.state.app_state = app_state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    api_prefix = "/api/v1"
    for r in (
        preflight.router,
        version.router,
        auth.router,
        audit.router,
        config.router,
        databases.router,
        instances.router,
        hosts.router,
        profiles.router,
        connections.router,
        ws.router,
        log_router.router,
    ):
        app.include_router(r, prefix=api_prefix)

    @app.get("/healthz", include_in_schema=False)
    def _h():
        return {"status": "ok"}

    return app, app_state


def _patch_config_with_db(name: str, **overrides) -> dict:
    cfg = {
        "bastion": "bastion-1",
        "host": "db.example.com",
        "port": 5432,
        "region": "us-east-1",
        "local_address": "127.0.0.1",
    }
    cfg.update(overrides)
    return cfg


@pytest.mark.unit
class TestDatabaseCRUDFlow:
    def test_create_then_list_then_update_then_delete(self, mocker):
        from cli_tool.sidecar.routers import databases as db_router

        app, _ = _make_app()
        storage: dict[str, dict] = {}
        mock_mgr = MagicMock()
        mock_mgr.list_databases.side_effect = lambda: dict(storage)
        mock_mgr.get_database.side_effect = lambda n: storage.get(n)
        mock_mgr.add_database.side_effect = lambda name, **kwargs: storage.__setitem__(name, dict(kwargs))
        mock_mgr.remove_database.side_effect = lambda n: storage.pop(n, None) is not None
        mocker.patch.object(db_router, "SSMConfigManager", return_value=mock_mgr)

        with TestClient(app) as client:
            # Create
            r = client.post(
                "/api/v1/databases/mydb",
                json={
                    "bastion": "bastion-1",
                    "host": "db.example.com",
                    "port": 5432,
                    "region": "us-east-1",
                },
                headers=AUTH,
            )
            assert r.status_code == 201, r.text
            assert r.json()["bastion"] == "bastion-1"

            # List
            r = client.get("/api/v1/databases", headers=AUTH)
            assert r.status_code == 200
            assert "mydb" in r.json()

            # Update
            r = client.patch(
                "/api/v1/databases/mydb",
                json={"port": 6543},
                headers=AUTH,
            )
            assert r.status_code == 200
            assert r.json()["port"] == 6543

            # Delete
            r = client.delete("/api/v1/databases/mydb", headers=AUTH)
            assert r.status_code == 204
            assert "mydb" not in client.get("/api/v1/databases", headers=AUTH).json()

    def test_create_conflict_returns_409(self, mocker):
        from cli_tool.sidecar.routers import databases as db_router

        app, _ = _make_app()
        # Pre-populate so the create endpoint sees the entry as existing.
        storage: dict[str, dict] = {"x": {"bastion": "b", "host": "h", "port": 5432, "region": "us-east-1"}}
        mock_mgr = MagicMock()
        mock_mgr.get_database.side_effect = lambda n: storage.get(n)
        # add_database is a no-op because the guard should fire first
        mock_mgr.add_database.side_effect = lambda *a, **kw: None
        mocker.patch.object(db_router, "SSMConfigManager", return_value=mock_mgr)

        body = {"bastion": "b", "host": "h", "port": 5432, "region": "us-east-1"}
        with TestClient(app) as client:
            r = client.post("/api/v1/databases/x", json=body, headers=AUTH)
            assert r.status_code == 409
            assert "already exists" in r.json()["detail"]


@pytest.mark.unit
class TestConnectionLifecycleFlow:
    def test_start_then_list_then_stop(self, mocker):
        from cli_tool.sidecar.services import connection_service as cs

        app, app_state = _make_app()

        storage = {"mydb": _patch_config_with_db("mydb")}
        mock_mgr = MagicMock()
        mock_mgr.get_database.side_effect = lambda n: storage.get(n)
        mock_mgr.list_databases.side_effect = lambda: dict(storage)
        mocker.patch.object(cs, "SSMConfigManager", return_value=mock_mgr)

        # Patch HostsManager so it doesn't try to read /etc/hosts
        mock_hosts = MagicMock()
        mock_hosts.get_managed_entries.return_value = []
        mocker.patch("cli_tool.sidecar.services.connection_service.HostsManager", return_value=mock_hosts)

        # Patch the connection loop to immediately mark "connected" and exit
        def fake_loop(name, db_config, local_port, use_hostname_forwarding, registry, record):
            record.state = "connected"
            registry.emit("connection.state_changed", {"name": name, "state": "connected", "local_port": local_port})
            return  # exits cleanly

        mocker.patch(
            "cli_tool.sidecar.services.connection_service._run_connection_loop",
            side_effect=fake_loop,
        )

        with TestClient(app) as client:
            r = client.post("/api/v1/connections/mydb", headers=AUTH)
            assert r.status_code == 202
            body = r.json()
            assert body["name"] == "mydb"
            assert body["state"] == "starting"

            # Allow the (synchronous-in-test) fake_loop to run
            time.sleep(0.1)

            r = client.get("/api/v1/connections", headers=AUTH)
            assert r.status_code == 200
            conns = r.json()
            assert len(conns) == 1
            assert conns[0]["name"] == "mydb"

            r = client.delete("/api/v1/connections/mydb", headers=AUTH)
            assert r.status_code == 204

    def test_404_on_stop_unknown(self):
        app, _ = _make_app()
        with TestClient(app) as client:
            r = client.delete("/api/v1/connections/missing", headers=AUTH)
            assert r.status_code == 404

    def test_start_404_for_unknown_database(self, mocker):
        from cli_tool.sidecar.services import connection_service as cs

        app, _ = _make_app()
        mock_mgr = MagicMock()
        mock_mgr.get_database.return_value = None
        mocker.patch.object(cs, "SSMConfigManager", return_value=mock_mgr)
        with TestClient(app) as client:
            r = client.post("/api/v1/connections/nope", headers=AUTH)
            assert r.status_code == 404


@pytest.mark.unit
class TestWebSocketEventsFlow:
    def test_websocket_receives_state_change_after_start(self, mocker):
        from cli_tool.sidecar.services import connection_service as cs

        app, _ = _make_app()

        storage = {"mydb": _patch_config_with_db("mydb")}
        mock_mgr = MagicMock()
        mock_mgr.get_database.side_effect = lambda n: storage.get(n)
        mock_mgr.list_databases.side_effect = lambda: dict(storage)
        mocker.patch.object(cs, "SSMConfigManager", return_value=mock_mgr)
        mock_hosts = MagicMock()
        mock_hosts.get_managed_entries.return_value = []
        mocker.patch.object(cs, "HostsManager", return_value=mock_hosts)

        # The fake loop publishes a single event then returns
        def fake_loop(name, db_config, local_port, use_hostname_forwarding, registry, record):
            registry.emit("connection.state_changed", {"name": name, "state": "connected", "local_port": local_port})

        mocker.patch(
            "cli_tool.sidecar.services.connection_service._run_connection_loop",
            side_effect=fake_loop,
        )

        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/events", subprotocols=["bearer", "test-token"]) as ws_conn:
                # First message is the "hello" handshake
                hello = json.loads(ws_conn.receive_text())
                assert hello["event"] == "hello"

                # Trigger the state change via the HTTP endpoint
                r = client.post("/api/v1/connections/mydb", headers=AUTH)
                assert r.status_code == 202

                # Next message should be the connection.state_changed
                msg = json.loads(ws_conn.receive_text())
                assert msg["event"] == "connection.state_changed"
                assert msg["name"] == "mydb"
                assert msg["state"] == "connected"
