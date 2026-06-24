"""Diagnostic checks for `devo doctor`.

Each check returns a dict: {"name": str, "status": "ok"|"warn"|"error", "detail": str}.
Checks must never raise — wrap risky work in try/except and report failure as status.
"""

import json
import shutil
import sys

from cli_tool.core.utils.config_manager import get_config_file, load_config
from cli_tool.core.utils.version_check import get_current_version, get_latest_version

MIN_PY = (3, 12)


def _check_python() -> dict:
    version = sys.version_info
    current = (version.major, version.minor, version.micro)
    if current >= MIN_PY:
        return {"name": "Python version", "status": "ok", "detail": f"{version.major}.{version.minor}.{version.micro}"}
    if current >= (3, 10):
        return {
            "name": "Python version",
            "status": "warn",
            "detail": f"{version.major}.{version.minor}.{version.micro} (recommend >= {'.'.join(map(str, MIN_PY))})",
        }
    return {
        "name": "Python version",
        "status": "error",
        "detail": f"{version.major}.{version.minor}.{version.micro} (need >= {'.'.join(map(str, MIN_PY))})",
    }


def _check_devo_version() -> dict:
    try:
        version = get_current_version()
    except Exception as e:
        return {"name": "Devo version", "status": "error", "detail": f"could not read: {e}"}
    if not version or version == "unknown":
        return {"name": "Devo version", "status": "warn", "detail": "unknown (install via pip or 'devo upgrade')"}
    return {"name": "Devo version", "status": "ok", "detail": f"v{version}"}


def _check_releases_endpoint() -> dict:
    try:
        latest = get_latest_version()
    except Exception as e:
        return {"name": "Releases API", "status": "error", "detail": f"request failed: {e}"}
    if not latest:
        return {"name": "Releases API", "status": "warn", "detail": "reachable but no version returned"}
    return {"name": "Releases API", "status": "ok", "detail": f"latest v{latest}"}


def _check_config() -> dict:
    path = get_config_file()
    if not path.exists():
        return {"name": "Config file", "status": "warn", "detail": f"missing: {path} (will be created on first run)"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        return {"name": "Config file", "status": "error", "detail": f"invalid JSON at {path}: {e}"}
    except OSError as e:
        return {"name": "Config file", "status": "error", "detail": f"unreadable: {e}"}
    return {"name": "Config file", "status": "ok", "detail": str(path)}


def _check_config_writable() -> dict:
    path = get_config_file()
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".devo-doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        return {"name": "Config writable", "status": "error", "detail": f"cannot write to {parent}: {e}"}
    return {"name": "Config writable", "status": "ok", "detail": str(parent)}


def _check_aws_cli() -> dict:
    path = shutil.which("aws")
    if not path:
        return {
            "name": "AWS CLI",
            "status": "warn",
            "detail": "not installed (required for aws-login, dynamodb, eventbridge, ssm, codeartifact)",
        }
    return {"name": "AWS CLI", "status": "ok", "detail": path}


def _check_git() -> dict:
    path = shutil.which("git")
    if not path:
        return {
            "name": "Git",
            "status": "warn",
            "detail": "not installed (required for commit, code-reviewer)",
        }
    return {"name": "Git", "status": "ok", "detail": path}


def _check_aws_credentials() -> dict:
    from cli_tool.core.utils.aws import verify_aws_credentials

    try:
        account, arn = verify_aws_credentials()
    except Exception as e:
        return {"name": "AWS credentials", "status": "error", "detail": f"check failed: {e}"}
    if not account:
        return {
            "name": "AWS credentials",
            "status": "warn",
            "detail": "not configured (run 'devo aws-login' or set AWS_PROFILE / AWS_ACCESS_KEY_ID)",
        }
    return {"name": "AWS credentials", "status": "ok", "detail": f"account {account}"}


def _check_bedrock_config() -> dict:
    try:
        config = load_config()
    except Exception as e:
        return {"name": "Bedrock config", "status": "error", "detail": f"could not load: {e}"}
    bedrock = config.get("bedrock") or {}
    model_id = bedrock.get("model_id")
    region = bedrock.get("region")
    if not model_id or not region:
        return {
            "name": "Bedrock config",
            "status": "error",
            "detail": f"missing model_id or region: model_id={model_id!r}, region={region!r}",
        }
    return {"name": "Bedrock config", "status": "ok", "detail": f"{model_id} ({region})"}


_CHECK_NAMES = [
    "_check_python",
    "_check_devo_version",
    "_check_releases_endpoint",
    "_check_config",
    "_check_config_writable",
    "_check_aws_cli",
    "_check_git",
    "_check_aws_credentials",
    "_check_bedrock_config",
]


def run_checks() -> list[dict]:
    """Run all diagnostic checks and return their results. Never raises.

    Checks are resolved by name each iteration so monkey-patching in tests works.
    """
    results = []
    for name in _CHECK_NAMES:
        check = globals().get(name)
        if check is None:
            results.append({"name": name, "status": "error", "detail": "check not found"})
            continue
        try:
            results.append(check())
        except Exception as e:
            display_name = name.removeprefix("_check_").replace("_", " ")
            results.append({"name": display_name, "status": "error", "detail": f"unexpected: {e}"})
    return results
