"""PostHog telemetry for Devo CLI — tracks usage and errors anonymously."""

import os
import platform
import sys
import threading
import uuid
from pathlib import Path

import posthog


def _get_telemetry_id_file() -> Path:
    return Path.home() / ".devo" / ".telemetry_id"


def _get_or_create_anonymous_id() -> str:
    """Return a stable anonymous UUID for this install."""
    id_file = _get_telemetry_id_file()
    try:
        if id_file.exists():
            return id_file.read_text().strip()
        anon_id = str(uuid.uuid4())
        id_file.parent.mkdir(exist_ok=True)
        id_file.write_text(anon_id)
        return anon_id
    except Exception:
        return "anonymous"


def is_enabled() -> bool:
    """Return True if telemetry is enabled."""
    if os.environ.get("DEVO_NO_TELEMETRY") == "1":
        return False
    try:
        from cli_tool.core.utils.config_manager import get_config_value

        return bool(get_config_value("telemetry.enabled", True))
    except Exception:
        return True


def _log(msg: str) -> None:
    if os.environ.get("DEVO_TELEMETRY_DEBUG") == "1":
        print(f"[telemetry] {msg}", file=sys.stderr)


def _get_common_properties() -> dict:
    try:
        from cli_tool._version import __version__ as version
    except ImportError:
        version = "unknown"

    return {
        "version": version,
        "os": platform.system(),
        "os_version": platform.release(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "arch": platform.machine(),
    }


def _send(event: str, properties: dict) -> None:
    """Fire-and-forget: send event to PostHog in a daemon thread."""
    if not is_enabled():
        _log("telemetry disabled, skipping event")
        return

    def _do_send():
        try:
            from cli_tool.config import POSTHOG_API_KEY, POSTHOG_HOST

            posthog.api_key = POSTHOG_API_KEY
            posthog.host = POSTHOG_HOST
            _log(f"sending '{event}' → {properties}")
            posthog.capture(event=event, distinct_id=_get_or_create_anonymous_id(), properties=properties)
            posthog.flush()
            _log(f"'{event}' sent successfully")
        except Exception as e:
            _log(f"error sending event: {e}")

    thread = threading.Thread(target=_do_send, daemon=True)
    thread.start()
    return thread


def capture_command(command: str, success: bool = True) -> threading.Thread | None:
    """Track a command invocation."""
    if not command:
        return None
    props = _get_common_properties()
    props["command"] = command
    props["success"] = success
    return _send("command_used", props)


def capture_error(command: str, error: Exception) -> threading.Thread | None:
    """Track an unhandled error."""
    props = _get_common_properties()
    props["command"] = command or "unknown"
    props["error_type"] = type(error).__name__
    props["error_message"] = str(error)[:200]
    return _send("command_error", props)


def show_first_run_notice() -> None:
    """Print a one-time telemetry notice the first time the CLI runs."""
    if _get_telemetry_id_file().exists():
        return
    from rich.console import Console
    from rich.panel import Panel

    Console().print(
        Panel(
            "[dim]devo-cli collects anonymous usage data to improve the tool.\n"
            "Opt-out: [cyan]export DEVO_NO_TELEMETRY=1[/cyan]"
            "  or  [cyan]devo config set telemetry.enabled false[/cyan][/dim]",
            title="[dim]Telemetry Notice[/dim]",
            border_style="dim",
            padding=(0, 2),
        )
    )
