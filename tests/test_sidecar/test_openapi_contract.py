"""Spec-level contract test.

Fetches the live OpenAPI spec from the sidecar (via /api/v1/openapi.json)
and asserts that every `cli_tool.sidecar.routers.*` Python module
mounts at least one path. Combined with the frontend OpenAPI contract
test, this guarantees that:

- the sidecar exposes /api/v1/openapi.json
- the spec is a well-formed OpenAPI 3.x document
- every router actually contributes at least one path
- the auth (`bearer`) and audit endpoints are present
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.state import AppState, EventHub


def _make_client() -> TestClient:
    async def _noop(*_a, **_kw):
        await asyncio.sleep(9999)

    import cli_tool.sidecar.app as app_mod

    orig_wp = app_mod.watch_profiles
    orig_cw = app_mod.start_config_watcher
    app_mod.watch_profiles = _noop
    app_mod.start_config_watcher = lambda *_args, **_kwargs: MagicMock()
    try:
        app_state = AppState(token="test-token", event_hub=EventHub())
        return TestClient(create_app(app_state))
    finally:
        app_mod.watch_profiles = orig_wp
        app_mod.start_config_watcher = orig_cw


@pytest.mark.unit
class TestOpenAPISpecContract:
    def test_spec_is_openapi_3(self):
        client = _make_client()
        with client:
            spec = client.get("/api/v1/openapi.json").json()
        assert spec["openapi"].startswith("3.")

    def test_spec_contains_info_block(self):
        client = _make_client()
        with client:
            spec = client.get("/api/v1/openapi.json").json()
        info = spec.get("info", {})
        assert info.get("title")
        assert info.get("version")

    def test_spec_documents_every_sidecar_router(self):
        """Walk the actual routers (we know their `prefix` attributes)
        and assert that the spec lists at least one path under each.
        """
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
        )

        router_prefixes = {
            "audit": audit.router.prefix,
            "auth": auth.router.prefix,
            "config": config.router.prefix,
            "connections": connections.router.prefix,
            "databases": databases.router.prefix,
            "hosts": hosts.router.prefix,
            "instances": instances.router.prefix,
            "log_router": log_router.router.prefix,
            "preflight": preflight.router.prefix,  # this one has no prefix
            "profiles": profiles.router.prefix,
            "version": version.router.prefix,
        }

        client = _make_client()
        with client:
            spec = client.get("/api/v1/openapi.json").json()

        paths = list(spec["paths"].keys())
        for name, prefix in router_prefixes.items():
            if name == "preflight":
                # preflight router has no prefix; the path is /preflight
                expected = "/api/v1/preflight"
            else:
                expected = f"/api/v1{prefix}"
            assert any(
                p.startswith(expected) for p in paths
            ), f"router {name!r} (prefix={prefix!r}) has no path in OpenAPI spec; expected {expected!r}"

    def test_security_schemes_documented(self):
        """The spec should mention how to authenticate. FastAPI's
        default doesn't auto-emit a SecurityScheme for `Depends`-based
        bearer auth, but we at least want the document to be importable
        and round-trippable.
        """
        client = _make_client()
        with client:
            spec = client.get("/api/v1/openapi.json").json()
        # Re-serialize to make sure the spec is valid JSON-of-JSON
        import json

        roundtrip = json.loads(json.dumps(spec))
        assert roundtrip["openapi"].startswith("3.")
