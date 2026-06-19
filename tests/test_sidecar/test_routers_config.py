import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.routers.config import router
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}


def _make_client() -> tuple[TestClient, AppState]:
    app = FastAPI()
    registry = ForwarderRegistry()
    hub = EventHub()
    app_state = AppState(token="test-token", registry=registry, event_hub=hub)
    app.state.app_state = app_state
    app.include_router(router)
    return TestClient(app), app_state


@pytest.mark.unit
class TestGetConfig:
    def test_returns_config_from_loader(self, mocker):
        mock_load = mocker.patch(
            "cli_tool.sidecar.routers.config.load_config",
            return_value={"aws_login": {"set_env_profile": True}},
        )
        client, _ = _make_client()

        response = client.get("/config", headers=AUTH)

        assert response.status_code == 200
        assert response.json() == {"aws_login": {"set_env_profile": True}}
        mock_load.assert_called_once()


@pytest.mark.unit
class TestPutConfig:
    def test_saves_and_returns_body(self, mocker):
        mocker.patch("cli_tool.sidecar.routers.config.save_config")
        client, _ = _make_client()
        body = {"bedrock": {"model_id": "nova-lite", "region": "us-east-1"}}

        response = client.put("/config", json=body, headers=AUTH)

        assert response.status_code == 200
        assert response.json() == body

    def test_save_called_with_body(self, mocker):
        mock_save = mocker.patch("cli_tool.sidecar.routers.config.save_config")
        client, _ = _make_client()
        body = {"telemetry": {"enabled": False}}

        client.put("/config", json=body, headers=AUTH)

        mock_save.assert_called_once_with(body)


@pytest.mark.unit
class TestPatchConfig:
    def test_merges_top_level_key(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.config.load_config",
            return_value={"a": 1, "b": 2},
        )
        mocker.patch("cli_tool.sidecar.routers.config.save_config")
        client, _ = _make_client()

        response = client.patch("/config", json={"b": 3}, headers=AUTH)

        assert response.status_code == 200
        assert response.json() == {"a": 1, "b": 3}

    def test_null_removes_key(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.config.load_config",
            return_value={"a": 1, "b": 2},
        )
        mocker.patch("cli_tool.sidecar.routers.config.save_config")
        client, _ = _make_client()

        response = client.patch("/config", json={"b": None}, headers=AUTH)

        assert response.status_code == 200
        assert response.json() == {"a": 1}

    def test_nested_merge(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.config.load_config",
            return_value={"aws_login": {"set_env_profile": True, "x": 1}},
        )
        mocker.patch("cli_tool.sidecar.routers.config.save_config")
        client, _ = _make_client()

        response = client.patch("/config", json={"aws_login": {"x": 2}}, headers=AUTH)

        assert response.status_code == 200
        assert response.json() == {"aws_login": {"set_env_profile": True, "x": 2}}


@pytest.mark.unit
class TestGetConfigSchema:
    def test_schema_has_correct_shape(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.config.get_default_config",
            return_value={},
        )
        client, _ = _make_client()

        response = client.get("/config/schema", headers=AUTH)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Devo Config"
        assert "properties" in data
