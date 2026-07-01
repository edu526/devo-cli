"""Shared application state for the sidecar."""

import asyncio
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry

# Default token lifetime. 8h covers a full work day; the desktop frontend
# refreshes the token automatically via /api/v1/auth/refresh.
DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60


class EventHub:
    """Thread-safe event bus → broadcast to all connected WS clients.

    Worker threads call publish(); async WS handlers consume from their queue.
    """

    def __init__(self) -> None:
        self._subscribers: list[tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        with self._lock:
            self._subscribers.append((q, loop))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers = [(sq, loop) for sq, loop in self._subscribers if sq is not q]

    def publish(self, event: str, payload: dict) -> None:
        msg: dict[str, Any] = {"event": event, **payload}
        with self._lock:
            subs = list(self._subscribers)

        for q, loop in subs:

            def _do_put(queue=q, message=msg):
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    pass

            if loop is not None:
                loop.call_soon_threadsafe(_do_put)
            else:
                _do_put()


@dataclass
class AppState:
    token: str = ""
    token_created_at: float = field(default_factory=time.time)
    token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS
    registry: ForwarderRegistry = field(default_factory=ForwarderRegistry)
    event_hub: EventHub = field(default_factory=EventHub)
    _active_tasks: list[asyncio.Task] = field(default_factory=list)
    _token_lock: threading.Lock = field(default_factory=threading.Lock)

    def issue_token(self) -> str:
        """Generate a new bearer token, invalidating the previous one.

        Called at startup and on /api/v1/auth/refresh. Returns the new token.
        """
        new_token = secrets.token_urlsafe(32)
        with self._token_lock:
            self.token = new_token
            self.token_created_at = time.time()
        return new_token

    def token_expired(self, now: float | None = None) -> bool:
        """Return True if the current token is older than ttl_seconds."""
        with self._token_lock:
            if not self.token or not self.token_created_at:
                return True
            ts = self.token_created_at
        current = now if now is not None else time.time()
        return (current - ts) > self.token_ttl_seconds

    def token_age_seconds(self, now: float | None = None) -> float:
        with self._token_lock:
            ts = self.token_created_at
        if not ts:
            return 0.0
        current = now if now is not None else time.time()
        return max(0.0, current - ts)

    def token_expires_at(self) -> float:
        with self._token_lock:
            ts = self.token_created_at
        return ts + self.token_ttl_seconds
