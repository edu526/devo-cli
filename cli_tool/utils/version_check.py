import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests


def get_cache_file():
    """Get path to version check cache file"""
    cache_dir = Path.home() / ".devo"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / "version_check.json"


def get_current_version():
    """Get current installed version"""
    try:
        from cli_tool._version import __version__

        return __version__
    except ImportError:
        return None


def get_latest_version_from_github():
    """Fetch latest version from GitHub API"""
    try:
        from cli_tool.config import GITHUB_API_RELEASES_URL

        response = requests.get(GITHUB_API_RELEASES_URL, timeout=2)
        response.raise_for_status()
        data = response.json()
        return data.get("tag_name", "").lstrip("v")
    except Exception:
        return None


def read_cache():
    """Read cached version check data"""
    cache_file = get_cache_file()
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception:
        return None


def write_cache(latest_version):
    """Write version check data to cache"""
    cache_file = get_cache_file()
    try:
        data = {
            "latest_version": latest_version,
            "checked_at": datetime.now().isoformat(),
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def clear_cache():
    """Clear version check cache to force a new check"""
    cache_file = get_cache_file()
    try:
        if cache_file.exists():
            cache_file.unlink()
            return True
    except Exception:
        pass
    return False


def parse_version(version_str):
    """Parse version string into tuple of integers for comparison"""
    try:
        # Remove 'v' prefix if present and any dev/pre-release suffixes
        version_str = version_str.lstrip("v").split("+")[0].split("-")[0].split(".dev")[0]
        parts = version_str.split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    except Exception:
        return (0, 0, 0)


def is_cache_valid(cache_data):
    """Check if cache is still valid (less than 24 hours old)"""
    if not cache_data or "checked_at" not in cache_data:
        return False

    try:
        checked_at = datetime.fromisoformat(cache_data["checked_at"])
        age = datetime.now() - checked_at
        return age < timedelta(hours=24)
    except Exception:
        return False


def check_for_updates():
    """
    Check if a new version is available.
    Returns tuple: (has_update, current_version, latest_version)
    """
    # Skip if disabled in config
    from cli_tool.utils.config_manager import get_config_value

    if not get_config_value("version_check.enabled", True):
        return False, None, None

    # Skip if environment variable is set
    if os.environ.get("DEVO_SKIP_VERSION_CHECK") == "1":
        return False, None, None

    current_version = get_current_version()
    if not current_version:
        return False, None, None

    # Try to read from cache first
    cache_data = read_cache()
    if cache_data and is_cache_valid(cache_data):
        latest_version = cache_data.get("latest_version")
    else:
        # Fetch from GitHub
        latest_version = get_latest_version_from_github()
        if latest_version:
            write_cache(latest_version)

    if not latest_version:
        return False, current_version, None

    # Compare versions using semantic versioning
    current_parsed = parse_version(current_version)
    latest_parsed = parse_version(latest_version)

    has_update = latest_parsed > current_parsed

    return has_update, current_version, latest_version


def show_update_notification():
    """Show update notification if available"""
    try:
        has_update, current_version, latest_version = check_for_updates()

        if has_update and latest_version:
            print()
            print(f"✨ New version available: v{latest_version} (current: v{current_version})")
            print("   Run 'devo upgrade' to update")
    except Exception:
        # Silently fail - don't interrupt user's workflow
        pass
