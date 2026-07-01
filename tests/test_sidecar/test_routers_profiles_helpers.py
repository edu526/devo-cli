"""Unit tests for the internal helpers in cli_tool.sidecar.routers.profiles.

The HTTP-path tests live in test_routers_profiles.py. This file targets
the two background-thread bodies (`_do_refresh_all`, `_do_refresh_one`)
that are otherwise hard to cover because they spawn `threading.Thread`.
We exercise them directly so we can patch the subprocess / aws_login
imports without standing up a real FastAPI request.
"""

from unittest.mock import MagicMock, patch

import pytest

from cli_tool.sidecar.routers import profiles as profiles_router
from cli_tool.sidecar.state import EventHub


@pytest.mark.unit
class TestDoRefreshAll:
    def test_publishes_success_with_verified_names(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([("dev", "sso")], []),
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session",
            return_value={"session-1": ["dev"]},
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions",
            return_value=(None, None, ["dev"]),
        )

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_all(hub)
        msg = q.get_nowait()
        assert msg == {"event": "profile.refreshed", "names": ["dev"], "success": True}

    def test_short_circuits_when_nothing_to_refresh(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([], []),
        )
        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_all(hub)
        msg = q.get_nowait()
        assert msg == {"event": "profile.refreshed", "names": [], "success": True}

    def test_publishes_failure_on_exception(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            side_effect=Exception("aws boom"),
        )
        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_all(hub)
        msg = q.get_nowait()
        assert msg["success"] is False
        assert msg["names"] == []
        assert "aws boom" in msg["error"]


@pytest.mark.unit
class TestDoRefreshOne:
    def test_publishes_not_found_when_profile_config_missing(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value=None,
        )

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_one(hub, "missing")
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert msgs[0] == {"event": "profile.refreshing", "name": "missing"}
        assert msgs[1]["event"] == "profile.refreshed"
        assert msgs[1]["success"] is False
        assert "not found" in msgs[1]["error"]

    def test_publishes_failure_when_run_sso_login_sync_fails(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"region": "us-east-1"},
        )
        mocker.patch(
            "cli_tool.sidecar.services.sso_service.run_sso_login_sync",
            return_value=False,
        )

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_one(hub, "dev")
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert msgs[0] == {"event": "profile.refreshing", "name": "dev"}
        assert msgs[1]["success"] is False
        assert "Refresh failed" in msgs[1]["error"]

    def test_publishes_success_when_sso_login_succeeds(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"region": "us-east-1"},
        )
        mocker.patch(
            "cli_tool.sidecar.services.sso_service.run_sso_login_sync",
            return_value=True,
        )

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_one(hub, "dev")
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert msgs[0] == {"event": "profile.refreshing", "name": "dev"}
        assert msgs[1] == {"event": "profile.refreshed", "names": ["dev"], "success": True}
