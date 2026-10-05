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

REFRESH = "cli_tool.commands.aws_login.commands.refresh"


@pytest.fixture(autouse=True)
def no_silent_refresh(mocker):
    """Keep these tests hermetic: the silent pass would shell out to the real
    `aws` CLI. By default pretend nothing could be renewed silently so every
    stale profile continues to the browser path these tests were written for."""
    return mocker.patch(f"{REFRESH}._silent_refresh_profiles", side_effect=lambda profs: ([], list(profs)))


@pytest.fixture(autouse=True)
def no_cache_deletion(mocker):
    """A forced refresh deletes AWS CLI cache files: never touch the real ones."""
    return mocker.patch.object(profiles_router, "_renew_role_credentials", side_effect=lambda names: list(names))


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


@pytest.mark.unit
class TestDoRefreshAllSilentFirst:
    @staticmethod
    def _drain(q):
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        return msgs

    def _common(self, mocker, stale):
        mocker.patch("cli_tool.commands.aws_login.core.config.list_aws_profiles", return_value=stale)
        mocker.patch(f"{REFRESH}._classify_profiles", return_value=(list(stale), []))
        mock_group = mocker.patch(
            f"{REFRESH}._group_profiles_by_session",
            side_effect=lambda profs: {"s": [p for p, _ in profs]},
        )
        mock_browser = mocker.patch(
            f"{REFRESH}._refresh_all_sessions",
            side_effect=lambda groups: (None, None, [p for ps in groups.values() for p in ps]),
        )
        return mock_group, mock_browser

    def test_silent_success_never_opens_the_browser(self, mocker, no_silent_refresh):
        _, mock_browser = self._common(mocker, [("dev", "x")])
        no_silent_refresh.side_effect = lambda profs: (["dev"], [])

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_all(hub)

        mock_browser.assert_not_called()
        assert self._drain(q)[-1] == {"event": "profile.refreshed", "names": ["dev"], "success": True}

    def test_only_profiles_that_failed_silently_go_to_the_browser(self, mocker, no_silent_refresh):
        mock_group, mock_browser = self._common(mocker, [("dev", "x"), ("prod", "y")])
        no_silent_refresh.side_effect = lambda profs: (["dev"], [("prod", "y")])

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_all(hub)

        assert mock_group.call_args[0][0] == [("prod", "y")]
        mock_browser.assert_called_once()
        last = self._drain(q)[-1]
        assert last["names"] == ["dev", "prod"]
        assert last["success"] is True
        assert "needs_login" not in last

    def test_allow_browser_false_reports_needs_login_instead(self, mocker, no_silent_refresh):
        _, mock_browser = self._common(mocker, [("dev", "x"), ("prod", "y")])
        no_silent_refresh.side_effect = lambda profs: (["dev"], [("prod", "y")])

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_all(hub, allow_browser=False)

        mock_browser.assert_not_called()
        last = self._drain(q)[-1]
        assert last == {
            "event": "profile.refreshed",
            "names": ["dev"],
            "success": True,
            "needs_login": ["prod"],
        }

    def test_allow_browser_false_with_nothing_renewable(self, mocker, no_silent_refresh):
        self._common(mocker, [("dev", "x")])

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_all(hub, allow_browser=False)

        last = self._drain(q)[-1]
        assert last["names"] == []
        assert last["needs_login"] == ["dev"]
        assert last["success"] is True

    def test_force_skips_the_silent_pass(self, mocker, no_silent_refresh):
        _, mock_browser = self._common(mocker, [("dev", "x")])

        profiles_router._do_refresh_all(EventHub(), force=True)

        no_silent_refresh.assert_not_called()
        mock_browser.assert_called_once()

    def test_silently_renewed_default_profile_rewrites_default_credentials(self, mocker, no_silent_refresh):
        self._common(mocker, [("dev", "x")])
        no_silent_refresh.side_effect = lambda profs: (["dev"], [])
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value="dev")
        mock_write = mocker.patch(
            "cli_tool.sidecar.routers.profiles.write_default_credentials",
            return_value={"expiration": "2099-01-01T00:00:00+00:00"},
        )

        profiles_router._do_refresh_all(EventHub())

        mock_write.assert_called_once_with("dev")


@pytest.mark.unit
class TestDoRefreshAllClassifiesFromCache:
    def test_classification_uses_the_cache_not_a_subprocess_per_profile(self, mocker):
        mocker.patch("cli_tool.commands.aws_login.core.config.list_aws_profiles", return_value=[("dev", "sso")])
        classify = mocker.patch(f"{REFRESH}._classify_profiles", return_value=([], []))

        profiles_router._do_refresh_all(EventHub())

        classify.assert_called_once_with([("dev", "sso")], cached_only=True)


@pytest.mark.unit
class TestDoRefreshOneSilentFirst:
    @staticmethod
    def _drain(q):
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        return msgs

    def test_renews_silently_without_opening_the_browser(self, mocker, no_silent_refresh):
        mocker.patch("cli_tool.commands.aws_login.core.config.get_profile_config", return_value={"sso_session": "s"})
        no_silent_refresh.side_effect = lambda profs: (["dev"], [])
        login = mocker.patch("cli_tool.sidecar.services.sso_service.run_sso_login_sync")

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_one(hub, "dev")

        login.assert_not_called()
        no_silent_refresh.assert_called_once_with([("dev", "manual")])
        assert self._drain(q) == [
            {"event": "profile.refreshing", "name": "dev"},
            {"event": "profile.refreshed", "names": ["dev"], "success": True},
        ]

    def test_falls_back_to_the_browser_login_when_silent_fails(self, mocker, no_silent_refresh):
        mocker.patch("cli_tool.commands.aws_login.core.config.get_profile_config", return_value={"sso_session": "s"})
        login = mocker.patch("cli_tool.sidecar.services.sso_service.run_sso_login_sync", return_value=True)
        mocker.patch.object(profiles_router, "_sync_default_credentials_if_in")

        hub = EventHub()
        q = hub.subscribe()
        profiles_router._do_refresh_one(hub, "dev")

        login.assert_called_once()
        assert self._drain(q)[-1] == {"event": "profile.refreshed", "names": ["dev"], "success": True}

    def test_silent_renewal_of_the_default_profile_rewrites_default_credentials(self, mocker, no_silent_refresh):
        mocker.patch("cli_tool.commands.aws_login.core.config.get_profile_config", return_value={"sso_session": "s"})
        no_silent_refresh.side_effect = lambda profs: (["dev"], [])
        sync = mocker.patch.object(profiles_router, "_sync_default_credentials_if_in")

        profiles_router._do_refresh_one(EventHub(), "dev")

        sync.assert_called_once_with(["dev"])

    def test_missing_profile_is_reported_before_trying_anything(self, mocker, no_silent_refresh):
        mocker.patch("cli_tool.commands.aws_login.core.config.get_profile_config", return_value=None)

        profiles_router._do_refresh_one(EventHub(), "ghost")

        no_silent_refresh.assert_not_called()


@pytest.mark.unit
class TestForce:
    def _stale_dev(self, mocker):
        mocker.patch("cli_tool.commands.aws_login.core.config.list_aws_profiles", return_value=[("dev", "sso")])
        mocker.patch(f"{REFRESH}._classify_profiles", return_value=([("dev", "x")], []))
        mocker.patch(f"{REFRESH}._group_profiles_by_session", return_value={"s": ["dev"]})
        mocker.patch(f"{REFRESH}._refresh_all_sessions", return_value=(None, None, ["dev"]))

    def test_forced_refresh_all_replaces_role_credentials_after_the_login(self, mocker, no_cache_deletion):
        self._stale_dev(mocker)
        profiles_router._do_refresh_all(EventHub(), force=True)
        no_cache_deletion.assert_called_once_with(["dev"])

    def test_normal_refresh_all_keeps_the_cached_role_credentials(self, mocker, no_cache_deletion):
        self._stale_dev(mocker)
        profiles_router._do_refresh_all(EventHub())
        no_cache_deletion.assert_not_called()

    def test_forced_refresh_one_skips_the_silent_pass_and_logs_in(self, mocker, no_silent_refresh, no_cache_deletion):
        mocker.patch("cli_tool.commands.aws_login.core.config.get_profile_config", return_value={"sso_session": "s"})
        login = mocker.patch("cli_tool.sidecar.services.sso_service.run_sso_login_sync", return_value=True)
        mocker.patch.object(profiles_router, "_sync_default_credentials_if_in")
        hub = EventHub()
        q = hub.subscribe()

        profiles_router._do_refresh_one(hub, "dev", force=True)

        no_silent_refresh.assert_not_called()
        login.assert_called_once()
        no_cache_deletion.assert_called_once_with(["dev"])
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert msgs[-1] == {"event": "profile.refreshed", "names": ["dev"], "success": True}

    def test_forced_refresh_one_keeps_the_cache_if_the_login_fails(self, mocker, no_cache_deletion):
        mocker.patch("cli_tool.commands.aws_login.core.config.get_profile_config", return_value={"sso_session": "s"})
        mocker.patch("cli_tool.sidecar.services.sso_service.run_sso_login_sync", return_value=False)

        profiles_router._do_refresh_one(EventHub(), "dev", force=True)

        no_cache_deletion.assert_not_called()

    def test_forced_refresh_one_fails_if_new_credentials_cant_be_fetched(self, mocker, no_cache_deletion):
        mocker.patch("cli_tool.commands.aws_login.core.config.get_profile_config", return_value={"sso_session": "s"})
        mocker.patch("cli_tool.sidecar.services.sso_service.run_sso_login_sync", return_value=True)
        no_cache_deletion.side_effect = lambda names: []
        hub = EventHub()
        q = hub.subscribe()

        profiles_router._do_refresh_one(hub, "dev", force=True)

        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert msgs[-1]["success"] is False


@pytest.mark.unit
class TestRenewRoleCredentials:
    def test_clears_then_refetches_and_returns_the_ones_that_worked(self, mocker):
        mocker.stopall()  # exercise the real helper
        clear = mocker.patch("cli_tool.commands.aws_login.core.credentials.clear_cached_role_credentials")
        mocker.patch(f"{REFRESH}._verify_in_parallel", return_value=[True, False])

        assert profiles_router._renew_role_credentials(["a", "b"]) == ["a"]
        assert [c.args[0] for c in clear.call_args_list] == ["a", "b"]
