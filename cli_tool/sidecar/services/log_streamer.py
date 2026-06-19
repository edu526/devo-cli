"""LogFileTailer — push-based tail of the sidecar log file into the EventHub.

A small `LogRecordHandler` is attached to the root logger. Every record
emitted by the application becomes an event on the hub (event name
`log.line`) with the formatted line as the payload. The LogsPage in
the desktop frontend subscribes to this event and appends to its
in-memory list in real time — no more 3 s polling.

The previous snapshot fetched via `GET /api/v1/logs?lines=N` is still
the source of truth for cold-start; new lines are appended as they
arrive.
"""

import logging
from typing import Optional

from cli_tool.sidecar.state import AppState

# Maximum number of characters of a single log line we are willing to
# push over WS. Anything longer gets truncated to avoid pathological
# records (e.g. minified JSON blobs) flooding the channel.
_MAX_LINE_CHARS = 4000


class LogRecordHandler(logging.Handler):
    """Forward every log record to the EventHub as a `log.line` event.

    The handler holds a weak reference to the AppState so it does not
    keep a closed sidecar alive. If the hub is unavailable (very early
    in startup or during shutdown) the record is silently dropped —
    logging is best-effort by design.
    """

    def __init__(self, app_state: AppState) -> None:
        super().__init__(logging.INFO)
        self._app_state = app_state

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            if len(line) > _MAX_LINE_CHARS:
                line = line[:_MAX_LINE_CHARS] + "…(truncated)"
            # level is the *only* field the frontend needs to colour the line
            self._app_state.event_hub.publish(
                "log.line",
                {"line": line, "level": record.levelname},
            )
        except Exception:  # pragma: no cover — defensive
            # Logging handlers must never raise.
            self.handleError(record)


def attach_log_streamer(app_state: AppState) -> LogRecordHandler:
    """Install the LogRecordHandler on the root logger and return it.

    Idempotent: a second call replaces the existing handler (so a
    sidecar restart during tests doesn't double-emit).
    """
    handler = LogRecordHandler(app_state)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    # Remove any prior streamer (e.g. on test re-creation)
    for existing in list(root.handlers):
        if isinstance(existing, LogRecordHandler):
            root.removeHandler(existing)
    root.addHandler(handler)
    return handler


def detach_log_streamer(handler: Optional[LogRecordHandler]) -> None:
    if handler is None:
        return
    root = logging.getLogger()
    if handler in root.handlers:
        root.removeHandler(handler)
