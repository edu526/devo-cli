from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.routers.databases import router
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}

_DB_BODY = {
    "bastion": "i-0abc123",
    "host": "db.internal",
    "port": 5432,
    "region": "us-east-1",
    "profile": None,
    "local_port": None,
    "local_address": "127.0.0.1",
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
        "cli_tool.sidecar.routers.databases.SSMConfigManager",
        return_value=instance,
    )
    return instance


@pytest.mark.unit
class TestListDatabases:
    def test_returns_dict(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.list_databases.return_value = {"db1": {}}
        client, _ = _make_client()

        response = client.get("/databases", headers=AUTH)

        assert response.status_code == 200
        assert response.json() == {"db1": {}}


@pytest.mark.unit
class TestCreateDatabase:
    def test_creates_and_returns_201(self, mocker):
        mgr = _mock_manager(mocker)
        created_record = {**_DB_BODY}
        mgr.get_database.side_effect = [None, created_record]
        client, _ = _make_client()

        response = client.post("/databases/mydb", json=_DB_BODY, headers=AUTH)

        assert response.status_code == 201
        assert response.json() == created_record
        mgr.add_database.assert_called_once()

    def test_conflict_when_exists_409(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_database.return_value = {**_DB_BODY}
        client, _ = _make_client()

        response = client.post("/databases/mydb", json=_DB_BODY, headers=AUTH)

        assert response.status_code == 409


@pytest.mark.unit
class TestGetDatabase:
    def test_found_returns_200(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_database.return_value = {**_DB_BODY}
        client, _ = _make_client()

        response = client.get("/databases/mydb", headers=AUTH)

        assert response.status_code == 200
        assert response.json() == _DB_BODY

    def test_not_found_returns_404(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_database.return_value = None
        client, _ = _make_client()

        response = client.get("/databases/ghost", headers=AUTH)

        assert response.status_code == 404


@pytest.mark.unit
class TestPatchDatabase:
    def test_updates_fields(self, mocker):
        existing = {**_DB_BODY}
        updated = {**_DB_BODY, "host": "new.internal"}
        mgr = _mock_manager(mocker)
        mgr.get_database.side_effect = [existing, updated]
        client, _ = _make_client()

        response = client.patch("/databases/mydb", json={"host": "new.internal"}, headers=AUTH)

        assert response.status_code == 200
        mgr.add_database.assert_called_once()
        call_kwargs = mgr.add_database.call_args.kwargs
        assert call_kwargs["host"] == "new.internal"

    def test_not_found_returns_404(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.get_database.return_value = None
        client, _ = _make_client()

        response = client.patch("/databases/ghost", json={"host": "x.internal"}, headers=AUTH)

        assert response.status_code == 404


@pytest.mark.unit
class TestDeleteDatabase:
    def test_deletes_returns_204(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.remove_database.return_value = True
        client, _ = _make_client()

        response = client.delete("/databases/mydb", headers=AUTH)

        assert response.status_code == 204
        mgr.remove_database.assert_called_once_with("mydb")

    def test_not_found_returns_404(self, mocker):
        mgr = _mock_manager(mocker)
        mgr.remove_database.return_value = False
        client, _ = _make_client()

        response = client.delete("/databases/ghost", headers=AUTH)

        assert response.status_code == 404
