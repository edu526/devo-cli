"""Unit tests for the audit log service and router."""

import asyncio
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.services import audit_service
from cli_tool.sidecar.state import AppState, EventHub

AUTH = {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# Service: log_event + read_recent + prune
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHashToken:
    def test_returns_dash_for_none(self):
        assert audit_service._hash_token(None) == "-"

    def test_returns_dash_for_empty(self):
        assert audit_service._hash_token("") == "-"

    def test_returns_16_char_hex(self):
        h = audit_service._hash_token("abc123")
        assert len(h) == 16
        int(h, 16)  # raises if not hex

    def test_deterministic(self):
        assert audit_service._hash_token("x") == audit_service._hash_token("x")

    def test_different_tokens_differ(self):
        assert audit_service._hash_token("a") != audit_service._hash_token("b")


@pytest.mark.unit
class TestCurrentLogPath:
    def test_path_includes_iso_date(self, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", Path("/tmp"))
        path = audit_service._current_log_path(date(2026, 6, 12))
        assert path == Path("/tmp/audit-2026-06-12.log")


@pytest.mark.unit
class TestPruneOldLogs:
    def test_removes_files_older_than_retention(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        # Create three files: 10 days, 40 days, 100 days old
        today = date(2026, 6, 12)
        for delta, label in [(10, "keep"), (40, "remove1"), (100, "remove2")]:
            (tmp_path / f"audit-{(today - timedelta(days=delta)).isoformat()}.log").write_text("x")

        removed = audit_service.prune_old_logs(now=today)
        assert removed == 2
        remaining = {p.name for p in tmp_path.glob("audit-*.log")}
        assert "audit-2026-06-02.log" in remaining
        assert "audit-2026-05-03.log" not in remaining
        assert "audit-2026-03-04.log" not in remaining

    def test_returns_zero_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path / "missing")
        assert audit_service.prune_old_logs() == 0

    def test_skips_malformed_filenames(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        (tmp_path / "audit-not-a-date.log").write_text("x")
        # Should not raise
        assert audit_service.prune_old_logs() == 0


@pytest.mark.unit
class TestLogEvent:
    def test_writes_jsonl_to_dated_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        target = tmp_path / "audit-2026-06-12.log"
        audit_service.log_event(
            method="GET",
            path="/api/v1/profiles",
            status_code=200,
            client_ip="127.0.0.1",
            token="secret",
            duration_ms=12.3,
            log_path=target,
        )
        content = target.read_text(encoding="utf-8")
        record = json.loads(content.strip())
        assert record["method"] == "GET"
        assert record["path"] == "/api/v1/profiles"
        assert record["status"] == 200
        assert record["ip"] == "127.0.0.1"
        assert record["token"] == audit_service._hash_token("secret")
        assert record["duration_ms"] == 12.3
        assert "ts" in record

    def test_token_is_hashed_not_plaintext(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        target = tmp_path / "audit-2026-06-12.log"
        audit_service.log_event(
            method="GET",
            path="/x",
            status_code=200,
            client_ip="127.0.0.1",
            token="super-secret-bearer",
            duration_ms=1.0,
            log_path=target,
        )
        content = target.read_text(encoding="utf-8")
        assert "super-secret-bearer" not in content

    def test_missing_token_yields_dash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        target = tmp_path / "audit-2026-06-12.log"
        audit_service.log_event(
            method="GET",
            path="/x",
            status_code=200,
            client_ip="127.0.0.1",
            token=None,
            duration_ms=1.0,
            log_path=target,
        )
        rec = json.loads(target.read_text(encoding="utf-8").strip())
        assert rec["token"] == "-"


@pytest.mark.unit
class TestReadRecent:
    def test_returns_records_newest_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        target = tmp_path / "audit-2026-06-12.log"
        for i in range(3):
            audit_service.log_event(
                method="GET",
                path=f"/x/{i}",
                status_code=200,
                client_ip="127.0.0.1",
                token=None,
                duration_ms=1.0,
                log_path=target,
            )
        out = audit_service.read_recent(limit=10)
        assert len(out) == 3
        # Latest is x/2
        assert out[0]["path"] == "/x/2"
        assert out[-1]["path"] == "/x/0"

    def test_limit_caps_results(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        target = tmp_path / "audit-2026-06-12.log"
        for i in range(5):
            audit_service.log_event(
                method="GET",
                path=f"/x/{i}",
                status_code=200,
                client_ip="127.0.0.1",
                token=None,
                duration_ms=1.0,
                log_path=target,
            )
        out = audit_service.read_recent(limit=2)
        assert len(out) == 2

    def test_since_filters_by_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        target = tmp_path / "audit-2026-06-12.log"
        for i in range(3):
            audit_service.log_event(
                method="GET",
                path=f"/x/{i}",
                status_code=200,
                client_ip="127.0.0.1",
                token=None,
                duration_ms=1.0,
                log_path=target,
            )
            time.sleep(0.005)
        # Skip the first record by cutting off at the timestamp of the second
        records = []
        with target.open("r", encoding="utf-8") as f:
            for line in f:
                records.append(json.loads(line))
        since = datetime.fromisoformat(records[1]["ts"])
        out = audit_service.read_recent(since=since, limit=10)
        assert len(out) == 2
        assert all(datetime.fromisoformat(r["ts"]) >= since for r in out)

    def test_returns_empty_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path / "missing")
        assert audit_service.read_recent() == []


# ---------------------------------------------------------------------------
# Router: /api/v1/audit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuditRouter:
    def test_list_returns_records(self, mocker, tmp_path, monkeypatch):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        target = tmp_path / "audit-2026-06-12.log"
        audit_service.log_event(
            method="GET",
            path="/api/v1/profiles",
            status_code=200,
            client_ip="127.0.0.1",
            token="test-token",
            duration_ms=1.0,
            log_path=target,
        )

        app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get("/api/v1/audit", headers=AUTH)
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["path"] == "/api/v1/profiles"
        assert body[0]["token"] == audit_service._hash_token("test-token")

    def test_requires_bearer(self, mocker, tmp_path, monkeypatch):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get("/api/v1/audit")
        assert response.status_code == 401

    def test_invalid_since_returns_400(self, mocker, tmp_path, monkeypatch):
        async def _noop_watch(*_args, **_kwargs):
            await asyncio.sleep(9999)

        mocker.patch("cli_tool.sidecar.app.watch_profiles", side_effect=_noop_watch)
        mocker.patch("cli_tool.sidecar.app.start_config_watcher", return_value=MagicMock())

        monkeypatch.setattr(audit_service, "AUDIT_LOG_DIR", tmp_path)
        app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
        app = create_app(app_state)
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/audit?since=not-a-date",
                headers=AUTH,
            )
        assert response.status_code == 400
