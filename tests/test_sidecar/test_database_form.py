"""What the Database form needs from the sidecar: listing RDS databases and renaming."""

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.connection_runner import ConnectionRecord, ForwarderRegistry
from cli_tool.core.utils.config_manager import save_config
from cli_tool.sidecar.routers.databases import router
from cli_tool.sidecar.services import database_discovery
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}


class FakeRds:
    def __init__(self, pages, fail=None):
        self.pages = pages
        self.fail = fail or {}

    def get_paginator(self, operation):
        rds = self

        class Paginator:
            def paginate(self):
                if operation in rds.fail:
                    raise rds.fail[operation]
                return rds.pages.get(operation, [])

        return Paginator()


@pytest.fixture
def rds(mocker):
    def _use(pages, fail=None):
        session = mocker.patch.object(database_discovery.boto3, "Session")
        session.return_value.client.return_value = FakeRds(pages, fail)
        return session

    return _use


CLUSTERS = [
    {
        "DBClusters": [
            {
                "DBClusterIdentifier": "nemt-qa",
                "DBClusterArn": "arn:cluster:nemt-qa",
                "Endpoint": "nemt-qa.cluster-abc.us-east-1.rds.amazonaws.com",
                "ReaderEndpoint": "nemt-qa.cluster-ro-abc.us-east-1.rds.amazonaws.com",
                "Port": 5432,
                "Engine": "aurora-postgresql",
            }
        ]
    }
]
INSTANCES = [
    {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "legacy",
                "Endpoint": {"Address": "legacy.abc.us-east-1.rds.amazonaws.com", "Port": 3306},
                "Engine": "mysql",
            },
            {"DBInstanceIdentifier": "creating", "Engine": "postgres"},  # no endpoint yet
        ]
    }
]
GLOBAL = [
    {
        "GlobalClusters": [
            {
                "GlobalClusterIdentifier": "epic-dev",
                "Endpoint": "epic-dev.global-xyz.global.rds.amazonaws.com",
                "Engine": "aurora-postgresql",
                "GlobalClusterMembers": [{"DBClusterArn": "arn:cluster:nemt-qa"}],
            }
        ]
    }
]


@pytest.mark.unit
class TestDiscovery:
    def test_lists_cluster_endpoints_instances_and_global_databases(self, rds):
        session = rds({"describe_db_clusters": CLUSTERS, "describe_db_instances": INSTANCES, "describe_global_clusters": GLOBAL})

        result = database_discovery.discover_databases("dev", "us-east-1")

        session.assert_called_once_with(profile_name="dev", region_name="us-east-1")
        assert result["error"] is None
        assert [(d["id"], d["kind"], d["port"]) for d in result["databases"]] == [
            ("epic-dev", "global", 5432),  # port from its member cluster
            ("legacy", "instance", 3306),
            ("nemt-qa", "reader", 5432),
            ("nemt-qa", "writer", 5432),
        ]

    def test_without_permissions_says_so_and_lets_the_host_be_typed(self, rds):
        denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "not authorized"}}, "DescribeDBClusters")
        rds({}, fail={"describe_db_clusters": denied})

        result = database_discovery.discover_databases("SSMBastionConnectDev", "us-east-1")

        assert result["databases"] == []
        assert "can't list RDS databases" in result["error"] and "Type the host" in result["error"]

    def test_an_expired_login_says_so(self, rds):
        rds({}, fail={"describe_db_clusters": NoCredentialsError()})

        result = database_discovery.discover_databases("dev", "us-east-1")

        assert result["databases"] == [] and "Log in to AWS" in result["error"]

    def test_global_databases_are_best_effort(self, rds):
        denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "DescribeGlobalClusters")
        rds({"describe_db_clusters": CLUSTERS, "describe_db_instances": INSTANCES}, fail={"describe_global_clusters": denied})

        result = database_discovery.discover_databases("dev", "us-east-1")

        assert result["error"] is None and len(result["databases"]) == 3


def _client():
    app = FastAPI()
    app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
    app.state.app_state = app_state
    app.include_router(router)
    return TestClient(app), app_state


def _db(**extra):
    return {"bastion": "i-1", "host": "a.rds", "port": 5432, "region": "us-east-1", "local_port": 5469, "local_address": "127.0.0.2", **extra}


@pytest.mark.unit
class TestEndpoints:
    def test_discover(self, mocker):
        discover = mocker.patch("cli_tool.sidecar.routers.databases.discover_databases", return_value={"databases": [], "error": None})

        response = _client()[0].get("/databases:discover", params={"region": "us-east-1", "profile": "dev"}, headers=AUTH)

        assert response.status_code == 200
        discover.assert_called_once_with("dev", "us-east-1")

    def test_rename_keeps_every_setting_and_its_place(self):
        save_config({"ssm": {"databases": {"first": _db(), "old": _db(hostname_forwarding=False), "last": _db()}}})

        response = _client()[0].patch("/databases/old", json={"name": "new", "port": 5433}, headers=AUTH)

        assert response.status_code == 200
        databases = SSMConfigManager().list_databases()
        assert list(databases) == ["first", "new", "last"]
        assert databases["new"] == _db(port=5433, profile=None, hostname_forwarding=False)

    def test_rename_onto_an_existing_name_is_a_conflict(self):
        save_config({"ssm": {"databases": {"a": _db(), "b": _db()}}})

        response = _client()[0].patch("/databases/a", json={"name": "b"}, headers=AUTH)

        assert response.status_code == 409
        assert list(SSMConfigManager().list_databases()) == ["a", "b"]

    def test_rename_while_its_tunnel_runs_is_refused(self):
        save_config({"ssm": {"databases": {"a": _db()}}})
        client, app_state = _client()
        record = ConnectionRecord(name="a")
        record.state = "connected"
        app_state.registry.register("a", record)

        response = client.patch("/databases/a", json={"name": "b"}, headers=AUTH)

        assert response.status_code == 409
        assert "Stop the connection" in response.json()["detail"]

    def test_rename_needs_a_valid_name(self):
        save_config({"ssm": {"databases": {"a": _db()}}})

        response = _client()[0].patch("/databases/a", json={"name": "bad name!"}, headers=AUTH)

        assert response.status_code == 422
