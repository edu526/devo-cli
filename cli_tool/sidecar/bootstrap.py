"""Sidecar entry point: bind, print READY handshake, serve."""

import logging
import logging.handlers
import socket
import sys
from pathlib import Path

import uvicorn

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.app import create_app
from cli_tool.sidecar.state import AppState, EventHub

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


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run(port: int = 0, host: str = "127.0.0.1", log_level: str = "info") -> None:
    _configure_logging(log_level)
    log = logging.getLogger(__name__)

    actual_port = port if port != 0 else _find_free_port()

    registry = ForwarderRegistry()
    event_hub = EventHub()
    app_state = AppState(registry=registry, event_hub=event_hub)
    # Centralised token issuance so the bootstrap path and /auth/refresh
    # share the same locking + timestamp semantics.
    token = app_state.issue_token()

    app = create_app(app_state)

    log.info("Sidecar starting on %s:%s — log file: %s", host, actual_port, LOG_FILE)

    # Handshake line read by the Tauri shell / parent process
    print(f"DEVO_SIDECAR_READY port={actual_port} token={token}", flush=True)

    uvicorn.run(app, host=host, port=actual_port, log_level=log_level)
