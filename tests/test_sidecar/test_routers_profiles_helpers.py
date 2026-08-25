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
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert msgs[0] == {"event": "profile.refreshing", "name": "1 profile(s)"}
        assert msgs[1] == {"event": "profile.refreshed", "names": ["dev"], "success": True}

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

    def test_writes_default_credentials_when_refreshed_profile_is_default(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"region": "us-east-1"},
        )
        mocker.patch(
            "cli_tool.sidecar.services.sso_service.run_sso_login_sync",
            return_value=True,
        )
        mocker.patch(
            "cli_tool.core.utils.config_manager.get_config_value",
            return_value="dev",
        )
        mock_write = mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
            return_value={"expiration": "2099-01-01T00:00:00+00:00"},
        )

        profiles_router._do_refresh_one(EventHub(), "dev")
        mock_write.assert_called_once_with("dev")

    def test_does_not_write_default_when_refreshed_profile_is_not_default(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"region": "us-east-1"},
        )
        mocker.patch(
            "cli_tool.sidecar.services.sso_service.run_sso_login_sync",
            return_value=True,
        )
        mocker.patch(
            "cli_tool.core.utils.config_manager.get_config_value",
            return_value="other-profile",
        )
        mock_write = mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
        )

        profiles_router._do_refresh_one(EventHub(), "dev")
        mock_write.assert_not_called()

    def test_does_not_write_default_when_no_default_profile_is_configured(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"region": "us-east-1"},
        )
        mocker.patch(
            "cli_tool.sidecar.services.sso_service.run_sso_login_sync",
            return_value=True,
        )
        mocker.patch(
            "cli_tool.core.utils.config_manager.get_config_value",
            return_value=None,
        )
        mock_write = mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
        )

        profiles_router._do_refresh_one(EventHub(), "dev")
        mock_write.assert_not_called()

    def test_swallows_write_default_failure(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_profile_config",
            return_value={"region": "us-east-1"},
        )
        mocker.patch(
            "cli_tool.sidecar.services.sso_service.run_sso_login_sync",
            return_value=True,
        )
        mocker.patch(
            "cli_tool.core.utils.config_manager.get_config_value",
            return_value="dev",
        )
        mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
            side_effect=RuntimeError("boom"),
        )

        # Must not raise — the refresh is the user-visible operation.
        profiles_router._do_refresh_one(EventHub(), "dev")


@pytest.mark.unit
class TestDoRefreshAllDefaultSync:
    def test_writes_default_when_default_profile_is_in_verified(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso"), ("prod", "sso")],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([("dev", "sso"), ("prod", "sso")], []),
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session",
            return_value={"session-1": ["dev", "prod"]},
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions",
            return_value=(None, None, ["dev", "prod"]),
        )
        mocker.patch(
            "cli_tool.core.utils.config_manager.get_config_value",
            return_value="dev",
        )
        mock_write = mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
            return_value={"expiration": "2099-01-01T00:00:00+00:00"},
        )

        profiles_router._do_refresh_all(EventHub())
        mock_write.assert_called_once_with("dev")

    def test_does_not_write_default_when_default_profile_not_verified(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso"), ("prod", "sso")],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([("dev", "sso"), ("prod", "sso")], []),
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session",
            return_value={"session-1": ["dev", "prod"]},
        )
        # Default profile (dev) FAILED verification, prod succeeded.
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions",
            return_value=(None, None, ["prod"]),
        )
        mocker.patch(
            "cli_tool.core.utils.config_manager.get_config_value",
            return_value="dev",
        )
        mock_write = mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
        )

        profiles_router._do_refresh_all(EventHub())
        mock_write.assert_not_called()

    def test_does_not_write_default_when_no_default_configured(self, mocker):
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
        mocker.patch(
            "cli_tool.core.utils.config_manager.get_config_value",
            return_value=None,
        )
        mock_write = mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
        )

        profiles_router._do_refresh_all(EventHub())
        mock_write.assert_not_called()


@pytest.mark.unit
class TestDoRefreshAllForce:
    def test_force_true_refreshes_valid_profiles_too(self, mocker):
        """When force=True, profiles that are still valid must also be renewed.

        Without force, _classify_profiles returns ([("dev", ...)], valid=[]);
        the second profile is dropped because it's valid. With force=True
        it must be added back to the refresh list and sent through.
        """
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso"), ("prod", "sso")],
        )
        # dev needs refresh, prod is still valid.
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([("dev", "sso")], [("prod", "sso")]),
        )
        mock_group = mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session",
            return_value={"session-1": ["dev", "prod"]},
        )
        mock_refresh = mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions",
            return_value=(None, None, ["dev", "prod"]),
        )

        profiles_router._do_refresh_all(EventHub(), force=True)

        # Both profiles made it into the session group, not just dev.
        grouped = mock_group.call_args[0][0]
        assert ("dev", "sso") in grouped
        # prod was added by the force branch with a "Forced refresh" reason.
        assert any(name == "prod" for name, _ in grouped)
        mock_refresh.assert_called_once()

    def test_force_false_skips_valid_profiles(self, mocker):
        """Default behaviour (force=False) must not refresh still-valid profiles."""
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("dev", "sso"), ("prod", "sso")],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([("dev", "sso")], [("prod", "sso")]),
        )
        mock_group = mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session",
            return_value={"session-1": ["dev"]},
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions",
            return_value=(None, None, ["dev"]),
        )

        profiles_router._do_refresh_all(EventHub(), force=False)

        grouped = mock_group.call_args[0][0]
        assert ("dev", "sso") in grouped
        assert not any(name == "prod" for name, _ in grouped)

    def test_force_true_short_circuits_when_nothing_to_refresh(self, mocker):
        """If classify says 'nothing to refresh' (empty list, no valids),
        force must still produce the short-circuit 'nothing' outcome."""
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[],
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._classify_profiles",
            return_value=([], []),
        )
        mock_refresh = mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._refresh_all_sessions",
        )
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._group_profiles_by_session",
        )

        profiles_router._do_refresh_all(EventHub(), force=True)

        mock_refresh.assert_not_called()
