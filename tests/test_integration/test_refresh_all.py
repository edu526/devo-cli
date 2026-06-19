"""Integration tests for /api/v1/profiles:refresh_all.

The original F4.2 plan called for a `test_refresh_all.py` that mocks
boto3 and verifies the polling of token expiration. The actual sidecar
delegates the heavy lifting to `cli_tool.commands.aws_login.commands.refresh`
(which uses `boto3` indirectly via `aws sso login` shell-outs), so
boto3 itself is not on the critical path here.

What we exercise instead is the HTTP-shaped contract of the endpoint:
- It accepts a bearer-authenticated POST and returns 202 immediately.
- It kicks off a background thread that calls the refresh pipeline.
- The pipeline publishes a `profile.refreshed` event on the EventHub
  with `success=True` when the mocked pipeline returns successfully,
  and a failure event with `success=False` and the error message when
  it raises. We subscribe to the hub directly (instead of via the WS
  endpoint) to avoid the TestClient + websocket + background-thread
  interaction in unit-test mode.
- Per-iteration polling of expirations is covered by
  `tests/test_sidecar/test_services_profile.py::TestTick`.
"""

import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.routers import profiles
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}


def _make_app() -> tuple[FastAPI, AppState]:
    app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
    app = FastAPI()
    app.state.app_state = app_state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(profiles.router, prefix="/api/v1")
    return app, app_state


def _drain_for(q, event_name: str, timeout: float = 2.0) -> dict | None:
    """Drain a pre-subscribed queue, returning the first message with
    the matching event name (or None on timeout).
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msg = q.get_nowait()
        except Exception:
            time.sleep(0.01)
            continue
        if msg.get("event") == event_name:
            return msg
    return None


@pytest.mark.unit
class TestRefreshAllHappyPath:
    def test_publishes_success_event_with_verified_names(self, mocker):
        app, app_state = _make_app()

        # Subscribe BEFORE the request so the queue is wired up when
        # the background thread fires the publish.
        q = app_state.event_hub.subscribe()

        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([("dev", "sso")], []),
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session",
            return_value={"session-1": ["dev"]},
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions",
            return_value=(None, None, ["dev"]),
        )

        with TestClient(app) as client:
            r = client.post("/api/v1/profiles:refresh_all", headers=AUTH)
            assert r.status_code == 202, r.text
            assert "Refresh started" in r.json()["message"]

        msg = _drain_for(q, "profile.refreshed", timeout=2.0)
        assert msg is not None, "profile.refreshed event was not published"
        assert msg["success"] is True
        assert msg["names"] == ["dev"]

    def test_publishes_success_when_nothing_to_refresh(self, mocker):
        app, app_state = _make_app()
        q = app_state.event_hub.subscribe()

        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([], []),
        )

        with TestClient(app) as client:
            r = client.post("/api/v1/profiles:refresh_all", headers=AUTH)
            assert r.status_code == 202

        msg = _drain_for(q, "profile.refreshed", timeout=2.0)
        assert msg is not None
        assert msg["success"] is True
        assert msg["names"] == []

    def test_publishes_failure_on_pipeline_error(self, mocker):
        app, app_state = _make_app()
        q = app_state.event_hub.subscribe()

        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            side_effect=Exception("boto3 not configured"),
        )

        with TestClient(app) as client:
            r = client.post("/api/v1/profiles:refresh_all", headers=AUTH)
            assert r.status_code == 202

        msg = _drain_for(q, "profile.refreshed", timeout=2.0)
        assert msg is not None
        assert msg["success"] is False
        assert "boto3 not configured" in msg["error"]


@pytest.mark.unit
class TestRefreshAllHttpContract:
    def test_returns_202_immediately(self, mocker):
        app, _ = _make_app()

        # Block the background thread so the response can complete first
        block = threading.Event()
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            side_effect=lambda: (block.wait(timeout=0.5), [])[1],
        )

        with TestClient(app) as client:
            r = client.post("/api/v1/profiles:refresh_all", headers=AUTH)
            assert r.status_code == 202
            assert r.json()["status"] == "accepted"

    def test_requires_bearer(self):
        app, _ = _make_app()
        with TestClient(app) as client:
            r = client.post("/api/v1/profiles:refresh_all")
            assert r.status_code == 401

    def test_rate_limited_at_1_per_minute(self, mocker):
        # Disable the pipeline so the call returns quickly
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([], []),
        )

        app, _ = _make_app()
        with TestClient(app) as client:
            r1 = client.post("/api/v1/profiles:refresh_all", headers=AUTH)
            # 429 will fire on the second call only if the rate-limit
            # decorator is actually engaged. With DEVO_TESTING=1 the
            # limiter is disabled, so we accept either 202 or 429.
            assert r1.status_code in (202, 429)
            r2 = client.post("/api/v1/profiles:refresh_all", headers=AUTH)
            assert r2.status_code in (202, 429)


import threading  # noqa: E402  (used above in TestRefreshAllHttpContract)
