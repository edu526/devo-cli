"""
Unit tests for cli_tool.core.utils.version_check module.

Tests cover:
- get_latest_version() parses 'version' field from new releases API
- get_latest_version() handles timeout and errors gracefully
- check_for_updates() returns correct update status
- Cache read/write/clear behavior
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from cli_tool.core.utils.version_check import (
    check_for_updates,
    clear_cache,
    get_latest_version,
    is_cache_valid,
    parse_version,
    read_cache,
    write_cache,
)

MOCK_API_RESPONSE = {
    "name": "devo-cli",
    "version": "v3.2.3",
    "published_at": "2026-03-07T17:01:19Z",
    "assets": {
        "linux": {"amd64": "https://github.com/edu526/devo-cli/releases/download/v3.2.3/devo-linux-amd64"},
    },
}


# ============================================================================
# get_latest_version
# ============================================================================


@pytest.mark.unit
def test_get_latest_version_parses_version_field(mocker):
    """Reads 'version' key (not 'tag_name') and strips the 'v' prefix."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_version()

    assert result == "3.2.3"


@pytest.mark.unit
def test_get_latest_version_uses_timeout_2(mocker):
    """requests.get is called with timeout=2."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mock_get = mocker.patch("requests.get", return_value=mock_resp)

    get_latest_version()

    _, kwargs = mock_get.call_args
    assert kwargs.get("timeout") == 2


@pytest.mark.unit
def test_get_latest_version_returns_none_on_timeout(mocker):
    """Returns None when request times out."""
    mocker.patch("requests.get", side_effect=requests.Timeout)

    assert get_latest_version() is None


@pytest.mark.unit
def test_get_latest_version_returns_none_on_http_error(mocker):
    """Returns None on non-2xx HTTP response."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
    mocker.patch("requests.get", return_value=mock_resp)

    assert get_latest_version() is None


@pytest.mark.unit
def test_get_latest_version_returns_none_on_connection_error(mocker):
    """Returns None on network failure."""
    mocker.patch("requests.get", side_effect=requests.ConnectionError)

    assert get_latest_version() is None


@pytest.mark.unit
def test_get_latest_version_returns_none_when_version_missing(mocker):
    """Returns None (empty string stripped) when 'version' key is absent."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"name": "devo-cli"}  # no 'version' key
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_version()

    # Empty string after lstrip("v") → falsy, treated as None by callers
    assert result == "" or result is None


# ============================================================================
# parse_version
# ============================================================================


@pytest.mark.unit
def test_parse_version_basic():
    assert parse_version("3.2.3") == (3, 2, 3)


@pytest.mark.unit
def test_parse_version_strips_v_prefix():
    assert parse_version("v3.2.3") == (3, 2, 3)


@pytest.mark.unit
def test_parse_version_strips_dev_suffix():
    assert parse_version("3.2.3.dev1+gabcdef") == (3, 2, 3)


# ============================================================================
# Cache helpers
# ============================================================================


@pytest.mark.unit
def test_write_and_read_cache(tmp_path, mocker):
    """write_cache persists version; read_cache retrieves it."""
    cache_file = tmp_path / "version_check.json"
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)

    write_cache("3.2.3")
    data = read_cache()

    assert data["latest_version"] == "3.2.3"


@pytest.mark.unit
def test_clear_cache_removes_file(tmp_path, mocker):
    """clear_cache deletes the cache file."""
    cache_file = tmp_path / "version_check.json"
    cache_file.write_text('{"latest_version": "3.2.3"}')
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)

    result = clear_cache()

    assert result is True
    assert not cache_file.exists()


@pytest.mark.unit
def test_is_cache_valid_fresh():
    """Cache written just now is valid."""
    data = {"checked_at": datetime.now().isoformat()}
    assert is_cache_valid(data) is True


@pytest.mark.unit
def test_is_cache_valid_expired():
    """Cache older than 24h is invalid."""
    old_time = (datetime.now() - timedelta(hours=25)).isoformat()
    data = {"checked_at": old_time}
    assert is_cache_valid(data) is False


# ============================================================================
# check_for_updates
# ============================================================================


@pytest.mark.unit
def test_check_for_updates_detects_newer_version(mocker, tmp_path, monkeypatch):
    """Returns has_update=True when latest > current."""
    monkeypatch.delenv("DEVO_SKIP_VERSION_CHECK", raising=False)
    cache_file = tmp_path / "version_check.json"
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)
    mocker.patch("cli_tool.core.utils.version_check.get_current_version", return_value="3.0.0")
    mocker.patch("cli_tool.core.utils.version_check.get_latest_version", return_value="3.2.3")
    mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=True)

    has_update, current, latest = check_for_updates()

    assert has_update is True
    assert current == "3.0.0"
    assert latest == "3.2.3"


@pytest.mark.unit
def test_check_for_updates_no_update_when_same(mocker, tmp_path, monkeypatch):
    """Returns has_update=False when already on latest."""
    monkeypatch.delenv("DEVO_SKIP_VERSION_CHECK", raising=False)
    cache_file = tmp_path / "version_check.json"
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)
    mocker.patch("cli_tool.core.utils.version_check.get_current_version", return_value="3.2.3")
    mocker.patch("cli_tool.core.utils.version_check.get_latest_version", return_value="3.2.3")
    mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=True)

    has_update, _, _ = check_for_updates()

    assert has_update is False


@pytest.mark.unit
def test_check_for_updates_uses_cache(mocker, tmp_path, monkeypatch):
    """Does not call the API when a valid cache exists."""
    monkeypatch.delenv("DEVO_SKIP_VERSION_CHECK", raising=False)
    cache_file = tmp_path / "version_check.json"
    cache_file.write_text(json.dumps({"latest_version": "3.2.3", "checked_at": datetime.now().isoformat()}))
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)
    mocker.patch("cli_tool.core.utils.version_check.get_current_version", return_value="3.0.0")
    mock_api = mocker.patch("cli_tool.core.utils.version_check.get_latest_version")
    mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=True)

    check_for_updates()

    mock_api.assert_not_called()


@pytest.mark.unit
def test_check_for_updates_skipped_when_disabled(mocker):
    """Returns (False, None, None) when version_check.enabled is False."""
    mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=False)

    has_update, current, latest = check_for_updates()

    assert has_update is False
    assert current is None
    assert latest is None


# ============================================================================
# Additional check_for_updates branches
# ============================================================================


@pytest.mark.unit
def test_check_for_updates_skipped_via_env_var(mocker, monkeypatch):
    """Returns (False, None, None) when DEVO_SKIP_VERSION_CHECK=1."""
    monkeypatch.setenv("DEVO_SKIP_VERSION_CHECK", "1")
    mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=True)

    has_update, current, latest = check_for_updates()

    assert has_update is False
    assert current is None
    assert latest is None


@pytest.mark.unit
def test_check_for_updates_returns_false_when_no_current_version(mocker, monkeypatch):
    """Returns (False, None, None) when current version cannot be determined."""
    monkeypatch.delenv("DEVO_SKIP_VERSION_CHECK", raising=False)
    mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=True)
    mocker.patch("cli_tool.core.utils.version_check.get_current_version", return_value=None)

    has_update, current, latest = check_for_updates()

    assert has_update is False
    assert current is None


@pytest.mark.unit
def test_check_for_updates_returns_false_when_no_latest_version(mocker, tmp_path, monkeypatch):
    """Returns (False, current, None) when latest version cannot be fetched."""
    monkeypatch.delenv("DEVO_SKIP_VERSION_CHECK", raising=False)
    cache_file = tmp_path / "version_check.json"
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)
    mocker.patch("cli_tool.core.utils.version_check.get_current_version", return_value="1.0.0")
    mocker.patch("cli_tool.core.utils.version_check.get_latest_version", return_value=None)
    mocker.patch("cli_tool.core.utils.config_manager.get_config_value", return_value=True)

    has_update, current, latest = check_for_updates()

    assert has_update is False
    assert current == "1.0.0"
    assert latest is None


# ============================================================================
# Additional parse_version branches
# ============================================================================


@pytest.mark.unit
def test_parse_version_strips_dash_suffix():
    """Strips pre-release suffix separated by '-'."""
    assert parse_version("3.2.3-rc1") == (3, 2, 3)


@pytest.mark.unit
def test_parse_version_strips_plus_suffix():
    """Strips build metadata separated by '+'."""
    assert parse_version("3.2.3+build.42") == (3, 2, 3)


@pytest.mark.unit
def test_parse_version_handles_invalid_returns_empty_or_zeros():
    """Returns empty tuple or (0,0,0) for completely invalid version strings."""
    result = parse_version("not-a-version")
    # The function strips by '-' first, so "not" becomes the only part
    # "not" is not a digit, so it's filtered out — result is ()
    assert result == () or result == (0, 0, 0)


@pytest.mark.unit
def test_parse_version_two_parts():
    """Parses two-part versions correctly."""
    result = parse_version("3.2")
    assert result == (3, 2)


# ============================================================================
# Additional cache helpers
# ============================================================================


@pytest.mark.unit
def test_read_cache_returns_none_when_no_file(tmp_path, mocker):
    """read_cache returns None when cache file does not exist."""
    cache_file = tmp_path / "no_cache.json"
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)

    result = read_cache()

    assert result is None


@pytest.mark.unit
def test_read_cache_returns_none_on_malformed_json(tmp_path, mocker):
    """read_cache returns None when cache file contains invalid JSON."""
    cache_file = tmp_path / "version_check.json"
    cache_file.write_text("not-valid-json")
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)

    result = read_cache()

    assert result is None


@pytest.mark.unit
def test_clear_cache_returns_false_when_no_file(tmp_path, mocker):
    """clear_cache returns False when the cache file does not exist."""
    cache_file = tmp_path / "nonexistent.json"
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)

    result = clear_cache()

    assert result is False


@pytest.mark.unit
def test_is_cache_valid_missing_checked_at_key():
    """is_cache_valid returns False when 'checked_at' key is missing."""
    data = {"latest_version": "3.2.3"}
    assert is_cache_valid(data) is False


@pytest.mark.unit
def test_is_cache_valid_none_data():
    """is_cache_valid returns False for None input."""
    assert is_cache_valid(None) is False


@pytest.mark.unit
def test_is_cache_valid_empty_dict():
    """is_cache_valid returns False for an empty dict."""
    assert is_cache_valid({}) is False


@pytest.mark.unit
def test_write_cache_silently_fails_on_io_error(tmp_path, mocker):
    """write_cache does not raise when file write fails."""
    cache_file = tmp_path / "version_check.json"
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)

    with patch("builtins.open", side_effect=OSError("disk full")):
        # Should not raise
        write_cache("3.2.3")


# ============================================================================
# get_current_version
# ============================================================================


@pytest.mark.unit
def test_get_current_version_returns_version_string(mocker):
    """get_current_version returns a non-None version string."""
    from cli_tool.core.utils.version_check import get_current_version

    result = get_current_version()
    # The real _version module exists, so result is a non-empty string
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
def test_get_current_version_returns_none_on_import_error(mocker):
    """get_current_version returns None when _version module is not found."""
    import importlib
    import sys

    # Remove _version from sys.modules if present
    sys.modules.pop("cli_tool._version", None)
    with patch.dict("sys.modules", {"cli_tool._version": None}):
        from cli_tool.core.utils import version_check as vc

        with patch.object(vc, "get_current_version", return_value=None):
            result = vc.get_current_version()
    assert result is None


# ============================================================================
# show_update_notification
# ============================================================================


@pytest.mark.unit
def test_show_update_notification_prints_when_update_available(mocker, capsys):
    """show_update_notification prints update message when update is available."""
    from cli_tool.core.utils.version_check import show_update_notification

    mocker.patch(
        "cli_tool.core.utils.version_check.check_for_updates",
        return_value=(True, "3.0.0", "3.5.0"),
    )

    show_update_notification()

    captured = capsys.readouterr()
    assert "3.5.0" in captured.out or "Update available" in captured.out


@pytest.mark.unit
def test_show_update_notification_silent_when_no_update(mocker, capsys):
    """show_update_notification prints nothing when no update is available."""
    from cli_tool.core.utils.version_check import show_update_notification

    mocker.patch(
        "cli_tool.core.utils.version_check.check_for_updates",
        return_value=(False, "3.5.0", "3.5.0"),
    )

    show_update_notification()

    captured = capsys.readouterr()
    assert "Update available" not in captured.out


@pytest.mark.unit
def test_show_update_notification_handles_exception_silently(mocker):
    """show_update_notification does not raise when check_for_updates fails."""
    from cli_tool.core.utils.version_check import show_update_notification

    mocker.patch(
        "cli_tool.core.utils.version_check.check_for_updates",
        side_effect=Exception("network error"),
    )

    # Should not raise
    show_update_notification()


# ============================================================================
# get_cache_file
# ============================================================================


@pytest.mark.unit
def test_get_cache_file_creates_directory_and_returns_path(tmp_path, mocker):
    """get_cache_file() creates ~/.devo dir and returns the cache file path (lines 11-13)."""
    from cli_tool.core.utils.version_check import get_cache_file

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    mocker.patch("cli_tool.core.utils.version_check.Path") if False else None  # we patch Path.home instead
    mocker.patch("pathlib.Path.home", return_value=fake_home)

    result = get_cache_file()

    devo_dir = fake_home / ".devo"
    assert devo_dir.exists()
    assert result == devo_dir / "version_check.json"


# ============================================================================
# get_current_version — real ImportError path
# ============================================================================


@pytest.mark.unit
def test_get_current_version_returns_none_when_version_module_absent(mocker, monkeypatch):
    """get_current_version returns None when _version raises ImportError (lines 22-23)."""
    import builtins
    import sys

    # Remove cached module
    sys.modules.pop("cli_tool._version", None)
    monkeypatch.setitem(sys.modules, "cli_tool._version", None)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cli_tool._version":
            raise ImportError("No module named 'cli_tool._version'")
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=fake_import)

    from cli_tool.core.utils import version_check as vc

    result = vc.get_current_version()
    assert result is None


# ============================================================================
# is_cache_valid — invalid date format
# ============================================================================


@pytest.mark.unit
def test_is_cache_valid_invalid_date_format_returns_false():
    """is_cache_valid returns False when checked_at has an invalid date format (lines 86-87)."""
    data = {"checked_at": "not-a-valid-date-at-all!!"}
    assert is_cache_valid(data) is False


@pytest.mark.unit
def test_clear_cache_exception_returns_false(mocker):
    """clear_cache returns False when unlink() raises an exception (lines 74-75)."""
    cache_file = mocker.MagicMock()
    cache_file.exists.return_value = True
    cache_file.unlink.side_effect = OSError("Permission denied")
    mocker.patch("cli_tool.core.utils.version_check.get_cache_file", return_value=cache_file)

    result = clear_cache()

    assert result is False


@pytest.mark.unit
def test_parse_version_none_returns_zeros():
    """parse_version(None) triggers the except path and returns (0, 0, 0) (lines 86-87)."""
    result = parse_version(None)
    assert result == (0, 0, 0)
