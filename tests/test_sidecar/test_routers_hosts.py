import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.routers.hosts import router
from cli_tool.sidecar.services.hosts_service import NeedsElevation
from cli_tool.sidecar.state import AppState, EventHub


def _make_client():
    app = FastAPI()
    app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
    app.state.app_state = app_state
    app.include_router(router)
    return TestClient(app), app_state


AUTH = {"Authorization": "Bearer test-token"}


@pytest.mark.unit
class TestGetHosts:
    def test_returns_list(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.hosts.list_hosts",
            return_value=[{"ip": "127.0.0.1", "hostname": "db"}],
        )
        client, _ = _make_client()
        response = client.get("/hosts", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == [{"ip": "127.0.0.1", "hostname": "db"}]


@pytest.mark.unit
class TestCreateHost:
    def test_creates_201(self, mocker):
        mocker.patch("cli_tool.sidecar.routers.hosts.add_host", return_value=None)
        client, _ = _make_client()
        response = client.post("/hosts", json={"ip": "10.0.0.1", "hostname": "mydb"}, headers=AUTH)
        assert response.status_code == 201
        assert response.json() == {"ip": "10.0.0.1", "hostname": "mydb"}

    def test_needs_elevation_returns_401(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.hosts.add_host",
            side_effect=NeedsElevation("sudo devo ssm hosts add 10.0.0.1 mydb"),
        )
        client, _ = _make_client()
        response = client.post("/hosts", json={"ip": "10.0.0.1", "hostname": "mydb"}, headers=AUTH)
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert "command" in detail
        assert detail["command"] == "sudo devo ssm hosts add 10.0.0.1 mydb"


@pytest.mark.unit
class TestDeleteHost:
    def test_deletes_204(self, mocker):
        mocker.patch("cli_tool.sidecar.routers.hosts.remove_host", return_value=None)
        client, _ = _make_client()
        response = client.delete("/hosts/mydb", headers=AUTH)
        assert response.status_code == 204

    def test_needs_elevation_returns_401(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.hosts.remove_host",
            side_effect=NeedsElevation("sudo devo ssm hosts remove mydb"),
        )
        client, _ = _make_client()
        response = client.delete("/hosts/mydb", headers=AUTH)
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert "command" in detail
        assert detail["command"] == "sudo devo ssm hosts remove mydb"


@pytest.mark.unit
class TestSetupHosts:
    def test_setup_returns_results(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.hosts.setup_hosts",
            return_value={
                "succeeded": [{"name": "db1", "host": "db1.example.com", "ip": "127.0.0.2", "local_port": 15432, "port_reassigned": False}],
                "failed": [],
            },
        )
        client, _ = _make_client()
        response = client.post("/hosts/setup", json={}, headers=AUTH)
        assert response.status_code == 200
        body = response.json()
        assert len(body["succeeded"]) == 1
        assert body["failed"] == []

    def test_setup_no_body(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.hosts.setup_hosts",
            return_value={"succeeded": [], "failed": []},
        )
        client, _ = _make_client()
        response = client.post("/hosts/setup", headers=AUTH)
        assert response.status_code == 200

    def test_setup_needs_elevation_returns_401(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.hosts.setup_hosts",
            side_effect=NeedsElevation("sudo devo ssm hosts setup"),
        )
        client, _ = _make_client()
        response = client.post("/hosts/setup", json={}, headers=AUTH)
        assert response.status_code == 401
        detail = response.json()["detail"]
        assert detail["command"] == "sudo devo ssm hosts setup"
