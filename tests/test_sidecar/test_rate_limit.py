"""Unit tests for the rate limit wiring on sensitive endpoints."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.state import AppState, EventHub


def _make_client() -> TestClient:
    async def _noop_watch(*_args, **_kwargs):
        await asyncio.sleep(9999)

    # Patch the lifecycle and the inner services so the request handlers
    # do not perform any real work — the test only cares about the
    # 429 / Retry-After behaviour.
    import unittest.mock as mock

    patches = [
        mock.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch),
        mock.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock()),
    ]
    for p in patches:
        p.start()

    app_state = AppState(token="tok", registry=ForwarderRegistry(), event_hub=EventHub())
    return TestClient(create_app(app_state))


AUTH = {"Authorization": "Bearer tok"}


@pytest.mark.unit
class TestRateLimitDisabledInTests:
    """When DEVO_TESTING=1 is set (via conftest), the Limiter is enabled=False
    and endpoints can be hit repeatedly without 429. This guards against
    accidentally re-enabling the limiter for the test run.
    """

    def test_refresh_all_does_not_429_under_repeat_calls(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.get_profiles_info",
            return_value=[],
        )
        client = _make_client()
        for _ in range(3):
            response = client.get("/api/v1/profiles", headers=AUTH)
            assert response.status_code == 200


@pytest.mark.unit
class TestRateLimitReEnabled:
    """Direct check that the production code path enforces the limit.

    We construct a fresh Limiter with enabled=True and verify the
    shared instance uses the same configuration in production (i.e.
    `enabled=True`, `headers_enabled=True`).
    """

    def test_production_limiter_is_enabled_with_headers(self, monkeypatch):
        # Build a fresh limiter exactly like the production factory does
        # when DEVO_TESTING is not set.
        monkeypatch.delenv("DEVO_TESTING", raising=False)
        # Reimport to re-trigger _build_limiter
        import importlib

        from cli_tool.sidecar import rate_limit

        importlib.reload(rate_limit)

        assert rate_limit.limiter.enabled is True
        assert rate_limit.limiter._headers_enabled is True

    def test_testing_limiter_is_disabled(self, monkeypatch):
        monkeypatch.setenv("DEVO_TESTING", "1")
        import importlib

        from cli_tool.sidecar import rate_limit

        importlib.reload(rate_limit)

        assert rate_limit.limiter.enabled is False
