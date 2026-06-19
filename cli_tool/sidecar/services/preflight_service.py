"""Preflight checks — verifies system prerequisites."""

import platform
import subprocess
from typing import Any

from cli_tool.commands.aws_login.core.config import list_aws_profiles
from cli_tool.core.utils.config_manager import get_config_file


def _run(cmd: list[str], timeout: int = 2) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=platform.system() == "Windows")
        return True, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return False, "not found"
    except subprocess.TimeoutExpired:
        return False, "timeout"


def check_preflight() -> dict[str, Any]:
    result: dict[str, Any] = {}

    # aws CLI
    ok, out = _run(["aws", "--version"])
    version = None
    if ok and out.startswith("aws-cli/"):
        version = out.split()[0].replace("aws-cli/", "")
    result["aws_cli"] = {"ok": ok, "version": version}

    # session-manager-plugin
    ok, _ = _run(["session-manager-plugin"])
    result["session_manager_plugin"] = {
        "ok": ok,
        "install_url": "https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html",
    }

    # socat (Linux/macOS only — Windows uses netsh which is built-in)
    if platform.system() == "Windows":
        result["socat"] = {"ok": True, "version": "n/a (Windows uses netsh)"}
    else:
        ok, out = _run(["socat", "-V"])
        version = None
        if ok:
            for line in out.splitlines():
                if line.startswith("socat version"):
                    version = line.split()[-1]
                    break
        result["socat"] = {"ok": ok, "version": version}

    # SSO configured
    try:
        profiles = list_aws_profiles()
        sso_count = sum(1 for _, src in profiles if src in ("sso", "both"))
        result["sso_configured"] = {"ok": sso_count > 0, "profiles": sso_count}
    except Exception:
        result["sso_configured"] = {"ok": False, "profiles": 0}

    # config exists
    config_path = get_config_file()
    result["config_exists"] = {"ok": config_path.exists(), "path": str(config_path)}

    return result
