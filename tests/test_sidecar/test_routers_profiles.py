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
