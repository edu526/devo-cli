from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.routers.instances import router
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}

_INST_BODY = {
    "instance_id": "i-0abc123456",
    "region": "us-east-1",
    "profile": None,
}


def _make_client() -> tuple[TestClient, AppState]:
    app = FastAPI()
    registry = ForwarderRegistry()
    hub = EventHub()
    app_state = AppState(token="test-token", registry=registry, event_hub=hub)
    app.state.app_state = app_state
    app.include_router(router)
    return TestClient(app), app_state


def _mock_manager(mocker) -> MagicMock:
    instance = MagicMock()
    mocker.patch(
        "cli_tool.sidecar.routers.instances.SSMConfigManager",
        return_value=instance,
    )
    return instance


@pytest.mark.unit
class TestListInstances:
    def test_returns_dict(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.list_instances.return_value = {"bastion": {}}
        client, _ = _make_client()

        response = client.get("/instances", headers=AUTH)

        assert response.status_code == 200
        assert response.json() == {"bastion": {}}


@pytest.mark.unit
class TestCreateInstance:
    def test_creates_returns_201(self, mocker):
        mgr = _mock_manager(mocker)
        created_record = {**_INST_BODY}
        mgr.get_instance.side_effect = [None, created_record]
        client, _ = _make_client()

        response = client.post("/instances/bastion", json=_INST_BODY, headers=AUTH)

        assert response.status_code == 201
        assert response.json() == created_record
        mgr.add_instance.assert_called_once()

    def test_conflict_409(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_instance.return_value = {**_INST_BODY}
        client, _ = _make_client()

        response = client.post("/instances/bastion", json=_INST_BODY, headers=AUTH)

        assert response.status_code == 409


@pytest.mark.unit
class TestGetInstance:
    def test_found_200(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_instance.return_value = {**_INST_BODY}
        client, _ = _make_client()

        response = client.get("/instances/bastion", headers=AUTH)

        assert response.status_code == 200
        assert response.json() == _INST_BODY

    def test_not_found_404(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_instance.return_value = None
        client, _ = _make_client()

        response = client.get("/instances/ghost", headers=AUTH)

        assert response.status_code == 404


@pytest.mark.unit
class TestPatchInstance:
    def test_updates_fields(self, mocker):
        existing = {**_INST_BODY}
        updated = {**_INST_BODY, "region": "eu-west-1"}
        mgr = _mock_manager(mocker)
        mgr.get_instance.side_effect = [existing, updated]
        client, _ = _make_client()

        response = client.patch("/instances/bastion", json={"region": "eu-west-1"}, headers=AUTH)

        assert response.status_code == 200
        mgr.add_instance.assert_called_once()
        call_kwargs = mgr.add_instance.call_args.kwargs
        assert call_kwargs["region"] == "eu-west-1"

    def test_not_found_404(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_instance.return_value = None
        client, _ = _make_client()

        response = client.patch("/instances/ghost", json={"region": "ap-southeast-1"}, headers=AUTH)

        assert response.status_code == 404


@pytest.mark.unit
class TestDeleteInstance:
    def test_deletes_204(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.remove_instance.return_value = True
        client, _ = _make_client()

        response = client.delete("/instances/bastion", headers=AUTH)

        assert response.status_code == 204
        mgr.remove_instance.assert_called_once_with("bastion")

    def test_not_found_404(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.remove_instance.return_value = False
        client, _ = _make_client()

        response = client.delete("/instances/ghost", headers=AUTH)

        assert response.status_code == 404
