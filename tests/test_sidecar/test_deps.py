"""Unit tests for cli_tool.sidecar.deps module."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from cli_tool.sidecar.deps import get_app_state, require_bearer
from cli_tool.sidecar.state import AppState

# ---------------------------------------------------------------------------
# get_app_state
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetAppState:
    def test_returns_app_state(self):
        sentinel = object()
        request = MagicMock()
        request.app.state.app_state = sentinel
        assert get_app_state(request) is sentinel


# ---------------------------------------------------------------------------
# require_bearer
#
# The real signature is:
#   async def require_bearer(authorization: str = Header(...), app_state: AppState = Depends(...))
# FastAPI injects the args at runtime; in unit tests we call the function
# directly, bypassing DI.
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRequireBearer:
    def _make_state(self, token: str) -> AppState:
        import time

        state = AppState(token=token, token_created_at=time.time(), token_ttl_seconds=3600)
        return state

    def test_valid_token_passes(self):
        state = self._make_state("secret")
        # no exception expected
        asyncio.run(require_bearer(authorization="Bearer secret", app_state=state))

    def test_missing_header_raises_401(self):
        state = self._make_state("secret")
        # None header doesn't match "Bearer secret"
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_bearer(authorization=None, app_state=state))
        assert exc_info.value.status_code == 401

    def test_wrong_token_raises_401(self):
        state = self._make_state("secret")
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_bearer(authorization="Bearer wrong", app_state=state))
        assert exc_info.value.status_code == 401

    def test_malformed_header_raises_401(self):
        # "Token abc" is not the expected "Bearer secret" prefix
        state = self._make_state("secret")
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(require_bearer(authorization="Token abc", app_state=state))
        assert exc_info.value.status_code == 401
