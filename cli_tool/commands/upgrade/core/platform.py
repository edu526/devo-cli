"""Platform detection for upgrade functionality."""

import platform
import shutil
import sys
from pathlib import Path


def detect_platform():
    """Detect current platform and architecture"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Map system names
    if system == "darwin":
        system = "darwin"
    elif system == "linux":
        system = "linux"
    elif system == "windows":
        system = "windows"
    else:
        return None

    # Map architecture names
    if machine in ["x86_64", "amd64"]:
        arch = "amd64"
    elif machine in ["arm64", "aarch64"]:
        arch = "arm64"
    else:
        return None

    return system, arch


def get_binary_name(system, arch):
    """Get binary name for platform"""
    if system == "windows":
        return f"devo-{system}-{arch}.zip"
    elif system == "darwin":
        # macOS uses tarball (onedir mode)
        return f"devo-{system}-{arch}.tar.gz"
    else:
        # Linux uses single binary (onefile mode)
        return f"devo-{system}-{arch}"


def get_executable_path():
    """Get path of current executable"""
    # Check if running as PyInstaller bundle
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable)
        system = platform.system().lower()

        # Windows/macOS onedir: return the parent directory
        if system in ["windows", "darwin"] and exe_path.name in ["devo.exe", "devo"]:
            return exe_path.parent
        # Linux onefile: return the executable itself
        return exe_path

    # Running as Python script - find devo in PATH
    devo_path = shutil.which("devo")
    if devo_path:
        return Path(devo_path)

    return None
