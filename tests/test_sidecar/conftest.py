"""Shared fixtures for the sidecar tests."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_login_coordinator(request, monkeypatch):
    """The login handler keeps module-level state (logins in flight, backoff)
    and, around a login, runs real silent renewals through the `aws` CLI.

    Reset the state for every test, and outside the handler's own tests
    replace those AWS calls: no silent renewal is possible (every login goes
    to the — mocked — browser flow, as the tests expect) and nothing is
    renewed afterwards. The user's own `aws_login.auto_open_browser` setting
    must not decide what a test sees either: the default (on) applies.
    """
    from cli_tool.sidecar.services import login_coordinator

    login_coordinator._reset_for_tests()
    monkeypatch.setattr(login_coordinator, "auto_open_browser", lambda: True)
    if "test_login_coordinator" not in str(request.node.fspath):
        monkeypatch.setattr(login_coordinator, "_renewable_without_browser", lambda profile, sso_session: False)
        monkeypatch.setattr(login_coordinator, "_renew_session_profiles", lambda key: [])
    yield
    login_coordinator._reset_for_tests()
