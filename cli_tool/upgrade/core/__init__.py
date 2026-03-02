"""Upgrade core functionality."""

from cli_tool.upgrade.core.downloader import download_binary, verify_binary
from cli_tool.upgrade.core.installer import replace_binary
from cli_tool.upgrade.core.platform import detect_platform, get_binary_name, get_executable_path
from cli_tool.upgrade.core.version import get_current_version, get_latest_release

__all__ = [
    "download_binary",
    "verify_binary",
    "replace_binary",
    "detect_platform",
    "get_binary_name",
    "get_executable_path",
    "get_current_version",
    "get_latest_release",
]
