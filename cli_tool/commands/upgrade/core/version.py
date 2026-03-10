"""Version management for upgrade functionality."""

import click
import requests


def get_current_version():
    """Get current installed version"""
    try:
        from cli_tool._version import __version__

        return __version__
    except ImportError:
        return "unknown"


def get_latest_release():
    """Get latest release info from releases.heyedu.dev and normalize to internal format.

    API response shape:
    {
        "name": "devo-cli",
        "version": "v3.2.3",
        "published_at": "...",
        "assets": {
            "macos": {"amd64": "<url>", "arm64": "<url>"},
            "linux": {"amd64": "<url>"},
            "windows": {"amd64": "<url>"}
        }
    }

    Returns a dict with `tag_name` and `assets` list (browser_download_url + name)
    so the rest of the upgrade flow works without changes.
    """
    try:
        from cli_tool.config import RELEASES_API_URL

        response = requests.get(RELEASES_API_URL, timeout=2)
        response.raise_for_status()
        data = response.json()

        # Normalize to the shape the upgrade command expects
        assets = []
        for os_key, arches in data.get("assets", {}).items():
            for arch, url in arches.items():
                # Derive the filename from the URL
                name = url.split("/")[-1]
                assets.append({"name": name, "browser_download_url": url})

        return {
            "tag_name": data.get("version", ""),
            "published_at": data.get("published_at", ""),
            "assets": assets,
        }

    except requests.Timeout:
        click.echo("Error fetching latest release: request timed out", err=True)
        return None
    except Exception as e:
        click.echo(f"Error fetching latest release: {str(e)}", err=True)
        return None
