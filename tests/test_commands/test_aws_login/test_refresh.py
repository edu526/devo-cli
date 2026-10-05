"""Unit tests for cli_tool.commands.aws_login.commands.refresh module."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call

import pytest

from cli_tool.commands.aws_login.commands.refresh import (
    _classify_profiles,
    _refresh_session,
    _silent_refresh_profiles,
    _update_default_credentials_after_refresh,
    _verify_in_parallel,
    _verify_session_profiles,
    refresh_all_profiles,
)

# ---------------------------------------------------------------------------
# _refresh_session
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_refresh_session_success_all_verified(mocker):
    """Successful session refresh verifies all profiles."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mock_get_config = mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config")
    mock_get_config.return_value = {"sso_session": "my-session"}

    mock_verify = mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials")
    mock_verify.return_value = {"account": "123456789012", "arn": "arn:aws:iam::123456789012:role/Dev"}

    ok, verified, failed, verified_names = _refresh_session("my-session", ["dev", "staging"])

    assert ok is True
    assert verified == 2
    assert failed == 0
    assert set(verified_names) == {"dev", "staging"}


@pytest.mark.unit
def test_refresh_session_uses_sso_session_login_cmd(mocker):
    """When profile has sso_session, login command uses --sso-session flag."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value={"sso_session": "my-sso"})
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", return_value=True)

    _refresh_session("my-sso", ["dev"])

    call_args = mock_run.call_args[0][0]
    assert "--sso-session" in call_args
    assert "my-sso" in call_args


@pytest.mark.unit
def test_refresh_session_uses_profile_login_cmd_when_no_sso_session(mocker):
    """When profile has no sso_session, login command uses --profile flag."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value={"sso_start_url": "https://example.com/start"})
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", return_value=True)

    _refresh_session("some-key", ["dev"])

    call_args = mock_run.call_args[0][0]
    assert "--profile" in call_args
    assert "dev" in call_args


@pytest.mark.unit
def test_refresh_session_uses_profile_login_cmd_when_config_is_none(mocker):
    """When get_profile_config returns None, login command uses --profile flag."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", return_value=True)

    _refresh_session("some-key", ["dev"])

    call_args = mock_run.call_args[0][0]
    assert "--profile" in call_args


@pytest.mark.unit
def test_refresh_session_returns_false_on_nonzero_returncode(mocker):
    """Non-zero return code from aws sso login returns failure tuple."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=1)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)

    ok, verified, failed, verified_names = _refresh_session("key", ["dev", "staging"])

    assert ok is False
    assert verified == 0
    assert failed == 2
    assert verified_names == []


@pytest.mark.unit
def test_refresh_session_timeout_returns_false(mocker):
    """subprocess.TimeoutExpired results in failure tuple."""
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("aws", 120))
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)

    ok, verified, failed, verified_names = _refresh_session("key", ["dev"])

    assert ok is False
    assert verified == 0
    assert failed == 1
    assert verified_names == []


@pytest.mark.unit
def test_refresh_session_keyboard_interrupt_exits(mocker):
    """KeyboardInterrupt causes sys.exit(1)."""
    mocker.patch("subprocess.run", side_effect=KeyboardInterrupt())
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)

    with pytest.raises(SystemExit) as exc_info:
        _refresh_session("key", ["dev"])

    assert exc_info.value.code == 1


@pytest.mark.unit
def test_refresh_session_partial_verification_failure(mocker):
    """Some profiles verified, some fail — counts are correct."""
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(returncode=0)

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value={"sso_session": "s"})

    verify_results = [True, None, True]  # None counts as failed (falsy)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.verify_credentials", side_effect=verify_results)

    ok, verified, failed, verified_names = _refresh_session("s", ["dev", "staging", "prod"])

    assert ok is True
    assert verified == 2
    assert failed == 1
    assert set(verified_names) == {"dev", "prod"}


# ---------------------------------------------------------------------------
# refresh_all_profiles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_refresh_all_profiles_no_profiles_exits_0(mocker):
    """When no AWS profiles exist, sys.exit(0) is called."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=[])

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_all_valid_exits_0(mocker):
    """When all profiles are valid, sys.exit(0) is called."""
    profiles = [("dev", "sso"), ("prod", "sso")]
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=profiles)

    future = datetime.now(timezone.utc) + timedelta(hours=8)
    # needs_refresh=False, expiration=future, reason="Valid"
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(False, future, "Valid"),
    )

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_all_valid_no_expiration_exits_0(mocker):
    """When all profiles are valid but have no expiration, sys.exit(0) is called."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=[("dev", "static")])
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(False, None, "Not an SSO profile"),
    )

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_user_cancels(mocker):
    """When user declines confirmation, sys.exit(0) is called."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.list_aws_profiles", return_value=[("dev", "sso")])
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=False)

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_refreshes_grouped_sessions(mocker):
    """Profiles sharing a session key are grouped and refreshed together."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso"), ("staging", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_session": "shared-session"},
    )
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 2, 0, ["dev", "staging"]))

    refresh_all_profiles()

    # Both profiles should be grouped under same session key
    mock_refresh.assert_called_once()
    args = mock_refresh.call_args
    assert args[0][0] == "shared-session"
    assert set(args[0][1]) == {"dev", "staging"}


@pytest.mark.unit
def test_refresh_all_profiles_profile_with_no_sso_key_skipped(mocker):
    """Profiles without sso_session or sso_start_url are not grouped for refresh."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "static")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"region": "us-east-1"},  # No sso_session or sso_start_url
    )
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session")

    refresh_all_profiles()

    mock_refresh.assert_not_called()


@pytest.mark.unit
def test_refresh_all_profiles_profile_config_none_skipped(mocker):
    """Profiles where get_profile_config returns None are skipped."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session")

    refresh_all_profiles()

    mock_refresh.assert_not_called()


@pytest.mark.unit
def test_refresh_all_profiles_uses_sso_start_url_as_key(mocker):
    """When profile has sso_start_url but no sso_session, uses URL as group key."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_start_url": "https://example.awsapps.com/start"},
    )
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)

    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 1, 0, ["dev"]))

    refresh_all_profiles()

    mock_refresh.assert_called_once()
    assert mock_refresh.call_args[0][0] == "https://example.awsapps.com/start"


@pytest.mark.unit
def test_refresh_all_profiles_multiple_sessions_multiple_calls(mocker):
    """Different session keys result in multiple _refresh_session calls."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso"), ("prod", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)

    # Different sessions for each profile
    def mock_get_config(profile_name):
        if profile_name == "dev":
            return {"sso_session": "dev-session"}
        return {"sso_session": "prod-session"}

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", side_effect=mock_get_config)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)
    mock_refresh = mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 1, 0, ["dev"]))

    refresh_all_profiles()

    assert mock_refresh.call_count == 2


@pytest.mark.unit
def test_refresh_all_profiles_summary_shows_failures(mocker, capsys):
    """Summary shows failure count when some profiles fail."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_session": "s"},
    )
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)
    # Returns 0 verified, 1 failed
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(False, 0, 1, []))

    # Should not raise
    refresh_all_profiles()


@pytest.mark.unit
def test_refresh_all_profiles_valid_profiles_prints_table(mocker):
    """When profiles are all valid with expiration, prints a status table without error."""
    future = datetime.now(timezone.utc) + timedelta(hours=6)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso"), ("prod", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(False, future, "Valid"),
    )

    with pytest.raises(SystemExit) as exc_info:
        refresh_all_profiles()

    assert exc_info.value.code == 0


@pytest.mark.unit
def test_refresh_all_profiles_summary_no_failures(mocker):
    """Summary shows only success count when all profiles refresh successfully."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_session": "s"},
    )
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 1, 0, ["dev"]))

    # Should not raise
    refresh_all_profiles()


@pytest.mark.unit
def test_refresh_session_verified_and_failed_counts_tracked(mocker):
    """Verified/failed counts from _refresh_session are accumulated correctly."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso"), ("prod", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)

    def mock_config(name):
        return {"sso_session": "shared"}

    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_profile_config", side_effect=mock_config)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)
    # Both profiles share same session so _refresh_session called once with (True, 1, 1)
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 1, 1, ["dev"]))

    # Should complete without error
    refresh_all_profiles()


# ---------------------------------------------------------------------------
# _update_default_credentials_after_refresh
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_update_default_credentials_no_config_skips(mocker):
    """When no default_credentials_profile is configured, does nothing."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value=None)
    mock_write = mocker.patch("cli_tool.commands.aws_login.commands.refresh.write_default_credentials")

    _update_default_credentials_after_refresh(["dev", "prod"])

    mock_write.assert_not_called()


@pytest.mark.unit
def test_update_default_credentials_profile_not_refreshed_skips(mocker):
    """When default profile was not among the refreshed profiles, does nothing."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value="staging")
    mock_write = mocker.patch("cli_tool.commands.aws_login.commands.refresh.write_default_credentials")

    _update_default_credentials_after_refresh(["dev", "prod"])

    mock_write.assert_not_called()


@pytest.mark.unit
def test_update_default_credentials_rewrites_on_match(mocker):
    """When default profile was refreshed, re-writes [default] credentials."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value="dev")
    mock_write = mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.write_default_credentials",
        return_value={"expiration": "2026-12-31T00:00:00Z"},
    )

    _update_default_credentials_after_refresh(["dev", "prod"])

    mock_write.assert_called_once_with("dev")


@pytest.mark.unit
def test_update_default_credentials_handles_write_failure(mocker):
    """When write_default_credentials returns None, does not raise."""
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value="dev")
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.write_default_credentials", return_value=None)

    # Should not raise
    _update_default_credentials_after_refresh(["dev"])


@pytest.mark.unit
def test_refresh_all_profiles_updates_default_after_refresh(mocker):
    """After a successful refresh, [default] credentials are updated if the default profile was refreshed."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_session": "my-session"},
    )
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value="dev")
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(True, 1, 0, ["dev"]))
    mock_write = mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.write_default_credentials",
        return_value={"expiration": "2026-12-31T00:00:00Z"},
    )

    refresh_all_profiles()

    mock_write.assert_called_once_with("dev")


@pytest.mark.unit
def test_refresh_all_profiles_no_default_update_when_all_fail(mocker):
    """When all profiles fail to refresh (success_count=0), [default] is not updated."""
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.list_aws_profiles",
        return_value=[("dev", "sso")],
    )
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.check_profile_needs_refresh",
        return_value=(True, None, "Expired"),
    )
    mocker.patch("click.confirm", return_value=True)
    mocker.patch(
        "cli_tool.commands.aws_login.commands.refresh.get_profile_config",
        return_value={"sso_session": "my-session"},
    )
    mocker.patch("cli_tool.commands.aws_login.commands.refresh.get_config_value", return_value="dev")
    mocker.patch("cli_tool.commands.aws_login.commands.refresh._refresh_session", return_value=(False, 0, 1, []))
    mock_write = mocker.patch("cli_tool.commands.aws_login.commands.refresh.write_default_credentials")

    refresh_all_profiles()

    mock_write.assert_not_called()


# ---------------------------------------------------------------------------
# _silent_refresh_profiles
# ---------------------------------------------------------------------------

_REFRESH = "cli_tool.commands.aws_login.commands.refresh"


def _patch_silent(mocker, configs, working):
    """configs: profile -> config dict; working: profiles whose silent renewal succeeds."""
    mocker.patch(f"{_REFRESH}.get_profile_config", side_effect=lambda name: configs.get(name))
    return mocker.patch(
        f"{_REFRESH}.verify_credentials",
        side_effect=lambda name: {"account": "1"} if name in working else None,
    )


@pytest.mark.unit
def test_silent_refresh_renews_profiles_whose_session_is_alive(mocker):
    mock_verify = _patch_silent(
        mocker,
        {"dev": {"sso_session": "corp"}, "prod": {"sso_session": "corp"}},
        working={"dev", "prod"},
    )

    renewed, failing = _silent_refresh_profiles([("dev", "Expired"), ("prod", "Expiring in 3 minutes")])

    assert renewed == ["dev", "prod"]
    assert failing == []
    assert mock_verify.call_count == 2


@pytest.mark.unit
def test_silent_refresh_reports_profiles_that_need_a_login_with_their_reason(mocker):
    _patch_silent(mocker, {"dev": {"sso_session": "corp"}}, working=set())

    renewed, failing = _silent_refresh_profiles([("dev", "Expired")])

    assert renewed == []
    assert failing == [("dev", "Expired")]


@pytest.mark.unit
def test_silent_refresh_skips_rest_of_a_dead_session(mocker):
    """Profiles of one SSO session share its token: after the first failure
    the others fail too, so they must not be tried (each try costs a timeout)."""
    mock_verify = _patch_silent(
        mocker,
        {
            "a": {"sso_session": "corp"},
            "b": {"sso_session": "corp"},
            "c": {"sso_session": "corp"},
            "d": {"sso_session": "personal"},
        },
        working={"d"},
    )

    renewed, failing = _silent_refresh_profiles([(p, "Expired") for p in "abcd"])

    assert renewed == ["d"]
    assert [p for p, _ in failing] == ["a", "b", "c"]
    # only the probe of each session was tried; b and c never were
    assert sorted(c.args[0] for c in mock_verify.call_args_list) == ["a", "d"]


@pytest.mark.unit
def test_silent_refresh_groups_legacy_profiles_by_start_url(mocker):
    mock_verify = _patch_silent(
        mocker,
        {"a": {"sso_start_url": "https://x"}, "b": {"sso_start_url": "https://x"}},
        working=set(),
    )

    _, failing = _silent_refresh_profiles([("a", "Expired"), ("b", "Expired")])

    assert [p for p, _ in failing] == ["a", "b"]
    assert mock_verify.call_count == 1


@pytest.mark.unit
def test_silent_refresh_without_session_key_tries_every_profile(mocker):
    mock_verify = _patch_silent(mocker, {}, working=set())

    _, failing = _silent_refresh_profiles([("a", "Expired"), ("b", "Expired")])

    assert [p for p, _ in failing] == ["a", "b"]
    assert mock_verify.call_count == 2


@pytest.mark.unit
def test_silent_refresh_probes_a_session_before_running_the_rest_of_it(mocker):
    """The first profile of a session must finish before its siblings start:
    it renews the shared SSO access token, which siblings then reuse."""
    import threading

    lock = threading.Lock()
    done = []
    started_before_probe_done = []

    def fake_verify(name):
        with lock:
            if name != "a" and "a" not in done:
                started_before_probe_done.append(name)
        if name == "a":
            with lock:
                done.append("a")
        return {"account": "1"}

    mocker.patch(
        f"{_REFRESH}.get_profile_config",
        side_effect=lambda name: {"sso_session": "corp"},
    )
    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    renewed, failing = _silent_refresh_profiles([(p, "Expired") for p in "abcd"])

    assert started_before_probe_done == []
    assert renewed == ["a", "b", "c", "d"]
    assert failing == []


@pytest.mark.unit
def test_silent_refresh_runs_profiles_of_a_live_session_in_parallel(mocker):
    """Three siblings meet at a barrier: it only opens if they truly run
    concurrently, so a serial implementation fails (the barrier times out)."""
    import threading

    barrier = threading.Barrier(3, timeout=5)

    def fake_verify(name):
        if name == "a":  # the probe runs alone
            return {"account": "1"}
        barrier.wait()
        return {"account": "1"}

    mocker.patch(f"{_REFRESH}.get_profile_config", side_effect=lambda name: {"sso_session": "corp"})
    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    renewed, failing = _silent_refresh_profiles([(p, "Expired") for p in "abcd"])

    assert renewed == ["a", "b", "c", "d"]
    assert failing == []


@pytest.mark.unit
def test_silent_refresh_keeps_input_order_in_results(mocker):
    """Results are reported in input order regardless of which thread ends first."""
    import time

    def fake_verify(name):
        time.sleep(0.05 if name in ("a", "b") else 0)
        return {"account": "1"} if name != "c" else None

    mocker.patch(
        f"{_REFRESH}.get_profile_config",
        side_effect=lambda name: {"sso_session": f"s-{name}"},  # one session each => all parallel probes
    )
    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    renewed, failing = _silent_refresh_profiles([(p, f"r-{p}") for p in "abcd"])

    assert renewed == ["a", "b", "d"]
    assert failing == [("c", "r-c")]


@pytest.mark.unit
def test_silent_refresh_treats_an_exception_as_a_failed_renewal(mocker):
    def fake_verify(name):
        if name == "boom":
            raise RuntimeError("aws exploded")
        return {"account": "1"}

    mocker.patch(f"{_REFRESH}.get_profile_config", side_effect=lambda name: {"sso_session": f"s-{name}"})
    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    renewed, failing = _silent_refresh_profiles([("ok", "x"), ("boom", "y")])

    assert renewed == ["ok"]
    assert failing == [("boom", "y")]


@pytest.mark.unit
def test_silent_refresh_with_no_profiles_returns_empty():
    assert _silent_refresh_profiles([]) == ([], [])


# ---------------------------------------------------------------------------
# _verify_in_parallel / _verify_session_profiles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_in_parallel_returns_results_in_input_order(mocker):
    import time

    def fake_verify(name):
        time.sleep(0.05 if name == "a" else 0)  # the first one finishes last
        return {"account": "1"} if name != "b" else None

    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    assert _verify_in_parallel(["a", "b", "c"]) == [True, False, True]


@pytest.mark.unit
def test_verify_in_parallel_handles_empty_and_single(mocker):
    mock_verify = mocker.patch(f"{_REFRESH}.verify_credentials", return_value={"account": "1"})

    assert _verify_in_parallel([]) == []
    assert _verify_in_parallel(["only"]) == [True]
    assert mock_verify.call_count == 1


@pytest.mark.unit
def test_verify_in_parallel_counts_an_exception_as_failure_of_that_profile(mocker):
    def fake_verify(name):
        if name == "boom":
            raise RuntimeError("aws exploded")
        return {"account": "1"}

    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    assert _verify_in_parallel(["ok", "boom", "ok2"]) == [True, False, True]


@pytest.mark.unit
def test_verify_in_parallel_actually_runs_concurrently(mocker):
    """Three checks meet at a barrier that only opens if they overlap."""
    import threading

    barrier = threading.Barrier(3, timeout=5)

    def fake_verify(name):
        barrier.wait()
        return {"account": "1"}

    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    assert _verify_in_parallel(["a", "b", "c"]) == [True, True, True]


@pytest.mark.unit
def test_verify_session_profiles_prints_in_profile_order_and_counts(mocker):
    import time

    def fake_verify(name):
        time.sleep(0.05 if name == "a" else 0)
        return {"account": "1"} if name != "b" else None

    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)
    mock_console = mocker.patch(f"{_REFRESH}.console")

    verified, failed, names = _verify_session_profiles(["a", "b", "c"])

    assert (verified, failed, names) == (2, 1, ["a", "c"])
    printed = [c.args[0] for c in mock_console.print.call_args_list]
    assert printed == [
        "[green]✓ Session refreshed successfully[/green]",
        "  ✓ a",
        "  ✗ b (verification failed)",
        "  ✓ c",
    ]


@pytest.mark.unit
def test_classify_profiles_passes_cached_only_to_the_check(mocker):
    check = mocker.patch(f"{_REFRESH}.check_profile_needs_refresh", return_value=(True, None, "No valid credentials found"))

    to_refresh, valid = _classify_profiles([("dev", "sso")], cached_only=True)

    check.assert_called_once_with("dev", cached_only=True)
    assert to_refresh == [("dev", "No valid credentials found")]
    assert valid == []


@pytest.mark.unit
def test_classify_profiles_defaults_to_the_live_check(mocker):
    check = mocker.patch(f"{_REFRESH}.check_profile_needs_refresh", return_value=(False, None, "Valid"))

    _classify_profiles([("dev", "sso")])

    check.assert_called_once_with("dev", cached_only=False)


@pytest.mark.unit
def test_two_silent_refreshes_never_overlap(mocker):
    """Renewals can share a single-use refresh token, so they are serialized."""
    import threading
    import time

    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_verify(name):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.1)
        with lock:
            active -= 1
        return {"account": "1"}

    mocker.patch(f"{_REFRESH}.get_profile_config", side_effect=lambda name: {"sso_session": f"s-{name}"})
    mocker.patch(f"{_REFRESH}.verify_credentials", side_effect=fake_verify)

    threads = [threading.Thread(target=_silent_refresh_profiles, args=([(name, "Expired")],)) for name in ("a", "b", "c")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak == 1
