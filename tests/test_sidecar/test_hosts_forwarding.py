"""Pausing hostname forwarding, for every database or for one (sidecar side)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.commands.ssm.utils import HostsManager
from cli_tool.core.utils.config_manager import load_config, save_config
from cli_tool.sidecar.routers.databases import router as databases_router
from cli_tool.sidecar.routers.hosts import router as hosts_router
from cli_tool.sidecar.services import connection_service, hosts_service
from cli_tool.sidecar.services.hosts_service import NeedsElevation
from cli_tool.sidecar.state import AppState, EventHub

MARKER_START = HostsManager.MARKER_START
MARKER_END = HostsManager.MARKER_END
AUTH = {"Authorization": "Bearer test-token"}


def _db(host, local_address, **extra):
    return {"bastion": "i-1", "host": host, "port": 5432, "region": "us-east-1", "local_address": local_address, "local_port": 5432, **extra}


def _hosts(*entries):
    return "\n".join([MARKER_START, *(f"{ip} {host}" for ip, host in entries), MARKER_END]) + "\n"


class FakeHostsFile:
    """The hosts file in a tmp dir; `writable = False` makes writes fail as
    they do without admin rights."""

    def __init__(self, tmp_path, mocker):
        self.path = tmp_path / "hosts"
        self.path.write_text("127.0.0.1 localhost\n")
        self.writable = True
        mocker.patch.object(HostsManager, "get_hosts_file_path", staticmethod(lambda: self.path))
        mocker.patch.object(HostsManager, "_write_hosts", lambda _self, content: self._write(content))

    def _write(self, content):
        if not self.writable:
            raise PermissionError("Permission denied. Needs elevation.")
        self.path.write_text(content)

    def entries(self):
        return HostsManager().get_managed_entries()


@pytest.fixture
def hosts(tmp_path, mocker):
    mocker.patch("platform.system", return_value="Linux")  # no macOS loopback aliases
    mocker.patch("cli_tool.commands.ssm.core.hosts_setup._find_free_port", side_effect=lambda port: port)
    return FakeHostsFile(tmp_path, mocker)


@pytest.fixture
def two_dbs(hosts):
    save_config({"ssm": {"databases": {"a": _db("a.rds", "127.0.0.2"), "b": _db("b.rds", "127.0.0.3")}}})
    hosts.path.write_text("127.0.0.1 localhost\n" + _hosts(("127.0.0.2", "a.rds"), ("127.0.0.3", "b.rds")))


@pytest.mark.unit
class TestStatus:
    def test_reports_each_database_without_writing(self, hosts, two_dbs, mocker):
        write = mocker.patch.object(HostsManager, "_write_hosts")
        hosts.path.write_text(_hosts(("127.0.0.2", "a.rds")))

        status = hosts_service.hosts_status()

        write.assert_not_called()
        assert status["enabled"] is True
        assert status["databases"]["a"] == {"enabled": True, "mapped": True}
        assert status["databases"]["b"] == {"enabled": True, "mapped": False}
        assert status["missing"] == ["b"]

    def test_paused_databases_are_never_missing(self, hosts, two_dbs):
        hosts.path.write_text("")
        SSMConfigManager().set_hostname_forwarding(False, "a")

        assert hosts_service.hosts_status()["missing"] == ["b"]

        SSMConfigManager().set_hostname_forwarding(False)
        status = hosts_service.hosts_status()

        assert status["missing"] == []
        assert status["enabled"] is False
        assert status["databases"]["b"] == {"enabled": False, "mapped": False}

    def test_an_entry_with_a_stale_ip_is_not_mapped(self, hosts, two_dbs):
        hosts.path.write_text(_hosts(("127.0.0.9", "a.rds"), ("127.0.0.3", "b.rds")))

        assert hosts_service.hosts_status()["missing"] == ["a"]


@pytest.mark.unit
class TestPauseAll:
    def test_pausing_removes_every_devo_entry_and_keeps_the_rest(self, hosts, two_dbs):
        status = hosts_service.set_forwarding(False)

        assert hosts.entries() == []
        assert "127.0.0.1 localhost" in hosts.path.read_text()
        assert status["enabled"] is False
        assert load_config()["ssm"]["hostname_forwarding"] is False

    def test_resuming_maps_every_database(self, hosts, two_dbs):
        hosts_service.set_forwarding(False)

        status = hosts_service.set_forwarding(True)

        assert hosts.entries() == [("127.0.0.2", "a.rds"), ("127.0.0.3", "b.rds")]
        assert status["enabled"] is True and status["missing"] == []

    def test_all_means_all_exceptions_included(self, hosts, two_dbs):
        hosts_service.set_database_forwarding("b", False)

        hosts_service.set_forwarding(False)
        hosts_service.set_database_forwarding("a", True)  # one forwarded while the rest is paused
        status = hosts_service.set_forwarding(True)

        assert all(d["enabled"] for d in status["databases"].values())
        assert all("hostname_forwarding" not in db for db in SSMConfigManager().list_databases().values())

    def test_pausing_without_rights_asks_for_elevation_and_changes_nothing(self, hosts, two_dbs):
        hosts.writable = False

        with pytest.raises(NeedsElevation) as exc:
            hosts_service.set_forwarding(False)

        assert exc.value.action == "hosts-clear"
        cli_args = exc.value.params["cli_args"]
        assert cli_args[:2] == ["ssm", "hosts"] and cli_args[-2:] == ["clear", "--yes"]
        # it runs in a hidden window: its outcome goes to sidecar.log
        assert cli_args[2] == "--log-file" and cli_args[3].endswith("sidecar.log")
        assert "hostname_forwarding" not in load_config()["ssm"]  # still on

    def test_after_the_elevated_command_the_retry_just_records_it(self, hosts, two_dbs):
        hosts.writable = False
        hosts.path.write_text("127.0.0.1 localhost\n")  # what `devo ssm hosts clear` left

        status = hosts_service.set_forwarding(False)

        assert status["enabled"] is False

    def test_resuming_without_rights_records_it_so_the_sync_banner_can_finish(self, hosts, two_dbs):
        """If the user cancels the admin prompt, the databases show up as
        missing and "Sync Hosts" finishes the job."""
        hosts_service.set_forwarding(False)
        hosts.writable = False

        with pytest.raises(NeedsElevation) as exc:
            hosts_service.set_forwarding(True)

        assert exc.value.params["cli_args"][-3:] == ["setup", "a", "b"]
        assert hosts_service.hosts_status()["missing"] == ["a", "b"]


@pytest.mark.unit
class TestPauseOne:
    def test_pausing_one_removes_only_its_entry(self, hosts, two_dbs):
        status = hosts_service.set_database_forwarding("a", False)

        assert hosts.entries() == [("127.0.0.3", "b.rds")]
        assert status["databases"]["a"]["enabled"] is False
        assert status["missing"] == []

    def test_resuming_one_maps_it_again(self, hosts, two_dbs):
        hosts_service.set_database_forwarding("a", False)

        status = hosts_service.set_database_forwarding("a", True)

        assert ("127.0.0.2", "a.rds") in hosts.entries()
        assert status["databases"]["a"] == {"enabled": True, "mapped": True}

    def test_an_entry_shared_with_a_forwarded_database_stays(self, hosts):
        save_config({"ssm": {"databases": {"a": _db("same.rds", "127.0.0.2"), "a-ro": _db("same.rds", "127.0.0.2")}}})
        hosts.path.write_text(_hosts(("127.0.0.2", "same.rds")))

        hosts_service.set_database_forwarding("a", False)

        assert hosts.entries() == [("127.0.0.2", "same.rds")]

    def test_with_everything_paused_one_can_be_forwarded(self, hosts, two_dbs):
        """Nothing in the hosts file, then just this one: it is mapped right away."""
        hosts_service.set_forwarding(False)

        status = hosts_service.set_database_forwarding("b", True)

        assert hosts.entries() == [("127.0.0.3", "b.rds")]
        assert status["enabled"] is False
        assert status["databases"]["a"]["enabled"] is False
        assert status["databases"]["b"] == {"enabled": True, "mapped": True}
        assert status["missing"] == []

        status = hosts_service.set_database_forwarding("b", False)  # and paused again

        assert hosts.entries() == []
        assert "hostname_forwarding" not in SSMConfigManager().get_database("b")  # back to following all

    def test_pausing_without_rights_removes_just_that_hostname_elevated(self, hosts, two_dbs):
        hosts.writable = False

        with pytest.raises(NeedsElevation) as exc:
            hosts_service.set_database_forwarding("a", False)

        assert exc.value.params["cli_args"][-2:] == ["remove-manual", "a.rds"]
        assert "hostname_forwarding" not in SSMConfigManager().get_database("a")

    def test_unknown_database(self, hosts, two_dbs):
        with pytest.raises(KeyError):
            hosts_service.set_database_forwarding("nope", False)


def _client(router):
    app = FastAPI()
    app.state.app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
    app.include_router(router)
    return TestClient(app)


@pytest.mark.unit
class TestEndpoints:
    def test_status(self, mocker):
        mocker.patch("cli_tool.sidecar.routers.hosts.hosts_status", return_value={"enabled": True, "databases": {}, "missing": []})

        response = _client(hosts_router).get("/hosts/status", headers=AUTH)

        assert response.status_code == 200
        assert response.json()["enabled"] is True

    def test_pause_all(self, mocker):
        set_forwarding = mocker.patch("cli_tool.sidecar.routers.hosts.set_forwarding", return_value={"enabled": False})

        response = _client(hosts_router).put("/hosts/forwarding", json={"enabled": False}, headers=AUTH)

        assert response.status_code == 200
        set_forwarding.assert_called_once_with(False)

    def test_pause_one(self, mocker):
        set_one = mocker.patch("cli_tool.sidecar.routers.hosts.set_database_forwarding", return_value={"enabled": True})

        response = _client(hosts_router).put("/hosts/forwarding/a", json={"enabled": False}, headers=AUTH)

        assert response.status_code == 200
        set_one.assert_called_once_with("a", False)

    def test_needs_elevation_is_a_403_with_the_command_to_run(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.hosts.set_forwarding",
            side_effect=NeedsElevation("cmd", action="hosts-clear", params={"cli_args": ["ssm", "hosts", "clear", "--yes"]}),
        )

        response = _client(hosts_router).put("/hosts/forwarding", json={"enabled": False}, headers=AUTH)

        assert response.status_code == 403
        assert response.json()["detail"]["params"]["cli_args"] == ["ssm", "hosts", "clear", "--yes"]

    def test_lock_reason(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.hosts_service.describe_hosts_lock",
            return_value="Kaspersky is blocking changes to your hosts file",
        )

        response = _client(hosts_router).get("/hosts/lock-reason", headers=AUTH)

        assert response.status_code == 200
        assert response.json() == {"message": "Kaspersky is blocking changes to your hosts file"}

    def test_unknown_database_is_a_404(self, mocker):
        mocker.patch("cli_tool.sidecar.routers.hosts.set_database_forwarding", side_effect=KeyError("nope"))

        response = _client(hosts_router).put("/hosts/forwarding/nope", json={"enabled": False}, headers=AUTH)

        assert response.status_code == 404

    def test_editing_a_database_keeps_its_paused_switch(self, hosts):
        save_config({"ssm": {"databases": {"a": _db("a.rds", "127.0.0.2", hostname_forwarding=False)}}})

        response = _client(databases_router).patch("/databases/a", json={"port": 5433}, headers=AUTH)

        assert response.status_code == 200
        assert response.json()["hostname_forwarding"] is False


@pytest.mark.unit
class TestTunnelsWhilePaused:
    @pytest.fixture
    def start(self, hosts, mocker):
        mocker.patch("cli_tool.commands.ssm.core.session.SSMSession._is_token_expired", return_value=False)
        thread = mocker.patch.object(connection_service.threading, "Thread")
        mocker.patch.object(connection_service, "_find_free_port", side_effect=lambda port: port)

        def _start(name):
            return connection_service.start_connection(name, ForwarderRegistry(), EventHub())

        return _start, thread

    def test_a_paused_database_opens_its_tunnel_on_127_0_0_1(self, start):
        """Its hostname is out of the hosts file on purpose: no "run hosts setup first"."""
        start_connection, thread = start
        save_config({"ssm": {"databases": {"a": _db("a.rds", "127.0.0.2", hostname_forwarding=False)}}})

        info = start_connection("a")

        assert info["state"] == "starting"
        use_hostname_forwarding = thread.call_args.kwargs["args"][3]
        assert use_hostname_forwarding is False

    def test_a_forwarded_database_without_its_entry_still_asks_for_setup(self, start):
        start_connection, _thread = start
        save_config({"ssm": {"databases": {"a": _db("a.rds", "127.0.0.2")}}})

        with pytest.raises(ValueError, match="hosts setup"):
            start_connection("a")


@pytest.mark.unit
class TestStaleEntriesAndSync:
    def test_status_lists_hostnames_no_forwarded_database_uses(self, hosts, two_dbs):
        hosts.path.write_text(_hosts(("127.0.0.2", "a.rds"), ("127.0.0.3", "b.rds"), ("127.0.0.9", "deleted.rds")))
        SSMConfigManager().set_hostname_forwarding(False, "b")

        assert hosts_service.hosts_status()["stale"] == ["b.rds", "deleted.rds"]

    def test_sync_maps_the_missing_and_removes_the_stale(self, hosts, two_dbs):
        hosts.path.write_text(_hosts(("127.0.0.2", "a.rds"), ("127.0.0.9", "deleted.rds")))

        status = hosts_service.sync_hosts()

        assert hosts.entries() == [("127.0.0.2", "a.rds"), ("127.0.0.3", "b.rds")]
        assert status["missing"] == [] and status["stale"] == []

    def test_sync_without_rights_asks_to_run_hosts_sync_elevated(self, hosts, two_dbs):
        hosts.path.write_text(_hosts(("127.0.0.9", "deleted.rds")))
        hosts.writable = False

        with pytest.raises(NeedsElevation) as exc:
            hosts_service.sync_hosts()

        assert exc.value.action == "hosts-sync"
        assert exc.value.params["cli_args"][-1] == "sync"

    def test_endpoint(self, mocker):
        sync = mocker.patch("cli_tool.sidecar.routers.hosts.sync_hosts", return_value={"missing": [], "stale": []})

        response = _client(hosts_router).post("/hosts/sync", headers=AUTH)

        assert response.status_code == 200
        sync.assert_called_once_with()
