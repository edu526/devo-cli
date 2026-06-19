import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.sidecar.routers.version import _build_version_payload, get_version, router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.unit
def test_get_version_returns_expected_shape():
    client = _make_client()
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "sidecar_version",
        "server_version",
        "build_date",
        "update_available",
    }


@pytest.mark.unit
def test_get_version_update_available_is_false():
    """Frontend consults Tauri updater directly; the sidecar never claims an update."""
    client = _make_client()
    body = client.get("/version").json()
    assert body["update_available"] is False


@pytest.mark.unit
def test_build_version_payload_sidecar_and_server_match():
    payload = _build_version_payload()
    assert payload["sidecar_version"] == payload["server_version"]
    assert payload["sidecar_version"] != ""


@pytest.mark.unit
def test_build_version_payload_build_date_is_none_or_isoformat():
    payload = _build_version_payload()
    if payload["build_date"] is not None:
        from datetime import datetime

        datetime.fromisoformat(payload["build_date"])


@pytest.mark.unit
def test_get_version_is_callable_directly():
    """Direct function call also returns the same shape (no FastAPI required)."""
    payload = get_version()
    assert "sidecar_version" in payload
    assert "update_available" in payload
