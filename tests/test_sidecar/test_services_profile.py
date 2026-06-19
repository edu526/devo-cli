"""Unit tests for cli_tool.sidecar.services.profile_service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from cli_tool.sidecar.services import profile_service
from cli_tool.sidecar.state import EventHub


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
            return_value=[{"name": "dev", "seconds_remaining": 60}],
        )
        hub = EventHub()
        q = hub.subscribe()
        warned: set[str] = set()

        profile_service._tick(hub, warned)

        msg = q.get_nowait()
        assert msg == {"event": "profile.expiring", "name": "dev", "seconds_remaining": 60}
        assert "dev" in warned

    def test_does_not_emit_again_for_same_profile(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[{"name": "dev", "seconds_remaining": 60}],
        )
        hub = EventHub()
        q = hub.subscribe()
        warned = {"dev"}  # already warned

        profile_service._tick(hub, warned)

        assert q.empty()

    def test_does_not_emit_for_none_seconds(self, mocker):
        mocker.patch(
            "cli_tool.sidecar.services.profile_service.get_profiles_info",
            return_value=[{"name": "dev", "seconds_remaining": None}],
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
            return_value=[{"name": "dev", "seconds_remaining": 3600}],
        )
        hub = EventHub()
        warned = {"dev"}  # previously warned
        profile_service._tick(hub, warned)
        assert "dev" not in warned

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
                {"name": "expired", "seconds_remaining": 0},
                {"name": "expiring", "seconds_remaining": 60},
                {"name": "valid", "seconds_remaining": 7200},
                {"name": "unknown", "seconds_remaining": None},
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
        assert "expired" in names
        assert "expiring" in names
        assert "valid" not in names
        assert "unknown" not in names
