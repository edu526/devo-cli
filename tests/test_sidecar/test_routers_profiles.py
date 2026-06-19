import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.routers.profiles import router
from cli_tool.sidecar.state import AppState, EventHub


def _make_client():
    app = FastAPI()
    app_state = AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())
    app.state.app_state = app_state
    # Required for @limiter.limit(...) decorators on this router
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(router)
    return TestClient(app), app_state


AUTH = {"Authorization": "Bearer test-token"}


@pytest.mark.unit
class TestListProfiles:
    def test_returns_profiles(self, mocker):
        profiles = [
            {"name": "dev", "source": "sso", "status": "valid"},
            {"name": "prod", "source": "sso", "status": "expired"},
        ]
        mocker.patch("cli_tool.sidecar.routers.profiles.get_profiles_info", return_value=profiles)
        client, _ = _make_client()
        response = client.get("/profiles", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == profiles


@pytest.mark.unit
class TestGetProfile:
    def test_returns_profile_when_found(self, mocker):
        profile = {"name": "dev", "source": "sso", "status": "valid"}
        mocker.patch("cli_tool.sidecar.routers.profiles.get_profile_info", return_value=profile)
        client, _ = _make_client()
        response = client.get("/profiles/dev", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == profile

    def test_returns_404_when_not_found(self, mocker):
        mocker.patch("cli_tool.sidecar.routers.profiles.get_profile_info", return_value=None)
        client, _ = _make_client()
        response = client.get("/profiles/missing", headers=AUTH)
        assert response.status_code == 404


@pytest.mark.unit
class TestCreateProfile:
    _VALID_BODY = {
        "name": "newdev",
        "sso_session": "my-sso",
        "sso_account_id": "123456789012",
        "sso_role_name": "ReadOnlyRole",
        "region": "us-east-1",
    }

    def test_creates_profile_and_returns_201(self, mocker):
        record = {"name": "newdev", "source": "sso", "status": "unknown", "is_default": False}
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.create_profile",
            return_value=record,
        )
        client, _ = _make_client()
        response = client.post("/profiles", json=self._VALID_BODY, headers=AUTH)
        assert response.status_code == 201
        assert response.json() == record

    def test_returns_409_on_validation_failure(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.create_profile",
            side_effect=ValueError("Profile 'newdev' already exists"),
        )
        client, _ = _make_client()
        response = client.post("/profiles", json=self._VALID_BODY, headers=AUTH)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_returns_422_on_missing_field(self):
        client, _ = _make_client()
        response = client.post("/profiles", json={"name": "newdev"}, headers=AUTH)
        assert response.status_code == 422
        assert "Missing required field" in response.json()["detail"]


@pytest.mark.unit
class TestListSsoSessions:
    def test_returns_sessions(self, mocker):
        sessions = [
            {"name": "corp", "sso_start_url": "https://x.awsapps.com/start", "sso_region": "us-east-1"},
        ]
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.list_sso_sessions",
            return_value=sessions,
        )
        client, _ = _make_client()
        response = client.get("/profiles/sessions", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == sessions

    def test_does_not_shadow_get_profile_by_name(self, mocker):
        # /profiles/sessions must NOT be matched by /profiles/{name}.
        # We register both: a sessions list and a name lookup. Calling
        # /profiles/sessions should return the list, not a 404 for a
        # profile named "sessions".
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.list_sso_sessions",
            return_value=[{"name": "s1"}],
        )
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.get_profile_info",
            return_value=None,
        )
        client, _ = _make_client()
        response = client.get("/profiles/sessions", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == [{"name": "s1"}]


@pytest.mark.unit
class TestCreateSsoSession:
    _VALID = {
        "name": "corp",
        "sso_start_url": "https://x.awsapps.com/start",
        "sso_region": "us-east-1",
    }

    def test_creates_and_returns_201(self, mocker):
        client, _ = _make_client()
        mocker.patch("cli_tool.sidecar.routers.profiles.add_sso_session_to_config")
        response = client.post("/profiles/sessions", json=self._VALID, headers=AUTH)
        assert response.status_code == 201
        assert response.json()["name"] == "corp"

    def test_returns_409_on_collision(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.add_sso_session_to_config",
            side_effect=ValueError("sso-session 'corp' already exists"),
        )
        client, _ = _make_client()
        response = client.post("/profiles/sessions", json=self._VALID, headers=AUTH)
        assert response.status_code == 409

    def test_returns_422_on_missing_field(self):
        client, _ = _make_client()
        response = client.post(
            "/profiles/sessions",
            json={"name": "corp"},
            headers=AUTH,
        )
        assert response.status_code == 422


@pytest.mark.unit
class TestDiscover:
    def test_returns_202_and_kicks_off_background(self, mocker):
        mocked_start = mocker.patch("cli_tool.sidecar.routers.profiles.start_discover")
        client, _ = _make_client()
        response = client.post(
            "/profiles:discover",
            json={"session": "corp"},
            headers=AUTH,
        )
        assert response.status_code == 202
        mocked_start.assert_called_once()
        args = mocked_start.call_args.args
        assert args[1] == "corp"

    def test_returns_422_without_session(self):
        client, _ = _make_client()
        response = client.post("/profiles:discover", json={}, headers=AUTH)
        assert response.status_code == 422


@pytest.mark.unit
class TestRefreshAll:
    def test_returns_202_accepted(self, mocker):
        mocker.patch("threading.Thread")
        client, _ = _make_client()
        response = client.post("/profiles:refresh_all", headers=AUTH)
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"


@pytest.mark.unit
class TestRefreshProfile:
    def test_returns_202_accepted(self, mocker):
        mocker.patch("threading.Thread")
        client, _ = _make_client()
        response = client.post("/profiles/dev:refresh", headers=AUTH)
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "accepted"
        assert "dev" in body["message"]

    def test_publishes_refreshing_event_on_start(self, mocker):
        published = []

        def fake_thread(*args, **kwargs):
            published.append("thread_created")
            return mocker.MagicMock()

        mocker.patch("threading.Thread", side_effect=fake_thread)
        client, _ = _make_client()
        client.post("/profiles/dev:refresh", headers=AUTH)
        assert published == ["thread_created"]

    def test_publishes_refreshed_success_on_completion(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"sso_session": "my-sso"},
        )
        mocker.patch("subprocess.run", return_value=mocker.MagicMock(returncode=0))
        mocker.patch(
            "cli_tool.commands.aws_login.core.credentials.verify_credentials",
            return_value={"account": "123"},
        )

        client, app_state = _make_client()
        events = []

        import threading

        done = threading.Event()
        original_publish = app_state.event_hub.publish

        def capturing_publish(event, payload):
            events.append((event, payload))
            original_publish(event, payload)
            if event == "profile.refreshed":
                done.set()

        app_state.event_hub.publish = capturing_publish

        client.post("/profiles/dev:refresh", headers=AUTH)
        done.wait(timeout=5)

        event_names = [e for e, _ in events]
        assert "profile.refreshing" in event_names
        assert "profile.refreshed" in event_names
        refreshed_payload = next(p for e, p in events if e == "profile.refreshed")
        assert refreshed_payload["success"] is True
        assert "dev" in refreshed_payload["names"]


@pytest.mark.unit
class TestSetDefaultProfile:
    def test_success_returns_name_and_result(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
            return_value={"key": "val"},
        )
        client, _ = _make_client()
        response = client.post("/profiles/dev:set_default", headers=AUTH)
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "dev"
        assert body["key"] == "val"

    def test_none_result_returns_500(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
            return_value=None,
        )
        client, _ = _make_client()
        response = client.post("/profiles/dev:set_default", headers=AUTH)
        assert response.status_code == 500


@pytest.mark.unit
class TestGetIdentity:
    def test_valid_identity_200(self, mocker):
        identity = {"UserId": "AIDAXXXXXXX", "Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/dev"}
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.verify_credentials",
            return_value=identity,
        )
        client, _ = _make_client()
        response = client.get("/profiles/dev/identity", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == identity

    def test_invalid_identity_401(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.verify_credentials",
            return_value=None,
        )
        client, _ = _make_client()
        response = client.get("/profiles/dev/identity", headers=AUTH)
        assert response.status_code == 401
