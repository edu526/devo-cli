"""Tests for /api/v1/codeartifact sidecar router."""

import base64
import json
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.routers.codeartifact import router
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


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fake-sig"


# ── GET /domains ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestListDomains:
    def test_returns_enriched_domains(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.get_domains",
            return_value=[
                {"domain": "d1", "repository": "r1", "namespace": "@x", "account_id": "111", "profile": "", "region": "us-east-1"},
            ],
        )
        client, _ = _make_client()
        response = client.get("/codeartifact/domains", headers=AUTH)
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["domain"] == "d1"


# ── POST /domains ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCreateDomain:
    def test_creates_domain(self, mocker):
        mock_create = mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.create_domain",
            return_value={"domain": "new", "repository": "r", "namespace": "", "account_id": "", "profile": "", "region": "us-east-1"},
        )
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/domains",
            json={"domain": "new", "repository": "r"},
            headers=AUTH,
        )
        assert response.status_code == 201
        mock_create.assert_called_once()

    def test_422_on_missing_required(self, mocker):
        mock_create = mocker.patch("cli_tool.sidecar.routers.codeartifact.create_domain")
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/domains",
            json={"domain": "x"},
            headers=AUTH,
        )
        assert response.status_code == 422
        mock_create.assert_not_called()

    def test_409_on_duplicate(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.create_domain",
            side_effect=ValueError("Domain 'x' already exists"),
        )
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/domains",
            json={"domain": "x", "repository": "r"},
            headers=AUTH,
        )
        assert response.status_code == 409


# ── PATCH /domains/{domain} ───────────────────────────────────────────────────


@pytest.mark.unit
class TestUpdateDomain:
    def test_updates_domain(self, mocker):
        mock_update = mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.update_domain",
            return_value={"domain": "d1", "repository": "r1", "namespace": "@x", "account_id": "111", "profile": "p1", "region": "us-east-1"},
        )
        client, _ = _make_client()
        response = client.patch(
            "/codeartifact/domains/d1",
            json={"profile": "p1"},
            headers=AUTH,
        )
        assert response.status_code == 200
        assert response.json()["profile"] == "p1"
        mock_update.assert_called_once_with("d1", {"profile": "p1"})

    def test_404_when_not_found(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.update_domain",
            side_effect=ValueError("Domain 'd1' not found"),
        )
        client, _ = _make_client()
        response = client.patch(
            "/codeartifact/domains/d1",
            json={"profile": "p1"},
            headers=AUTH,
        )
        assert response.status_code == 404


# ── DELETE /domains/{domain} ──────────────────────────────────────────────────


@pytest.mark.unit
class TestDeleteDomain:
    def test_deletes_domain(self, mocker):
        mock_delete = mocker.patch("cli_tool.sidecar.routers.codeartifact.delete_domain")
        client, _ = _make_client()
        response = client.delete("/codeartifact/domains/d1", headers=AUTH)
        assert response.status_code == 204
        mock_delete.assert_called_once_with("d1")

    def test_404_when_not_found(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.delete_domain",
            side_effect=ValueError("Domain 'd1' not found"),
        )
        client, _ = _make_client()
        response = client.delete("/codeartifact/domains/d1", headers=AUTH)
        assert response.status_code == 404


# ── GET /tokens ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestListTokens:
    def test_returns_empty_when_no_files(self, mocker, tmp_path):
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        client, _ = _make_client()
        response = client.get("/codeartifact/tokens", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == []

    def test_parses_npmrc_token(self, mocker, tmp_path):
        exp = int(time.time()) + 3600
        token = _make_jwt(exp)
        npmrc = tmp_path / ".npmrc"
        npmrc.write_text(
            f"@mycompany:registry=https://mycompany-123.d.codeartifact.us-east-1.amazonaws.com/npm/mycompany-ui-kit/\n"
            f"//mycompany-123.d.codeartifact.us-east-1.amazonaws.com/npm/mycompany-ui-kit/:_authToken={token}\n"
        )
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        client, _ = _make_client()
        response = client.get("/codeartifact/tokens", headers=AUTH)
        body = response.json()
        assert len(body) == 1
        t = body[0]
        assert t["domain"] == "mycompany"
        assert t["repository"] == "mycompany-ui-kit"
        assert t["account_id"] == "123"
        assert t["region"] == "us-east-1"
        assert t["tool"] == "npm"
        assert t["expires_at"] is not None

    def test_parses_pip_conf_token(self, mocker, tmp_path):
        exp = int(time.time()) + 3600
        token = _make_jwt(exp)
        pip_dir = tmp_path / ".pip"
        pip_dir.mkdir()
        (pip_dir / "pip.conf").write_text(
            "[global]\n" f"index-url = https://aws:{token}@mycompany-123.d.codeartifact.us-east-1.amazonaws.com/pypi/mycompany-ui-kit/simple/\n"
        )
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        client, _ = _make_client()
        response = client.get("/codeartifact/tokens", headers=AUTH)
        body = response.json()
        assert len(body) == 1
        assert body[0]["tool"] == "pip"

    def test_parses_pypirc_token(self, mocker, tmp_path):
        exp = int(time.time()) + 3600
        token = _make_jwt(exp)
        (tmp_path / ".pypirc").write_text(
            "[distutils]\nindex-servers = codeartifact\n\n"
            "[codeartifact]\n"
            "repository = https://mycompany-123.d.codeartifact.us-east-1.amazonaws.com/pypi/mycompany-ui-kit/\n"
            "username = aws\n"
            f"password = {token}\n"
        )
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        client, _ = _make_client()
        response = client.get("/codeartifact/tokens", headers=AUTH)
        body = response.json()
        assert len(body) == 1
        assert body[0]["tool"] == "twine"

    def test_dedupes_npmrc_by_domain_repo(self, mocker, tmp_path):
        exp = int(time.time()) + 3600
        token = _make_jwt(exp)
        # Two lines pointing to same domain/repo (e.g. always-auth + authToken)
        npmrc = tmp_path / ".npmrc"
        npmrc.write_text(
            f"//mycompany-123.d.codeartifact.us-east-1.amazonaws.com/npm/mycompany-ui-kit/:always-auth=true\n"
            f"//mycompany-123.d.codeartifact.us-east-1.amazonaws.com/npm/mycompany-ui-kit/:_authToken={token}\n"
        )
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        client, _ = _make_client()
        body = client.get("/codeartifact/tokens", headers=AUTH).json()
        assert len(body) == 1


# ── POST /login ───────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLoginEndpoint:
    def test_422_on_missing_domain(self):
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/login",
            json={"tool": "npm"},
            headers=AUTH,
        )
        assert response.status_code == 422

    def test_422_on_unsupported_tool(self):
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/login",
            json={"domain": "x", "tool": "yarn"},
            headers=AUTH,
        )
        assert response.status_code == 422

    def test_404_when_domain_not_in_config(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.get_domains",
            return_value=[],
        )
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/login",
            json={"domain": "missing", "tool": "npm"},
            headers=AUTH,
        )
        assert response.status_code == 404

    def test_400_on_value_error(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.get_domains",
            return_value=[{"domain": "d", "repository": "r", "namespace": "", "account_id": "", "profile": "", "region": "us-east-1"}],
        )
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.login",
            side_effect=ValueError("No valid SSO profile found"),
        )
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/login",
            json={"domain": "d", "tool": "npm"},
            headers=AUTH,
        )
        assert response.status_code == 400

    def test_502_on_aws_error(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.get_domains",
            return_value=[{"domain": "d", "repository": "r", "namespace": "", "account_id": "", "profile": "", "region": "us-east-1"}],
        )
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.login",
            side_effect=Exception("botocore error"),
        )
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/login",
            json={"domain": "d", "tool": "npm"},
            headers=AUTH,
        )
        assert response.status_code == 502


# ── JWT exp parsing ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestJwtExp:
    def test_valid_jwt(self):
        from cli_tool.sidecar.services.codeartifact_service import _jwt_exp

        exp = int(time.time()) + 3600
        token = _make_jwt(exp)
        result = _jwt_exp(token)
        assert result is not None
        # ISO format check
        from datetime import datetime

        parsed = datetime.fromisoformat(result)
        assert abs(parsed.timestamp() - exp) < 1

    def test_invalid_jwt_returns_none(self):
        from cli_tool.sidecar.services.codeartifact_service import _jwt_exp

        assert _jwt_exp("not-a-jwt") is None
        assert _jwt_exp("a.b") is None
        assert _jwt_exp("") is None

    def test_url_encoded_jwt(self):
        """Tokens in ~/.npmrc are URL-encoded (+ → %2B, / → %2F, = → %3D)."""
        from urllib.parse import quote

        from cli_tool.sidecar.services.codeartifact_service import _jwt_exp

        exp = int(time.time()) + 3600
        token = _make_jwt(exp)
        encoded = quote(token, safe=".")
        result = _jwt_exp(encoded)
        assert result is not None


# ── CRUD service functions ──────────────────────────────────────────────────


@pytest.mark.unit
class TestCreateDomainService:
    def test_raises_on_missing_required(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import create_domain

        mocker.patch(
            "cli_tool.core.utils.config_manager.load_config",
            return_value={"codeartifact": {"domains": []}},
        )
        with pytest.raises(ValueError, match="Missing required"):
            create_domain({"domain": "x"})

    def test_raises_on_duplicate(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import create_domain

        mocker.patch(
            "cli_tool.core.utils.config_manager.load_config",
            return_value={"codeartifact": {"domains": [{"domain": "x", "repository": "r"}]}},
        )
        with pytest.raises(ValueError, match="already exists"):
            create_domain({"domain": "x", "repository": "r"})

    def test_appends_and_saves(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import create_domain

        save_mock = mocker.patch("cli_tool.core.utils.config_manager.save_config")
        mocker.patch(
            "cli_tool.core.utils.config_manager.load_config",
            return_value={"codeartifact": {"domains": []}},
        )
        mocker.patch(
            "cli_tool.sidecar.services.codeartifact_service.get_domains",
            return_value=[{"domain": "new", "repository": "r", "namespace": "", "account_id": "", "profile": "", "region": "us-east-1"}],
        )
        create_domain({"domain": "new", "repository": "r", "namespace": "@x", "account_id": "111"})
        save_mock.assert_called_once()
        saved_config = save_mock.call_args[0][0]
        assert saved_config["codeartifact"]["domains"][0]["domain"] == "new"


@pytest.mark.unit
class TestUpdateDomainService:
    def test_updates_existing(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import update_domain

        save_mock = mocker.patch("cli_tool.core.utils.config_manager.save_config")
        mocker.patch(
            "cli_tool.core.utils.config_manager.load_config",
            return_value={"codeartifact": {"domains": [{"domain": "x", "repository": "r", "profile": ""}]}},
        )
        mocker.patch(
            "cli_tool.sidecar.services.codeartifact_service.get_domains",
            return_value=[{"domain": "x", "repository": "r", "namespace": "", "account_id": "", "profile": "p1", "region": "us-east-1"}],
        )
        update_domain("x", {"profile": "p1"})
        save_mock.assert_called_once()

    def test_raises_when_not_found(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import update_domain

        mocker.patch(
            "cli_tool.core.utils.config_manager.load_config",
            return_value={"codeartifact": {"domains": []}},
        )
        with pytest.raises(ValueError, match="not found"):
            update_domain("missing", {"profile": "p1"})


@pytest.mark.unit
class TestSSOLoginChain:
    def test_returns_202_with_sso_required_when_login_raises(self, mocker):
        """When SSOLoginRequired fires, return 202 + sso_required status."""
        from cli_tool.sidecar.services.codeartifact_service import SSOLoginRequired

        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.get_domains",
            return_value=[{"domain": "d", "repository": "r", "namespace": "", "account_id": "123", "profile": "p", "region": "us-east-1"}],
        )
        mocker.patch(
            "cli_tool.sidecar.routers.codeartifact.login",
            side_effect=SSOLoginRequired("p", "SSO session for 'p' expired"),
        )
        # Don't actually run aws sso login
        mocker.patch("cli_tool.sidecar.routers.codeartifact.threading.Thread")
        client, _ = _make_client()
        response = client.post(
            "/codeartifact/login",
            json={"domain": "d", "tool": "npm"},
            headers=AUTH,
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "sso_required"
        assert body["profile"] == "p"
        assert body["domain"] == "d"
        assert body["tool"] == "npm"

    def test_sso_login_calls_run_sso_login_sync(self, mocker):
        """Background thread should call run_sso_login_sync."""
        from cli_tool.sidecar.routers.codeartifact import _do_sso_login_and_publish
        from cli_tool.sidecar.state import EventHub

        hub = EventHub()
        mock_run = mocker.patch("cli_tool.sidecar.services.sso_service.run_sso_login_sync")

        _do_sso_login_and_publish(hub, "my-profile")

        mock_run.assert_called_once_with(hub, "my-profile", source="codeartifact")

    def test_sso_login_publishes_failure_on_bad_exit(self, mocker):
        # This test is no longer relevant as the exception logic is handled in run_sso_login_sync
        pass


@pytest.mark.unit
class TestEnsureSsoFresh:
    def _mock_config(self, mocker, expires_at):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"sso_start_url": "https://x"},
        )
        mocker.patch(
            "cli_tool.sidecar.services.codeartifact_service._sso_token_expiration_from_cache",
            return_value=expires_at,
        )

    def _mock_boto3(self, mocker, side_effect=None):
        client_mock = mocker.MagicMock()
        if side_effect:
            client_mock.get_caller_identity.side_effect = side_effect
        else:
            client_mock.get_caller_identity.return_value = {"Account": "123"}
        session_mock = mocker.MagicMock()
        session_mock.client.return_value = client_mock
        mocker.patch("boto3.Session", return_value=session_mock)
        return session_mock

    def test_probes_when_sso_token_healthy(self, mocker):
        """Healthy token is still probed via boto3 to catch server-side dead refresh tokens."""
        from datetime import datetime, timedelta, timezone

        from cli_tool.sidecar.services.codeartifact_service import _ensure_sso_fresh

        session_mock = self._mock_boto3(mocker)
        self._mock_config(mocker, datetime.now(timezone.utc) + timedelta(hours=1))

        _ensure_sso_fresh("test-profile")
        session_mock.client.assert_called_once()

    def test_raises_when_probe_fails_healthy_by_file(self, mocker):
        """Server-side dead refresh token: file says healthy but boto3 probe fails."""
        from datetime import datetime, timedelta, timezone

        from cli_tool.sidecar.services.codeartifact_service import SSOLoginRequired, _ensure_sso_fresh

        self._mock_boto3(
            mocker,
            side_effect=Exception("Error when retrieving token from sso: Token has expired and refresh failed"),
        )
        self._mock_config(mocker, datetime.now(timezone.utc) + timedelta(hours=1))

        with pytest.raises(SSOLoginRequired):
            _ensure_sso_fresh("test-profile")

    def test_refreshes_when_expiring(self, mocker):
        from datetime import datetime, timedelta, timezone

        from cli_tool.sidecar.services.codeartifact_service import _ensure_sso_fresh

        session_mock = self._mock_boto3(mocker)
        self._mock_config(mocker, datetime.now(timezone.utc) - timedelta(seconds=10))

        _ensure_sso_fresh("test-profile")
        session_mock.client.assert_called_once()

    def test_raises_when_refresh_token_also_dead(self, mocker):
        from datetime import datetime, timedelta, timezone

        from cli_tool.sidecar.services.codeartifact_service import SSOLoginRequired, _ensure_sso_fresh

        self._mock_boto3(
            mocker,
            side_effect=Exception("Error when retrieving token from sso: Token has expired and refresh failed"),
        )
        self._mock_config(mocker, datetime.now(timezone.utc) - timedelta(seconds=10))

        with pytest.raises(SSOLoginRequired):
            _ensure_sso_fresh("test-profile")

    def test_raises_on_generic_token_expired_message(self, mocker):
        """Catches non-SSOTokenRetrievalError exceptions that contain SSO error text."""
        from datetime import datetime, timedelta, timezone

        from cli_tool.sidecar.services.codeartifact_service import SSOLoginRequired, _ensure_sso_fresh

        self._mock_boto3(mocker, side_effect=Exception("Token has expired and refresh failed"))
        self._mock_config(mocker, datetime.now(timezone.utc) + timedelta(hours=1))

        with pytest.raises(SSOLoginRequired):
            _ensure_sso_fresh("test-profile")

    def test_login_calls_ensure_sso_fresh(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import login

        ensure_mock = mocker.patch("cli_tool.sidecar.services.codeartifact_service._ensure_sso_fresh")
        mocker.patch(
            "cli_tool.sidecar.services.codeartifact_service._get_token",
            return_value=("tok", "2099-01-01T00:00:00Z"),
        )
        mocker.patch("cli_tool.sidecar.services.codeartifact_service._write_npmrc")
        mocker.patch("cli_tool.sidecar.services.codeartifact_service._save_token_metadata")

        domain_cfg = {
            "domain": "d",
            "repository": "r",
            "namespace": "@x",
            "account_id": "123",
            "profile": "p",
            "region": "us-east-1",
        }
        login(domain_cfg, "npm")
        ensure_mock.assert_called_once_with("p")


@pytest.mark.unit
class TestDeleteDomainService:
    def test_deletes_existing(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import delete_domain

        save_mock = mocker.patch("cli_tool.core.utils.config_manager.save_config")
        mocker.patch(
            "cli_tool.core.utils.config_manager.load_config",
            return_value={"codeartifact": {"domains": [{"domain": "x", "repository": "r"}]}},
        )
        delete_domain("x")
        save_mock.assert_called_once()

    def test_raises_when_not_found(self, mocker):
        from cli_tool.sidecar.services.codeartifact_service import delete_domain

        mocker.patch(
            "cli_tool.core.utils.config_manager.load_config",
            return_value={"codeartifact": {"domains": []}},
        )
        with pytest.raises(ValueError, match="not found"):
            delete_domain("missing")


@pytest.mark.unit
class TestListActiveTokensFromRegistry:
    def test_reads_from_registry_file(self, mocker, tmp_path):
        from cli_tool.sidecar.services import codeartifact_service

        reg_file = tmp_path / "registry-tokens.json"
        future = "2099-01-01T00:00:00+00:00"
        past = "2000-01-01T00:00:00+00:00"
        reg_file.write_text(
            json.dumps(
                {
                    "d1::npm": {
                        "domain": "d1",
                        "tool": "npm",
                        "repository": "r",
                        "account_id": "123",
                        "region": "us-east-1",
                        "registry_url": "https://x",
                        "expires_at": future,
                    },
                    "d2::npm": {
                        "domain": "d2",
                        "tool": "npm",
                        "repository": "r2",
                        "account_id": "123",
                        "region": "us-east-1",
                        "registry_url": "https://y",
                        "expires_at": past,
                    },
                }
            )
        )
        mocker.patch("cli_tool.sidecar.services.codeartifact_service._token_registry_path", return_value=reg_file)
        result = codeartifact_service.list_active_tokens()
        domains = {t["domain"] for t in result}
        assert "d1" in domains
        assert "d2" not in domains  # expired, filtered

    def test_empty_when_no_registry(self, mocker, tmp_path):
        from cli_tool.sidecar.services import codeartifact_service

        reg_file = tmp_path / "missing.json"
        mocker.patch("cli_tool.sidecar.services.codeartifact_service._token_registry_path", return_value=reg_file)
        # Also mock Path.home to make JWT parser see no .npmrc
        home = tmp_path
        mocker.patch("pathlib.Path.home", return_value=home)
        result = codeartifact_service.list_active_tokens()
        assert result == []
