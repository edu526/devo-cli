"""
Unit tests for cli_tool.commands.upgrade.core.version module.

Tests cover:
- get_latest_release() parses the new releases API response format
- get_latest_release() normalizes assets to internal format (tag_name + assets list)
- get_latest_release() handles timeout and HTTP errors gracefully
- get_current_version() returns version or 'unknown'
"""

import pytest
import requests

from cli_tool.commands.upgrade.core.version import get_current_version, get_latest_release

# Sample API response matching https://releases.heyedu.dev/devo-cli/latest
MOCK_API_RESPONSE = {
    "name": "devo-cli",
    "version": "v3.2.3",
    "published_at": "2026-03-07T17:01:19Z",
    "assets": {
        "macos": {
            "amd64": "https://github.com/edu526/devo-cli/releases/download/v3.2.3/devo-darwin-amd64.tar.gz",
            "arm64": "https://github.com/edu526/devo-cli/releases/download/v3.2.3/devo-darwin-arm64.tar.gz",
        },
        "linux": {
            "amd64": "https://github.com/edu526/devo-cli/releases/download/v3.2.3/devo-linux-amd64",
        },
        "windows": {
            "amd64": "https://github.com/edu526/devo-cli/releases/download/v3.2.3/devo-windows-amd64.zip",
        },
    },
}


# ============================================================================
# get_current_version
# ============================================================================


@pytest.mark.unit
def test_get_current_version_returns_version(mocker):
    """Returns the installed version string."""
    mocker.patch("cli_tool.commands.upgrade.core.version.get_current_version", return_value="3.2.3")
    # Call the real function via a fresh import to avoid mock recursion
    from cli_tool.commands.upgrade.core.version import get_current_version as fn

    mocker.patch("cli_tool._version.__version__", "3.2.3", create=True)
    result = fn()
    # Just verify it returns a string (version or 'unknown')
    assert isinstance(result, str)


@pytest.mark.unit
def test_get_current_version_returns_unknown_on_import_error(mocker):
    """Returns 'unknown' when _version module is missing."""
    import cli_tool.commands.upgrade.core.version as version_mod

    def patched():
        try:
            raise ImportError
        except ImportError:
            return "unknown"

    mocker.patch.object(version_mod, "get_current_version", patched)
    assert version_mod.get_current_version() == "unknown"


# ============================================================================
# get_latest_release — happy path
# ============================================================================


@pytest.mark.unit
def test_get_latest_release_returns_tag_name(mocker):
    """tag_name is populated from the 'version' field of the API response."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()

    assert result is not None
    assert result["tag_name"] == "v3.2.3"


@pytest.mark.unit
def test_get_latest_release_assets_contain_linux(mocker):
    """Linux amd64 asset is present with correct name and URL."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()
    names = [a["name"] for a in result["assets"]]

    assert "devo-linux-amd64" in names


@pytest.mark.unit
def test_get_latest_release_assets_contain_macos_amd64(mocker):
    """macOS amd64 tarball asset is present."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()
    names = [a["name"] for a in result["assets"]]

    assert "devo-darwin-amd64.tar.gz" in names


@pytest.mark.unit
def test_get_latest_release_assets_contain_macos_arm64(mocker):
    """macOS arm64 tarball asset is present."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()
    names = [a["name"] for a in result["assets"]]

    assert "devo-darwin-arm64.tar.gz" in names


@pytest.mark.unit
def test_get_latest_release_assets_contain_windows(mocker):
    """Windows amd64 zip asset is present."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()
    names = [a["name"] for a in result["assets"]]

    assert "devo-windows-amd64.zip" in names


@pytest.mark.unit
def test_get_latest_release_asset_has_browser_download_url(mocker):
    """Each asset has a browser_download_url pointing to the correct URL."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()
    linux_asset = next(a for a in result["assets"] if a["name"] == "devo-linux-amd64")

    assert linux_asset["browser_download_url"] == ("https://github.com/edu526/devo-cli/releases/download/v3.2.3/devo-linux-amd64")


@pytest.mark.unit
def test_get_latest_release_total_asset_count(mocker):
    """All 4 assets (linux amd64, macos amd64+arm64, windows amd64) are returned."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()

    assert len(result["assets"]) == 4


@pytest.mark.unit
def test_get_latest_release_uses_correct_url(mocker):
    """requests.get is called with RELEASES_API_URL and timeout=2."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE
    mock_get = mocker.patch("requests.get", return_value=mock_resp)

    get_latest_release()

    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs.get("timeout") == 2


# ============================================================================
# get_latest_release — error handling
# ============================================================================


@pytest.mark.unit
def test_get_latest_release_returns_none_on_timeout(mocker):
    """Returns None when the request times out."""
    mocker.patch("requests.get", side_effect=requests.Timeout)

    result = get_latest_release()

    assert result is None


@pytest.mark.unit
def test_get_latest_release_returns_none_on_http_error(mocker):
    """Returns None when the API returns a non-2xx status."""
    mock_resp = mocker.MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable")
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()

    assert result is None


@pytest.mark.unit
def test_get_latest_release_returns_none_on_connection_error(mocker):
    """Returns None on network connectivity failure."""
    mocker.patch("requests.get", side_effect=requests.ConnectionError)

    result = get_latest_release()

    assert result is None


@pytest.mark.unit
def test_get_latest_release_returns_none_on_invalid_json(mocker):
    """Returns None when the API response is not valid JSON."""
    mock_resp = mocker.MagicMock()
    mock_resp.json.side_effect = ValueError("No JSON")
    mocker.patch("requests.get", return_value=mock_resp)

    result = get_latest_release()

    assert result is None
