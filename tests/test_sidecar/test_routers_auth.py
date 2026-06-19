"""Unit tests for cli_tool.sidecar.routers.auth and the TTL behavior."""

import asyncio
import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.deps import require_bearer
from cli_tool.sidecar.state import AppState, EventHub

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state() -> AppState:
    return AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())


def _patched_app(mocker, app_state: AppState) -> TestClient:
    async def _noop_watch(*_args, **_kwargs):
        await asyncio.sleep(9999)

    mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
    mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())
    return TestClient(create_app(app_state))


# ---------------------------------------------------------------------------
# /api/v1/auth/refresh
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthRefresh:
    def test_refresh_with_valid_token_returns_new_token(self, mocker):
        state = _make_state()
        client = _patched_app(mocker, state)
        original = state.token

        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {original}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token"] != original
        assert state.token == body["token"]
        assert "expires_at" in body
        assert "issued_at" in body

    def test_refresh_invalidates_previous_token(self, mocker):
        state = _make_state()
        client = _patched_app(mocker, state)
        original = state.token

        client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {original}"})

        # Replaying the old token should now be rejected by require_bearer.
        response = client.get(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {original}"},
        )
        assert response.status_code == 401

    def test_refresh_without_header_rejects(self, mocker):
        state = _make_state()
        client = _patched_app(mocker, state)
        response = client.post("/api/v1/auth/refresh")
        assert response.status_code == 401

    def test_refresh_with_wrong_token_rejects(self, mocker):
        state = _make_state()
        client = _patched_app(mocker, state)
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": "Bearer not-the-real-token"},
        )
        assert response.status_code == 401

    def test_refresh_with_malformed_header_rejects(self, mocker):
        state = _make_state()
        client = _patched_app(mocker, state)
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": "Token abc"},
        )
        assert response.status_code == 401

    def test_refresh_with_too_old_token_rejects(self, mocker):
        state = _make_state()
        # Backdate the token beyond 2 * TTL
        state.token_created_at = time.time() - (state.token_ttl_seconds * 3)
        client = _patched_app(mocker, state)
        response = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {state.token}"},
        )
        assert response.status_code == 401
        assert "too old" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TTL behavior in require_bearer
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRequireBearerTtl:
    def test_expired_token_raises_401(self):
        state = AppState(token="t", token_created_at=time.time() - 99999, token_ttl_seconds=60)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_bearer(authorization="Bearer t", app_state=state))
        assert exc_info.value.status_code == 401
        assert "expired" in str(exc_info.value.detail).lower()

    def test_fresh_token_passes(self):
        state = AppState(token="t", token_created_at=time.time(), token_ttl_seconds=60)
        asyncio.run(require_bearer(authorization="Bearer t", app_state=state))

    def test_empty_token_in_state_raises(self):
        state = AppState(token="", token_created_at=time.time(), token_ttl_seconds=60)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_bearer(authorization="Bearer t", app_state=state))
        assert exc_info.value.status_code == 401

    def test_wrong_token_raises(self):
        state = AppState(token="real", token_created_at=time.time(), token_ttl_seconds=60)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_bearer(authorization="Bearer wrong", app_state=state))
        assert exc_info.value.status_code == 401

    def test_missing_authorization_header_raises(self):
        state = AppState(token="t", token_created_at=time.time(), token_ttl_seconds=60)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_bearer(authorization=None, app_state=state))
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# AppState token lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAppStateTokenLifecycle:
    def test_issue_token_sets_token_and_timestamp(self):
        state = _make_state()
        state.issue_token()
        assert state.token
        assert state.token_created_at > 0
        assert not state.token_expired()

    def test_issue_token_invalidates_previous(self):
        state = _make_state()
        old = state.issue_token()
        new = state.issue_token()
        assert old != new
        assert state.token == new

    def test_token_expired_true_after_ttl(self):
        state = _make_state()
        state.token_ttl_seconds = 1
        state.token_created_at = time.time() - 2
        assert state.token_expired()

    def test_token_age_seconds_increases(self):
        state = _make_state()
        state.token_created_at = time.time() - 30
        assert 29 <= state.token_age_seconds() <= 31

    def test_token_expires_at_is_created_at_plus_ttl(self):
        state = _make_state()
        state.issue_token()
        assert state.token_expires_at() == pytest.approx(state.token_created_at + state.token_ttl_seconds, abs=0.01)

    def test_token_expired_when_token_empty(self):
        state = _make_state()
        state.token = ""
        assert state.token_expired()
