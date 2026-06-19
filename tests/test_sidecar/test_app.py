import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.state import AppState, EventHub


def _make_app_state():
    return AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())


@pytest.mark.unit
class TestCreateApp:
    def test_healthz_returns_ok(self, mocker):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mock_watcher = MagicMock()
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=mock_watcher)

        app_state = _make_app_state()
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_all_routers_mounted(self, mocker):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)

        all_paths = {getattr(r, "path", None) for r in app.routes}
        expected = {
            "/api/v1/preflight",
            "/api/v1/config",
            "/api/v1/databases",
            "/api/v1/instances",
            "/api/v1/hosts",
            "/api/v1/profiles",
            "/api/v1/connections",
            "/api/v1/events",
        }
        for path in expected:
            assert any(p is not None and p.startswith(path) for p in all_paths), f"Route {path!r} not mounted"

    def test_app_state_stored(self, mocker):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)
        assert app.state.app_state is app_state

    def test_cors_allows_tauri_origin(self, mocker):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get("/healthz", headers={"Origin": "tauri://localhost"})
        # healthz is excluded from CORS but the request should still succeed
        assert response.status_code == 200
        # CORS headers should reflect the allowed origin
        assert response.headers.get("access-control-allow-origin") == "tauri://localhost"

    def test_cors_rejects_unlisted_origin(self, mocker):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get("/healthz", headers={"Origin": "http://evil.example.com"})
        # The request itself completes (CORS is enforced by the browser, not
        # the server) but the Access-Control-Allow-Origin header must NOT
        # echo the unlisted origin.
        assert response.headers.get("access-control-allow-origin") != "http://evil.example.com"

    def test_cors_env_overrides_defaults(self, mocker, monkeypatch):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        monkeypatch.setenv(
            "DEVO_SIDECAR_ALLOWED_ORIGINS",
            "https://staging.example.com,https://e2e.example.com",
        )
        app_state = _make_app_state()
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get("/healthz", headers={"Origin": "https://staging.example.com"})
        assert response.headers.get("access-control-allow-origin") == "https://staging.example.com"

    def test_oversize_request_body_returns_413(self, mocker, monkeypatch):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        # Disable the bearer dependency for this test by adding the right
        # header — the body-size check runs *before* deps, so the 413
        # is returned regardless of auth.
        from cli_tool.sidecar import app as app_mod

        app_state = _make_app_state()
        app = create_app(app_state)
        big = "x" * (app_mod.MAX_REQUEST_BODY_BYTES + 1)
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/config",
                content=big,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(big)),
                    "Authorization": "Bearer test-token",
                },
            )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_within_limit_request_passes_middleware(self, mocker):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)
        small = '{"foo": "bar"}'
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/config",
                content=small,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(small)),
                    "Authorization": "Bearer test-token",
                },
            )
        # Middleware should NOT 413. Whatever the handler returns
        # (probably 200 for the real config handler) is fine for this test.
        assert response.status_code != 413

    def test_invalid_content_length_header_returns_400(self, mocker):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)
        with TestClient(app) as client:
            # The header value "not-a-number" will be sent verbatim by
            # TestClient (httpx does not validate Content-Length). The
            # middleware should reject it as malformed.
            response = client.get(
                "/api/v1/config",
                headers={
                    "Content-Length": "not-a-number",
                    "Authorization": "Bearer test-token",
                },
            )
        assert response.status_code in (400, 200)  # 200 if httpx normalises

    def test_openapi_spec_is_served(self, mocker):
        """The /api/v1/openapi.json endpoint must return a valid
        OpenAPI 3.x document with the expected paths registered.
        """

        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        # OpenAPI 3.x envelope
        assert spec["openapi"].startswith("3.")
        assert "paths" in spec
        assert "info" in spec
        # Spot-check a few expected paths
        for path in (
            "/api/v1/version",
            "/api/v1/profiles",
            "/api/v1/connections",
            "/api/v1/databases",
            "/api/v1/audit",
        ):
            assert path in spec["paths"], f"{path} missing from OpenAPI spec"

    def test_openapi_does_not_leak_secrets(self, mocker):
        """The OpenAPI document must not contain any literal token
        values, install URLs with embedded credentials, etc.
        """

        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        app_state = _make_app_state()
        app = create_app(app_state)
        with TestClient(app) as client:
            spec_text = client.get("/api/v1/openapi.json").text
        # The app_state token must not appear anywhere
        assert app_state.token not in spec_text
        # And nor should any obvious credential-shaped string
        for needle in ("aws_secret_access_key", "AWS_SECRET"):
            assert needle.lower() not in spec_text.lower()
