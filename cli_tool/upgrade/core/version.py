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
    """Get latest release info from GitHub"""
    try:
        from cli_tool.config import GITHUB_API_RELEASES_URL

        response = requests.get(GITHUB_API_RELEASES_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        click.echo(f"Error fetching latest release: {str(e)}", err=True)
        return None
