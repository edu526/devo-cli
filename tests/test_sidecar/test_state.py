"""Unit tests for cli_tool.sidecar.state module."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from cli_tool.sidecar.state import AppState, EventHub

# ---------------------------------------------------------------------------
# EventHub
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEventHub:
    def test_subscribe_returns_queue(self):
        hub = EventHub()
        q = hub.subscribe()
        assert isinstance(q, asyncio.Queue)

    def test_publish_puts_message_in_subscriber_queue(self):
        hub = EventHub()
        q = hub.subscribe()
        hub.publish("test_event", {"key": "value"})
        msg = q.get_nowait()
        # real publish does {"event": event, **payload} — payload keys are inlined
        assert msg == {"event": "test_event", "key": "value"}

    def test_multiple_subscribers_all_receive(self):
        hub = EventHub()
        q1 = hub.subscribe()
        q2 = hub.subscribe()
        hub.publish("broadcast", {"x": 1})
        assert q1.get_nowait() == {"event": "broadcast", "x": 1}
        assert q2.get_nowait() == {"event": "broadcast", "x": 1}

    def test_unsubscribe_stops_receiving(self):
        hub = EventHub()
        q = hub.subscribe()
        hub.unsubscribe(q)
        hub.publish("after_unsub", {})
        assert q.empty()

    def test_publish_no_subscribers_no_error(self):
        hub = EventHub()
        # should not raise with an empty subscriber list
        hub.publish("lonely_event", {"data": 42})

    def test_thread_safe_publish(self):
        hub = EventHub()
        q = hub.subscribe()
        errors = []

        def publish_one():
            try:
                hub.publish("threaded", {"n": 1})  # {"event": "threaded", "n": 1} ends up in queue
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=publish_one) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Unexpected errors from threads: {errors}"
        # all 10 messages must have landed
        count = 0
        while not q.empty():
            q.get_nowait()
            count += 1
        assert count == 10


# ---------------------------------------------------------------------------
# AppState
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAppState:
    def test_fields_stored(self):
        hub = EventHub()
        registry = MagicMock()
        state = AppState(token="tok123", registry=registry, event_hub=hub)
        assert state.token == "tok123"
        assert state.registry is registry
        assert state.event_hub is hub

    def test_active_tasks_defaults_empty(self):
        hub = EventHub()
        registry = MagicMock()
        state = AppState(token="tok", registry=registry, event_hub=hub)
        assert state._active_tasks == []
