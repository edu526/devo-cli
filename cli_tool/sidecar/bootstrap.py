"""Sidecar entry point: bind, print READY handshake, serve."""

import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.state import AppState, EventHub

os.environ["DEVO_SIDECAR"] = "1"

LOG_FILE = Path.home() / ".devo" / "sidecar.log"


def _configure_logging(log_level: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_level.upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)


def _kill_orphan_ssm_processes() -> None:
    """Kill any leftover session-manager-plugin processes from a previous session.

    If the sidecar crashed or was killed without a clean shutdown, SSM child
    processes survive as orphans. We sweep them on startup so they don't hold
    ports or consume resources.

    Runs on a background thread (see run()) so a slow or large sweep — e.g.
    after a retry storm left many orphans behind — never delays the
    DEVO_SIDECAR_READY handshake that Tauri is waiting on (30s timeout).
    Because it's fire-and-forget, everything here — including the logging
    calls — is guarded: this must never surface as an unhandled exception
    on a background thread (e.g. logging to a handler whose stream was
    already closed during interpreter/process shutdown).
    """
    log = logging.getLogger(__name__)
    t0 = time.monotonic()
    try:
        import psutil

        killed = 0
        scanned = 0
        for proc in psutil.process_iter(["name"]):
            scanned += 1
            try:
                if proc.info["name"] and "session-manager-plugin" in proc.info["name"].lower():
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        elapsed = time.monotonic() - t0
        log.info(
            "[TIMING] Orphan sweep: scanned %d process(es), terminated %d, took %.3fs",
            scanned,
            killed,
            elapsed,
        )
        if elapsed > 2.0:
            log.warning(
                "[TIMING] Orphan sweep took %.3fs — unusually slow, check for a large number of stuck processes",
                elapsed,
            )
    except Exception:
        try:
            log.exception("[TIMING] Orphan sweep failed after %.3fs", time.monotonic() - t0)
        except Exception:
            pass


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run(port: int = 0, host: str = "127.0.0.1", log_level: str = "warning") -> None:
    t0 = time.monotonic()

    def _elapsed() -> float:
        return time.monotonic() - t0

    try:
        from cli_tool.core.utils.config_manager import load_config

        # Override CLI arg with config
        log_level = "debug" if load_config().get("debug_mode") else "warning"
    except Exception:
        pass  # Fallback to function argument if config fails

    _configure_logging(log_level)
    log = logging.getLogger(__name__)
    log.info("[TIMING] Logging configured at +%.3fs", _elapsed())

    # Fire-and-forget: the orphan sweep must never block the READY handshake
    # below (Tauri gives up waiting for it after 30s). It doesn't touch
    # anything the rest of startup depends on — it only cleans up processes
    # left over from a previous, already-dead sidecar instance.
    threading.Thread(target=_kill_orphan_ssm_processes, name="orphan-ssm-sweep", daemon=True).start()
    log.info("[TIMING] Orphan sweep dispatched to background thread at +%.3fs", _elapsed())

    actual_port = port if port != 0 else _find_free_port()
    log.info("[TIMING] Port resolved (%s) at +%.3fs", actual_port, _elapsed())

    registry = ForwarderRegistry()
    event_hub = EventHub()
    app_state = AppState(registry=registry, event_hub=event_hub)
    # Centralised token issuance so the bootstrap path and /auth/refresh
    # share the same locking + timestamp semantics.
    token = app_state.issue_token()

    app = create_app(app_state)
    log.info("[TIMING] FastAPI app created at +%.3fs", _elapsed())

    log.info("Sidecar starting on %s:%s — log file: %s", host, actual_port, LOG_FILE)

    # Handshake line read by the Tauri shell / parent process
    print(f"DEVO_SIDECAR_READY port={actual_port} token={token}", flush=True)
    log.info("[TIMING] DEVO_SIDECAR_READY printed at +%.3fs", _elapsed())
    uvicorn.run(
        app,
        host=host,
        port=actual_port,
        log_level=log_level,
        access_log=(log_level == "debug"),
    )
