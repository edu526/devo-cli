"""Unit tests for cli_tool.sidecar.services.profile_service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from cli_tool.sidecar.services import profile_service
from cli_tool.sidecar.state import EventHub

SILENT = "cli_tool.commands.aws_login.commands.refresh._silent_refresh_profiles"
CONFIG_VALUE = "cli_tool.core.utils.config_manager.get_config_value"


@pytest.fixture(autouse=True)
def hermetic(mocker):
    """Never read the developer's real AWS cache or spawn the real `aws` CLI."""
    mocker.patch.object(profile_service, "read_cached_credentials_expiration", return_value=None)
    mocker.patch.object(profile_service, "_auto_renew", return_value=False)


@pytest.mark.unit
class TestGetProfilesInfo:
    def test_returns_empty_list_when_list_aws_profiles_raises(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            side_effect=Exception("boom"),
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        out = profile_service.get_profiles_info()
        assert out == []

    def test_skips_non_sso_profiles(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("default", "credentials"), ("dev", "sso"), ("prod", "both")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=None,
        )
        out = profile_service.get_profiles_info()
        names = [p["name"] for p in out]
        assert names == ["dev", "prod"]
        assert all(p["status"] == "unknown" for p in out)

    def test_marks_expired_when_past_now(self, mocker):
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=past,
        )
        out = profile_service.get_profiles_info()
        assert out[0]["status"] == "expired"
        assert out[0]["seconds_remaining"] == 0

    def test_marks_expiring_within_5_minutes(self, mocker):
        soon = datetime.now(timezone.utc) + timedelta(minutes=2)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=soon,
        )
        out = profile_service.get_profiles_info()
        assert out[0]["status"] == "expiring"

    def test_marks_valid_when_remaining_is_plenty(self, mocker):
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=future,
        )
        out = profile_service.get_profiles_info()
        assert out[0]["status"] == "valid"
        assert out[0]["seconds_remaining"] > 0

    def test_is_default_flag_matches_config(self, mocker):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("dev", "sso"), ("prod", "sso")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value="prod")
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=future,
        )
        out = profile_service.get_profiles_info()
        assert {p["name"]: p["is_default"] for p in out} == {"dev": False, "prod": True}

    def test_parallel_fetch_returns_all_profiles_above_worker_count(self, mocker):
        """With >_MAX_WORKERS profiles, ThreadPoolExecutor must still return all of them."""
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        names = [f"p{i}" for i in range(profile_service._MAX_WORKERS + 5)]
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[(n, "sso") for n in names],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=future,
        )
        out = profile_service.get_profiles_info()
        assert {p["name"] for p in out} == set(names)
        assert len(out) == len(names)


@pytest.mark.unit
class TestGetProfileInfo:
    def test_returns_none_when_list_aws_profiles_raises(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            side_effect=Exception("boom"),
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        assert profile_service.get_profile_info("dev") is None

    def test_returns_none_when_profile_not_found(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("dev", "sso")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        assert profile_service.get_profile_info("missing") is None

    def test_returns_none_for_non_sso_profile(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("default", "credentials")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=None)
        assert profile_service.get_profile_info("default") is None

    def test_returns_profile_when_found(self, mocker):
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.list_aws_profiles",
            return_value=[("dev", "sso"), ("prod", "sso")],
        )
        mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value="dev")
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profile_credentials_expiration",
            return_value=future,
        )
        info = profile_service.get_profile_info("prod")
        assert info is not None
        assert info["name"] == "prod"
        assert info["status"] == "valid"
        assert info["is_default"] is False


@pytest.mark.unit
class TestTick:
    """The watch_profiles loop is a thin wrapper around _tick(). The
    helper is synchronous and testable without driving an event loop."""

    def test_emits_event_first_time_threshold_crossed(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[{"name": "dev", "sso_session": "my-sso", "sso_token": {"seconds_remaining": 60}}],
        )
        hub = EventHub()
        q = hub.subscribe()
        warned: set[str] = set()

        profile_service._tick(hub, warned)

        msg = q.get_nowait()
        assert msg == {"event": "profile.expiring", "name": "my-sso", "seconds_remaining": 60, "type": "sso"}
        assert "my-sso" in warned

    def test_does_not_emit_again_for_same_session(self, mocker):
        """Two profiles sharing the same SSO session only emit one notification."""
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[
                {"name": "dev-a", "sso_session": "shared-sso", "sso_token": {"seconds_remaining": 60}},
                {"name": "dev-b", "sso_session": "shared-sso", "sso_token": {"seconds_remaining": 60}},
            ],
        )
        hub = EventHub()
        q = hub.subscribe()
        warned: set[str] = set()

        profile_service._tick(hub, warned)

        # Only one event should have been emitted
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        assert len(events) == 1
        assert events[0]["name"] == "shared-sso"

    def test_does_not_emit_again_when_already_warned(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[{"name": "dev", "sso_session": "my-sso", "sso_token": {"seconds_remaining": 60}}],
        )
        hub = EventHub()
        q = hub.subscribe()
        warned = {"my-sso"}  # already warned

        profile_service._tick(hub, warned)

        assert q.empty()

    def test_does_not_emit_for_none_seconds(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[{"name": "dev", "sso_session": "my-sso", "sso_token": {"seconds_remaining": None}}],
        )
        hub = EventHub()
        q = hub.subscribe()
        warned: set[str] = set()

        profile_service._tick(hub, warned)

        assert q.empty()
        assert warned == set()

    def test_clears_warned_set_after_recovery(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[{"name": "dev", "sso_session": "my-sso", "sso_token": {"seconds_remaining": 3600}}],
        )
        hub = EventHub()
        warned = {"my-sso"}  # previously warned
        profile_service._tick(hub, warned)
        assert "my-sso" not in warned

    def test_swallows_exception_in_get_profiles_info(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            side_effect=Exception("boom"),
        )
        hub = EventHub()
        q = hub.subscribe()
        warned: set[str] = set()
        profile_service._tick(hub, warned)  # must not raise
        assert q.empty()

    def test_handles_mix_of_profiles(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[
                {"name": "p1", "sso_session": "expired-sso", "sso_token": {"seconds_remaining": 0}},
                {"name": "p2", "sso_session": "expiring-sso", "sso_token": {"seconds_remaining": 60}},
                {"name": "p3", "sso_session": "valid-sso", "sso_token": {"seconds_remaining": 7200}},
                {"name": "p4", "sso_session": "unknown-sso", "sso_token": {"seconds_remaining": None}},
            ],
        )
        hub = EventHub()
        q = hub.subscribe()
        warned: set[str] = set()

        profile_service._tick(hub, warned)

        events = []
        while not q.empty():
            events.append(q.get_nowait())
        names = [e["name"] for e in events]
        assert "expired-sso" in names
        assert "expiring-sso" in names
        assert "valid-sso" not in names
        assert "unknown-sso" not in names

    def test_silent_sts_auto_refresh(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[
                {
                    "name": "dev",
                    "sso_session": "my-sso",
                    "is_default": True,
                    "seconds_remaining": 60,  # STS is dying
                    "sso_token": {"seconds_remaining": 7200},  # SSO is healthy
                }
            ],
        )
        write_mock = mocker.patch("cli_tool.commands.aws_login.core.credentials.write_default_credentials")
        hub = EventHub()
        warned: set[str] = set()

        profile_service._tick(hub, warned)

        write_mock.assert_called_once_with("dev")

    def test_default_resync_fires_on_first_tick_even_when_sts_looks_healthy(self, mocker):
        """`export-credentials` silently refreshes STS before it ever looks
        "dying", so the resync must not depend on that signal — it should
        fire on the very first tick (never synced before) regardless."""
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[
                {
                    "name": "dev",
                    "sso_session": "my-sso",
                    "is_default": True,
                    "seconds_remaining": 3600,  # STS looks perfectly healthy
                    "sso_token": {"seconds_remaining": 7200},
                }
            ],
        )
        write_mock = mocker.patch("cli_tool.commands.aws_login.core.credentials.write_default_credentials")
        hub = EventHub()
        warned: set[str] = set()

        result = profile_service._tick(hub, warned)

        write_mock.assert_called_once_with("dev")
        assert "dev" in result

    def test_default_resync_skipped_within_interval(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[
                {
                    "name": "dev",
                    "sso_session": "my-sso",
                    "is_default": True,
                    "seconds_remaining": 3600,
                    "sso_token": {"seconds_remaining": 7200},
                }
            ],
        )
        write_mock = mocker.patch("cli_tool.commands.aws_login.core.credentials.write_default_credentials")
        hub = EventHub()
        warned: set[str] = set()
        last_default_sync = {"dev": datetime.now(timezone.utc)}

        result = profile_service._tick(hub, warned, last_default_sync)

        write_mock.assert_not_called()
        assert result["dev"] == last_default_sync["dev"]

    def test_default_resync_fires_again_after_interval_elapses(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[
                {
                    "name": "dev",
                    "sso_session": "my-sso",
                    "is_default": True,
                    "seconds_remaining": 3600,
                    "sso_token": {"seconds_remaining": 7200},
                }
            ],
        )
        write_mock = mocker.patch("cli_tool.commands.aws_login.core.credentials.write_default_credentials")
        hub = EventHub()
        warned: set[str] = set()
        stale_sync = datetime.now(timezone.utc) - timedelta(seconds=profile_service._DEFAULT_SYNC_INTERVAL_SECONDS + 1)

        result = profile_service._tick(hub, warned, {"dev": stale_sync})

        write_mock.assert_called_once_with("dev")
        assert result["dev"] > stale_sync

    def test_default_resync_skipped_when_sso_token_itself_is_expiring(self, mocker):
        """If the underlying SSO token is also close to dying, don't bother
        attempting a resync that would just fail — wait for a real login."""
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[
                {
                    "name": "dev",
                    "sso_session": "my-sso",
                    "is_default": True,
                    "seconds_remaining": 3600,
                    "sso_token": {"seconds_remaining": 30},  # SSO itself is dying
                }
            ],
        )
        write_mock = mocker.patch("cli_tool.commands.aws_login.core.credentials.write_default_credentials")
        hub = EventHub()
        warned: set[str] = set()

        profile_service._tick(hub, warned)

        write_mock.assert_not_called()


@pytest.mark.unit
class TestBuildProfileInfoUsesCache:
    NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    def test_cached_expiration_is_used_without_spawning_aws(self, mocker):
        mocker.patch.object(profile_service, "read_cached_credentials_expiration", return_value=self.NOW + timedelta(hours=2))
        spawn = mocker.patch.object(profile_service, "get_profile_credentials_expiration")
        mocker.patch.object(profile_service, "_get_sso_token_info", return_value=None)
        mocker.patch.object(profile_service, "_get_sso_session_name", return_value=None)

        info = profile_service._build_profile_info("dev", "sso", None, self.NOW)

        spawn.assert_not_called()
        assert info["status"] == "valid"
        assert info["seconds_remaining"] == 2 * 3600

    def test_expired_cache_entry_is_reported_as_expired_not_unknown(self, mocker):
        mocker.patch.object(profile_service, "read_cached_credentials_expiration", return_value=self.NOW - timedelta(hours=55))
        spawn = mocker.patch.object(profile_service, "get_profile_credentials_expiration")
        mocker.patch.object(profile_service, "_get_sso_token_info", return_value=None)
        mocker.patch.object(profile_service, "_get_sso_session_name", return_value=None)

        info = profile_service._build_profile_info("dev", "sso", None, self.NOW)

        spawn.assert_not_called()
        assert info["status"] == "expired"

    def test_falls_back_to_aws_when_there_is_no_cache_entry(self, mocker):
        mocker.patch.object(profile_service, "read_cached_credentials_expiration", return_value=None)
        spawn = mocker.patch.object(profile_service, "get_profile_credentials_expiration", return_value=self.NOW + timedelta(hours=1))
        mocker.patch.object(profile_service, "_get_sso_token_info", return_value=None)
        mocker.patch.object(profile_service, "_get_sso_session_name", return_value=None)

        info = profile_service._build_profile_info("dev", "sso", None, self.NOW)

        spawn.assert_called_once_with("dev")
        assert info["status"] == "valid"


def _p(name, secs, session="corp", sso="expired", status=None):
    """A profile-info record as get_profiles_info() returns them."""
    if status is None:
        status = "unknown" if secs is None else ("expired" if secs <= 0 else ("expiring" if secs <= 300 else "valid"))
    return {
        "name": name,
        "seconds_remaining": secs,
        "status": status,
        "sso_session": session,
        "sso_token": {"status": sso} if sso else None,
    }


def _events(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


@pytest.mark.unit
class TestAutoRenew:
    @pytest.fixture(autouse=True)
    def real_auto_renew(self, mocker):
        # undo the module-wide stub: these tests exercise the real function
        mocker.stopall()
        mocker.patch.object(profile_service, "read_cached_credentials_expiration", return_value=None)
        self.config = mocker.patch(CONFIG_VALUE, side_effect=lambda key, default=None: default)
        # Dead sessions go to the shared login handler; never run a real login.
        self.request_login = mocker.patch(
            "cli_tool.sidecar.services.login_coordinator.request_login",
            return_value=("started", None),
        )

    def test_renews_only_stale_profiles(self, mocker):
        silent = mocker.patch(SILENT, return_value=(["old", "soon"], []))
        profiles = [_p("fresh", 3 * 3600), _p("old", -10), _p("soon", 10 * 60), _p("never", None)]
        silent.return_value = (["old", "soon", "never"], [])

        renewed = profile_service._auto_renew(EventHub(), profiles, {})

        assert renewed is True
        sent = [name for name, _ in silent.call_args[0][0]]
        assert sorted(sent) == ["never", "old", "soon"]  # not "fresh"

    def test_threshold_is_fifteen_minutes(self, mocker):
        silent = mocker.patch(SILENT, return_value=(["in14"], []))
        profile_service._auto_renew(EventHub(), [_p("in14", 14 * 60), _p("in16", 16 * 60)], {})
        assert [n for n, _ in silent.call_args[0][0]] == ["in14"]

    def test_nothing_to_do_does_not_spawn_anything(self, mocker):
        silent = mocker.patch(SILENT)
        assert profile_service._auto_renew(EventHub(), [_p("a", 3 * 3600)], {}) is False
        silent.assert_not_called()

    def test_can_be_disabled_in_config(self, mocker):
        self.config.side_effect = lambda key, default=None: False if key == "aws_login.auto_renew" else default
        silent = mocker.patch(SILENT)

        assert profile_service._auto_renew(EventHub(), [_p("a", -5)], {}) is False
        silent.assert_not_called()

    def test_dead_session_asks_the_login_handler_once(self, mocker):
        mocker.patch(SILENT, return_value=([], [("a", "stale"), ("b", "stale")]))
        hub = EventHub()
        q = hub.subscribe()

        renewed = profile_service._auto_renew(hub, [_p("a", -5), _p("b", -5)], {})

        assert renewed is False
        self.request_login.assert_called_once_with(hub, profile="a", source="auto_renew", automatic=True, known_expired=True)
        # the handler's own events drive the UI; no needs_login here
        assert _events(q) == []

    def test_held_back_login_publishes_one_needs_login_event(self, mocker):
        """When the handler holds an automatic login back (a recent one wasn't
        completed), the UI is told so it can offer a "Log in" button."""
        mocker.patch(SILENT, return_value=([], [("a", "stale"), ("b", "stale")]))
        self.request_login.return_value = ("suppressed", None)
        hub = EventHub()
        q = hub.subscribe()
        state: dict = {}

        profile_service._auto_renew(hub, [_p("a", -5), _p("b", -5)], state)
        state["retry_after"].clear()
        profile_service._auto_renew(hub, [_p("a", -5), _p("b", -5)], state)

        assert _events(q) == [
            {
                "event": "profile.needs_login",
                "sessions": ["corp"],
                "names": ["a", "b"],
                "by_session": {"corp": ["a", "b"]},
            }
        ]

    def test_sessions_with_a_login_in_progress_are_not_retried_silently(self, mocker):
        silent = mocker.patch(SILENT)
        mocker.patch("cli_tool.sidecar.services.login_coordinator.is_running", side_effect=lambda key: key == "corp")

        profile_service._auto_renew(EventHub(), [_p("a", -5, session="corp")], {})

        silent.assert_not_called()

    def test_failed_profiles_are_not_retried_during_the_cooldown(self, mocker):
        silent = mocker.patch(SILENT, return_value=([], [("a", "stale")]))
        hub = EventHub()
        q = hub.subscribe()
        state: dict = {}

        profile_service._auto_renew(hub, [_p("a", -5)], state)
        _events(q)
        profile_service._auto_renew(hub, [_p("a", -5)], state)

        assert silent.call_count == 1
        assert _events(q) == []  # and no second notification

    def test_a_valid_sso_token_bypasses_the_cooldown(self, mocker):
        """The user logged in meanwhile: retry at once instead of waiting."""
        silent = mocker.patch(SILENT, return_value=([], [("a", "stale")]))
        state: dict = {}
        profile_service._auto_renew(EventHub(), [_p("a", -5)], state)

        silent.return_value = (["a"], [])
        renewed = profile_service._auto_renew(EventHub(), [_p("a", -5, sso="valid")], state)

        assert silent.call_count == 2
        assert renewed is True

    def test_retries_after_the_cooldown_has_passed(self, mocker):
        silent = mocker.patch(SILENT, return_value=([], [("a", "stale")]))
        state: dict = {}
        profile_service._auto_renew(EventHub(), [_p("a", -5)], state)
        state["retry_after"]["a"] = datetime.now(timezone.utc) - timedelta(seconds=1)

        profile_service._auto_renew(EventHub(), [_p("a", -5)], state)

        assert silent.call_count == 2

    def test_a_session_that_renewed_something_is_not_reported_as_needing_login(self, mocker):
        mocker.patch(SILENT, return_value=(["a"], [("b", "stale")]))
        hub = EventHub()
        q = hub.subscribe()

        renewed = profile_service._auto_renew(hub, [_p("a", -5), _p("b", -5)], {})

        assert renewed is True
        assert _events(q) == []  # b failed on its own; a login would not fix that

    def test_notifies_again_after_the_session_recovered_and_died_again(self, mocker):
        silent = mocker.patch(SILENT, return_value=([], [("a", "stale")]))
        self.request_login.return_value = ("suppressed", None)
        hub = EventHub()
        q = hub.subscribe()
        state: dict = {}

        profile_service._auto_renew(hub, [_p("a", -5)], state)
        assert len(_events(q)) == 1

        silent.return_value = (["a"], [])  # logged in, renewed
        profile_service._auto_renew(hub, [_p("a", -5, sso="valid")], state)

        silent.return_value = ([], [("a", "stale")])  # session dies again later
        state["retry_after"].clear()
        profile_service._auto_renew(hub, [_p("a", -5)], state)

        kinds = [e["event"] for e in _events(q)]
        assert kinds == ["profile.login_resolved", "profile.needs_login"]

    def test_publishes_login_resolved_when_a_reported_session_is_renewed(self, mocker):
        silent = mocker.patch(SILENT, return_value=([], [("a", "stale")]))
        hub = EventHub()
        q = hub.subscribe()
        state: dict = {}
        profile_service._auto_renew(hub, [_p("a", -5)], state)
        _events(q)

        silent.return_value = (["a"], [])
        state["retry_after"].clear()
        profile_service._auto_renew(hub, [_p("a", -5)], state)

        assert _events(q) == [{"event": "profile.login_resolved", "sessions": ["corp"]}]

    def test_publishes_login_resolved_when_the_user_logs_in_elsewhere(self, mocker):
        """e.g. `aws sso login` in a terminal: the SSO token is valid again even
        though nothing was renewed by us yet."""
        mocker.patch(SILENT, return_value=([], [("a", "stale")]))
        hub = EventHub()
        q = hub.subscribe()
        state: dict = {}
        profile_service._auto_renew(hub, [_p("a", -5)], state)
        _events(q)

        profile_service._auto_renew(hub, [_p("a", 3 * 3600, sso="valid")], state)

        assert _events(q) == [{"event": "profile.login_resolved", "sessions": ["corp"]}]

    def test_login_resolved_is_not_published_for_sessions_never_reported(self, mocker):
        mocker.patch(SILENT, return_value=(["a"], []))
        hub = EventHub()
        q = hub.subscribe()

        profile_service._auto_renew(hub, [_p("a", -5, sso="valid")], {})

        assert _events(q) == []

    def test_each_dead_session_gets_its_own_login_request(self, mocker):
        mocker.patch(SILENT, return_value=([], [("a", "stale"), ("z", "stale")]))

        profile_service._auto_renew(EventHub(), [_p("a", -5, session="corp"), _p("z", -5, session="personal")], {})

        assert sorted(c.kwargs["profile"] for c in self.request_login.call_args_list) == ["a", "z"]

    def test_sessions_are_reported_independently(self, mocker):
        mocker.patch(SILENT, return_value=([], [("a", "stale"), ("z", "stale")]))
        self.request_login.return_value = ("suppressed", None)
        hub = EventHub()
        q = hub.subscribe()

        profile_service._auto_renew(hub, [_p("a", -5, session="corp"), _p("z", -5, session="personal")], {})

        (event,) = _events(q)
        assert event["sessions"] == ["corp", "personal"]
        assert sorted(event["names"]) == ["a", "z"]
        assert event["by_session"] == {"corp": ["a"], "personal": ["z"]}


@pytest.mark.unit
class TestTickAutoRenew:
    def test_rereads_profiles_after_a_renewal(self, mocker):
        get_info = mocker.patch.object(profile_service, "get_profiles_info", return_value=[])
        mocker.patch.object(profile_service, "_auto_renew", return_value=True)

        profile_service._tick(EventHub(), set())

        assert get_info.call_count == 2

    def test_does_not_reread_when_nothing_was_renewed(self, mocker):
        get_info = mocker.patch.object(profile_service, "get_profiles_info", return_value=[])
        mocker.patch.object(profile_service, "_auto_renew", return_value=False)

        profile_service._tick(EventHub(), set())

        assert get_info.call_count == 1

    def test_a_failing_auto_renew_does_not_break_the_tick(self, mocker):
        mocker.patch.object(
            profile_service,
            "get_profiles_info",
            return_value=[{"name": "dev", "sso_session": "s", "sso_token": {"seconds_remaining": 60}}],
        )
        mocker.patch.object(profile_service, "_auto_renew", side_effect=RuntimeError("boom"))
        hub = EventHub()
        q = hub.subscribe()

        profile_service._tick(hub, set())

        assert _events(q)[0]["event"] == "profile.expiring"  # the rest of the tick still ran

    def test_passes_its_memory_to_auto_renew(self, mocker):
        mocker.patch.object(profile_service, "get_profiles_info", return_value=[])
        auto = mocker.patch.object(profile_service, "_auto_renew", return_value=False)
        state: dict = {}

        profile_service._tick(EventHub(), set(), None, state)

        assert auto.call_args[0][2] is state


@pytest.mark.unit
class TestWatchProfiles:
    def test_ticks_run_in_a_worker_thread_and_do_not_block_the_event_loop(self, mocker):
        import asyncio
        import threading
        import time

        mocker.patch.object(profile_service, "_FIRST_POLL_DELAY", 0)
        mocker.patch.object(profile_service, "_POLL_INTERVAL", 0.01)
        ticks: list[int] = []

        def slow_tick(hub, warned, last_default_sync, renew_state):
            ticks.append(threading.get_ident())
            time.sleep(0.3)  # what a real tick can spend on `aws`
            return last_default_sync

        mocker.patch.object(profile_service, "_tick", side_effect=slow_tick)

        async def scenario():
            task = asyncio.create_task(profile_service.watch_profiles(EventHub()))
            beats = 0
            end = time.monotonic() + 0.5
            while time.monotonic() < end:
                await asyncio.sleep(0.02)
                beats += 1
            task.cancel()
            return beats

        beats = asyncio.run(scenario())

        assert ticks and all(t != threading.get_ident() for t in ticks)
        # a blocked loop would manage only a couple of beats in 0.5 s
        assert beats >= 10

    def test_keeps_running_after_a_tick_raises(self, mocker):
        import asyncio

        mocker.patch.object(profile_service, "_FIRST_POLL_DELAY", 0)
        mocker.patch.object(profile_service, "_POLL_INTERVAL", 0.01)
        calls = []

        def flaky(hub, warned, last_default_sync, renew_state):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            return last_default_sync

        mocker.patch.object(profile_service, "_tick", side_effect=flaky)

        async def scenario():
            task = asyncio.create_task(profile_service.watch_profiles(EventHub()))
            await asyncio.sleep(0.2)
            task.cancel()

        asyncio.run(scenario())

        assert len(calls) >= 2
