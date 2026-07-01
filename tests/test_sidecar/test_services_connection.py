"""Unit tests for cli_tool.sidecar.services.connection_service."""

from unittest.mock import MagicMock, patch

import pytest

from cli_tool.commands.ssm.core.connection_runner import ConnectionRecord, ForwarderRegistry
from cli_tool.sidecar.services import connection_service
from cli_tool.sidecar.state import EventHub


def _make_registry(records: dict[str, ConnectionRecord] | None = None) -> ForwarderRegistry:
    reg = ForwarderRegistry()
    for name, rec in (records or {}).items():
        reg.register(name, rec)
    return reg


def _db_config(name: str = "mydb", **overrides) -> dict:
    base = {
        "bastion": "bastion-1",
        "host": "db.example.com",
        "port": 5432,
        "region": "us-east-1",
        "local_address": "127.0.0.1",
    }
    base.update(overrides)
    return base


@pytest.mark.unit
class TestListConnections:
    def test_empty_registry_returns_empty_list(self):
        reg = _make_registry()
        assert connection_service.list_connections(reg) == []

    def test_returns_one_row_per_record(self):
        rec1 = ConnectionRecord(name="a", local_port=15432)
        rec1.state = "connected"
        rec2 = ConnectionRecord(name="b", local_port=15433)
        rec2.state = "starting"
        reg = _make_registry({"a": rec1, "b": rec2})

        out = connection_service.list_connections(reg)
        assert out == [
            {"name": "a", "state": "connected", "local_port": 15432, "error": None},
            {"name": "b", "state": "starting", "local_port": 15433, "error": None},
        ]

    def test_propagates_error_field(self):
        rec = ConnectionRecord(name="x", local_port=15432)
        rec.error = "boom"
        reg = _make_registry({"x": rec})
        out = connection_service.list_connections(reg)
        assert out[0]["error"] == "boom"


@pytest.mark.unit
class TestStopConnection:
    def test_stop_connection_invokes_registry(self):
        rec = ConnectionRecord(name="x", local_port=15432)
        rec.stop_event = MagicMock()
        reg = _make_registry({"x": rec})

        connection_service.stop_connection("x", reg)
        rec.stop_event.set.assert_called_once()

    def test_stop_connection_for_unknown_name_is_noop(self):
        reg = _make_registry()
        # Should not raise
        connection_service.stop_connection("missing", reg)


@pytest.mark.unit
class TestStopAllConnections:
    def test_stop_all_sets_global_event_and_stops_each(self):
        rec_a = ConnectionRecord(name="a", local_port=15432)
        rec_b = ConnectionRecord(name="b", local_port=15433)
        rec_a.stop_event = MagicMock()
        rec_b.stop_event = MagicMock()
        reg = _make_registry({"a": rec_a, "b": rec_b})

        connection_service.stop_all_connections(reg)
        assert reg.stop_event.is_set()
        rec_a.stop_event.set.assert_called()
        rec_b.stop_event.set.assert_called()


@pytest.mark.unit
class TestStartConnection:
    def test_raises_keyerror_for_unknown_db(self, mocker):
        mock_cfg = MagicMock()
        mock_cfg.get_database.return_value = None
        mocker.patch.object(connection_service, "SSMConfigManager", return_value=mock_cfg)

        hub = EventHub()
        reg = _make_registry()
        with pytest.raises(KeyError, match="not configured"):
            connection_service.start_connection("nope", reg, hub)

    def test_raises_value_error_if_already_active(self, mocker):
        existing = ConnectionRecord(name="mydb", local_port=15432)
        existing.state = "connected"
        reg = _make_registry({"mydb": existing})

        with pytest.raises(ValueError, match="already active"):
            connection_service.start_connection("mydb", reg, EventHub())

    def test_raises_if_already_active_even_in_starting(self, mocker):
        existing = ConnectionRecord(name="mydb", local_port=15432)
        existing.state = "starting"
        reg = _make_registry({"mydb": existing})

        with pytest.raises(ValueError, match="already active"):
            connection_service.start_connection("mydb", reg, EventHub())

    def test_allows_restart_from_stopped(self, mocker):
        rec = ConnectionRecord(name="mydb", local_port=15432)
        rec.state = "stopped"
        reg = _make_registry({"mydb": rec})

        mock_cfg = MagicMock()
        mock_cfg.get_database.return_value = _db_config("mydb")
        mocker.patch.object(connection_service, "SSMConfigManager", return_value=mock_cfg)
        mocker.patch.object(connection_service, "HostsManager")
        # Patch _find_free_port to return a deterministic port
        mocker.patch.object(connection_service, "_find_free_port", return_value=15432)
        # Patch the connection loop so no real SSM session starts
        mocker.patch.object(connection_service, "_run_connection_loop")

        hub = EventHub()
        result = connection_service.start_connection("mydb", reg, hub)
        assert result["name"] == "mydb"
        assert result["state"] == "starting"
        assert result["local_port"] == 15432

    def test_raises_when_hostname_forwarding_host_missing(self, mocker):
        rec = ConnectionRecord(name="mydb", local_port=15432)
        rec.state = "stopped"
        reg = _make_registry({"mydb": rec})

        mock_cfg = MagicMock()
        # local_address != 127.0.0.1 → triggers hostname forwarding check
        mock_cfg.get_database.return_value = _db_config("mydb", local_address="db.example.com")
        mocker.patch.object(connection_service, "SSMConfigManager", return_value=mock_cfg)
        mock_hosts = MagicMock()
        mock_hosts.get_managed_entries.return_value = []  # host not managed
        mocker.patch.object(connection_service, "HostsManager", return_value=mock_hosts)

        with pytest.raises(ValueError, match="not in /etc/hosts"):
            connection_service.start_connection("mydb", reg, EventHub())

    def test_registers_observer_first_time(self, mocker):
        rec = ConnectionRecord(name="mydb", local_port=15432)
        rec.state = "stopped"
        reg = _make_registry({"mydb": rec})

        mock_cfg = MagicMock()
        mock_cfg.get_database.return_value = _db_config("mydb")
        mocker.patch.object(connection_service, "SSMConfigManager", return_value=mock_cfg)
        mocker.patch.object(connection_service, "HostsManager")
        mocker.patch.object(connection_service, "_find_free_port", return_value=15432)
        mocker.patch.object(connection_service, "_run_connection_loop")

        assert not reg._observers
        connection_service.start_connection("mydb", reg, EventHub())
        assert len(reg._observers) == 1

    def test_does_not_register_second_observer(self, mocker):
        rec = ConnectionRecord(name="mydb", local_port=15432)
        rec.state = "stopped"
        reg = _make_registry({"mydb": rec})

        mock_cfg = MagicMock()
        mock_cfg.get_database.return_value = _db_config("mydb")
        mocker.patch.object(connection_service, "SSMConfigManager", return_value=mock_cfg)
        mocker.patch.object(connection_service, "HostsManager")
        mocker.patch.object(connection_service, "_find_free_port", return_value=15432)
        mocker.patch.object(connection_service, "_run_connection_loop")

        # Pre-register an observer to simulate "second start"
        reg.add_observer(lambda *_: None)
        before = len(reg._observers)
        connection_service.start_connection("mydb", reg, EventHub())
        assert len(reg._observers) == before  # unchanged


@pytest.mark.unit
class TestStartAllConnections:
    def test_starts_every_database_in_config(self, mocker):
        mock_cfg = MagicMock()
        mock_cfg.list_databases.return_value = ["a", "b", "c"]
        mock_cfg.get_database.side_effect = lambda n: _db_config(n)
        mocker.patch.object(connection_service, "SSMConfigManager", return_value=mock_cfg)
        mocker.patch.object(connection_service, "HostsManager")
        mocker.patch.object(connection_service, "_find_free_port", return_value=15432)
        mocker.patch.object(connection_service, "_run_connection_loop")

        reg = _make_registry()
        results = connection_service.start_all_connections(reg, EventHub())

        assert len(results) == 3
        assert {r["name"] for r in results} == {"a", "b", "c"}
        assert all(r["state"] == "starting" for r in results)

    def test_continues_after_failure(self, mocker):
        mock_cfg = MagicMock()
        mock_cfg.list_databases.return_value = ["ok", "bad"]

        # First db succeeds, second raises KeyError
        def fake_get(name):
            if name == "ok":
                return _db_config("ok")
            return None

        mock_cfg.get_database.side_effect = fake_get
        mocker.patch.object(connection_service, "SSMConfigManager", return_value=mock_cfg)
        mocker.patch.object(connection_service, "HostsManager")
        mocker.patch.object(connection_service, "_find_free_port", return_value=15432)
        mocker.patch.object(connection_service, "_run_connection_loop")

        reg = _make_registry()
        results = connection_service.start_all_connections(reg, EventHub())

        # ok should be in results (started); bad should appear with error
        names_states = {r["name"]: r.get("state") for r in results}
        assert names_states["ok"] == "starting"
        assert names_states["bad"] == "error"
        assert "not configured" in next(r for r in results if r["name"] == "bad")["error"]
