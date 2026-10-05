"""Tests for the shared SSO login handler (login_coordinator)."""

import threading
import time

import pytest

from cli_tool.sidecar.services import login_coordinator as lc
from cli_tool.sidecar.state import EventHub

RUN = "cli_tool.sidecar.services.sso_service.run_sso_login_sync"
PROFILE_CONFIG = "cli_tool.commands.aws_login.core.config.get_profile_config"


def _events(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


@pytest.fixture
def same_session(mocker):
    """Every profile belongs to the SSO session "corp"."""
    mocker.patch(PROFILE_CONFIG, side_effect=lambda name: {"sso_session": "corp"})


@pytest.fixture
def needs_browser(mocker):
    """The session can't be renewed silently; nothing to renew afterwards."""
    mocker.patch.object(lc, "_renewable_without_browser", return_value=False)
    mocker.patch.object(lc, "_renew_session_profiles", return_value=[])


class _Blocking:
    """A fake run_sso_login_sync that waits until released."""

    def __init__(self, result=True):
        self.calls = []
        self.release = threading.Event()
        self.result = result

    def __call__(self, hub, profile, source, **kwargs):
        self.calls.append((profile, source, kwargs.get("sso_session")))
        hub.publish("sso.login.started", {"profile": profile, "source": source})
        hub.publish("sso.login.url_ready", {"profile": profile, "source": source, "url": "https://x", "code": "AB-12"})
        self.release.wait(timeout=2)
        hub.publish("sso.login.completed", {"profile": profile, "source": source, "success": self.result})
        return self.result


def _wait_idle(key="corp", timeout=2.0):
    end = time.monotonic() + timeout
    while lc.is_running(key) and time.monotonic() < end:
        time.sleep(0.01)


@pytest.mark.unit
class TestSessionKey:
    def test_named_sso_session_wins(self):
        assert lc.session_key_for(sso_session="corp") == "corp"

    def test_profile_uses_its_sso_session(self, mocker):
        mocker.patch(PROFILE_CONFIG, return_value={"sso_session": "corp", "sso_start_url": "https://x"})
        assert lc.session_key_for("dev") == "corp"

    def test_legacy_profile_uses_its_start_url(self, mocker):
        mocker.patch(PROFILE_CONFIG, return_value={"sso_start_url": "https://x"})
        assert lc.session_key_for("dev") == "https://x"

    def test_unknown_profile_falls_back_to_its_name(self, mocker):
        mocker.patch(PROFILE_CONFIG, return_value=None)
        assert lc.session_key_for("dev") == "dev"


@pytest.mark.unit
@pytest.mark.usefixtures("same_session", "needs_browser")
class TestOneLoginPerSession:
    def test_second_request_for_the_same_session_joins(self, mocker):
        fake = _Blocking()
        mocker.patch(RUN, side_effect=fake)
        hub = EventHub()

        s1, _ = lc.request_login(hub, profile="db-dev", source="connection", automatic=True)
        time.sleep(0.05)
        s2, _ = lc.request_login(hub, profile="db-prod", source="codeartifact", automatic=False)
        fake.release.set()
        _wait_idle()

        assert (s1, s2) == (lc.STARTED, lc.JOINED)
        assert len(fake.calls) == 1

    def test_every_requester_gets_the_login_events_with_its_own_source(self, mocker):
        fake = _Blocking()
        mocker.patch(RUN, side_effect=fake)
        hub = EventHub()
        q = hub.subscribe()

        lc.request_login(hub, profile="db-dev", source="connection", automatic=True)
        time.sleep(0.05)
        lc.request_login(hub, profile="p", source="codeartifact", automatic=False)
        fake.release.set()
        _wait_idle()

        completed = {(e["profile"], e["source"]) for e in _events(q) if e["event"] == "sso.login.completed"}
        assert completed == {("db-dev", "connection"), ("p", "codeartifact")}

    def test_a_late_joiner_is_caught_up_with_the_manual_login_url(self, mocker):
        fake = _Blocking()
        mocker.patch(RUN, side_effect=fake)
        hub = EventHub()

        lc.request_login(hub, profile="db-dev", source="connection", automatic=True)
        time.sleep(0.05)  # url_ready already published
        q = hub.subscribe()
        lc.request_login(hub, profile="p", source="profile", automatic=False)
        late = _events(q)
        fake.release.set()
        _wait_idle()

        assert {"event": "sso.login.url_ready", "profile": "p", "source": "profile", "url": "https://x", "code": "AB-12"} in late

    def test_publishes_session_started_and_finished(self, mocker):
        mocker.patch(RUN, return_value=True)
        mocker.patch.object(lc, "_renew_session_profiles", return_value=["db-dev", "db-prod"])
        hub = EventHub()
        q = hub.subscribe()

        assert lc.login_and_wait(hub, profile="db-dev", source="profile") is True

        events = _events(q)
        assert {"event": "sso.session.login_started", "session": "corp", "source": "profile", "automatic": False} in events
        assert {
            "event": "sso.session.login_finished",
            "session": "corp",
            "success": True,
            "renewed": ["db-dev", "db-prod"],
        } in events

    def test_different_sessions_log_in_independently(self, mocker):
        mocker.patch(PROFILE_CONFIG, side_effect=lambda name: {"sso_session": f"s-{name}"})
        calls = []
        mocker.patch(RUN, side_effect=lambda hub, profile, source, **kw: calls.append(profile) or True)
        hub = EventHub()

        lc.login_and_wait(hub, profile="a", source="profile")
        lc.login_and_wait(hub, profile="b", source="profile")

        assert calls == ["a", "b"]

    def test_a_crashing_login_is_cleaned_up(self, mocker):
        mocker.patch(RUN, side_effect=RuntimeError("aws exploded"))
        hub = EventHub()
        q = hub.subscribe()

        assert lc.login_and_wait(hub, profile="db-dev", source="profile") is False

        assert not lc.is_running("corp")
        assert any(e["event"] == "sso.session.login_finished" and e["success"] is False for e in _events(q))


@pytest.mark.unit
@pytest.mark.usefixtures("same_session")
class TestBrowserOnlyWhenNeeded:
    def test_no_browser_when_the_session_can_be_renewed_silently(self, mocker):
        mocker.patch.object(lc, "_renewable_without_browser", return_value=True)
        mocker.patch.object(lc, "_renew_session_profiles", return_value=[])
        run = mocker.patch(RUN)
        hub = EventHub()
        q = hub.subscribe()

        assert lc.login_and_wait(hub, profile="db-dev", source="profile") is True

        run.assert_not_called()
        events = _events(q)
        assert not any(e["event"] == "sso.session.login_started" for e in events)
        # requesters still get the event they wait on
        assert {
            "event": "sso.login.completed",
            "profile": "db-dev",
            "source": "profile",
            "success": True,
            "browser": False,
        } in events

    def test_known_expired_goes_straight_to_the_browser(self, mocker):
        check = mocker.patch.object(lc, "_renewable_without_browser", return_value=True)
        mocker.patch.object(lc, "_renew_session_profiles", return_value=[])
        run = mocker.patch(RUN, return_value=True)

        lc.login_and_wait(EventHub(), profile="db-dev", source="profile", known_expired=True)

        check.assert_not_called()
        run.assert_called_once()

    def test_profile_check_uses_the_silent_renewal(self, mocker):
        silent = mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._silent_refresh_profiles",
            return_value=(["db-dev"], []),
        )
        assert lc._renewable_without_browser("db-dev", None) is True
        silent.assert_called_once_with([("db-dev", "pre-login")])

    def test_session_check_uses_the_cached_sso_token(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.get_existing_sso_sessions",
            return_value={"corp": {"sso_start_url": "https://x"}},
        )
        token = mocker.patch("cli_tool.commands.aws_login.core.credentials.get_sso_cache_token", return_value="tok")
        assert lc._renewable_without_browser(None, "corp") is True
        token.return_value = None
        assert lc._renewable_without_browser(None, "corp") is False

    def test_a_failing_check_means_a_login_is_needed(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._silent_refresh_profiles",
            side_effect=RuntimeError("boom"),
        )
        assert lc._renewable_without_browser("db-dev", None) is False


@pytest.mark.unit
@pytest.mark.usefixtures("same_session", "needs_browser")
class TestAutomaticBackoff:
    def test_a_failed_automatic_login_holds_back_the_next_automatic_one(self, mocker):
        run = mocker.patch(RUN, return_value=False)
        hub = EventHub()

        lc.request_login(hub, profile="db-dev", source="connection", automatic=True)
        _wait_idle()
        status, _ = lc.request_login(hub, profile="db-dev", source="auto_renew", automatic=True)

        assert status == lc.SUPPRESSED
        assert run.call_count == 1

    def test_an_explicit_request_is_never_held_back(self, mocker):
        run = mocker.patch(RUN, return_value=False)
        hub = EventHub()
        lc.request_login(hub, profile="db-dev", source="connection", automatic=True)
        _wait_idle()

        assert lc.login_and_wait(hub, profile="db-dev", source="profile") is False
        assert run.call_count == 2

    def test_backoff_doubles_and_is_capped(self, mocker):
        mocker.patch(RUN, return_value=False)
        delays = []
        for _ in range(6):
            lc.request_login(EventHub(), profile="db-dev", source="connection", automatic=True)
            _wait_idle()
            delays.append(lc._auto_backoff["corp"][1])
            lc._auto_backoff["corp"] = (0.0, lc._auto_backoff["corp"][1])  # let the next one through

        assert delays[0] == 15 * 60
        assert delays[1] == 30 * 60
        assert delays[-1] == 2 * 60 * 60

    def test_the_hold_expires(self, mocker):
        mocker.patch(RUN, return_value=False)
        lc.request_login(EventHub(), profile="db-dev", source="connection", automatic=True)
        _wait_idle()
        lc._auto_backoff["corp"] = (time.monotonic() - 1, lc._auto_backoff["corp"][1])

        status, _ = lc.request_login(EventHub(), profile="db-dev", source="connection", automatic=True)

        assert status == lc.STARTED

    def test_a_successful_login_clears_the_hold(self, mocker):
        run = mocker.patch(RUN, return_value=False)
        lc.request_login(EventHub(), profile="db-dev", source="connection", automatic=True)
        _wait_idle()
        run.return_value = True
        lc.login_and_wait(EventHub(), profile="db-dev", source="profile")

        assert "corp" not in lc._auto_backoff

    def test_an_explicit_joiner_keeps_a_failure_from_holding_back(self, mocker):
        """If the user explicitly asked during an automatic attempt that failed,
        their next automatic retry must not be delayed for it."""
        fake = _Blocking(result=False)
        mocker.patch(RUN, side_effect=fake)
        hub = EventHub()
        lc.request_login(hub, profile="db-dev", source="connection", automatic=True)
        time.sleep(0.05)
        lc.request_login(hub, profile="db-dev", source="profile", automatic=False)
        fake.release.set()
        _wait_idle()

        assert "corp" not in lc._auto_backoff


@pytest.mark.unit
@pytest.mark.usefixtures("needs_browser")
class TestSessionOnlyLogin:
    def test_logs_in_by_session_name(self, mocker):
        run = mocker.patch(RUN, return_value=True)

        assert lc.login_and_wait(EventHub(), sso_session="corp", source="discover", known_expired=True) is True

        args, kwargs = run.call_args
        assert args[1] == "corp"
        assert kwargs["sso_session"] == "corp"

    def test_needs_a_profile_or_a_session(self):
        with pytest.raises(ValueError):
            lc.request_login(EventHub(), source="x", automatic=False)


@pytest.mark.unit
class TestRenewSessionProfiles:
    def test_renews_only_the_profiles_of_that_session(self, mocker):
        mocker.patch(
            "cli_tool.commands.aws_login.core.config.list_aws_profiles",
            return_value=[("a", "sso"), ("b", "sso"), ("c", "sso"), ("static", "credentials")],
        )
        mocker.patch(PROFILE_CONFIG, side_effect=lambda n: {"sso_session": "corp" if n in ("a", "b") else "other"})
        silent = mocker.patch(
            "cli_tool.commands.aws_login.commands.refresh._silent_refresh_profiles",
            side_effect=lambda profs: ([p for p, _ in profs], []),
        )

        assert lc._renew_session_profiles("corp") == ["a", "b"]
        assert [p for p, _ in silent.call_args[0][0]] == ["a", "b"]

    def test_is_best_effort(self, mocker):
        mocker.patch("cli_tool.commands.aws_login.core.config.list_aws_profiles", side_effect=RuntimeError("x"))
        assert lc._renew_session_profiles("corp") == []
