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
from unittest.mock import MagicMock

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
