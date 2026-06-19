import asyncio
import json

import pytest
from fastapi import WebSocketDisconnect

from cli_tool.commands.ssm.core.connection_runner import ForwarderRegistry
from cli_tool.sidecar.state import AppState, EventHub

VALID_HEADER = {"sec-websocket-protocol": "bearer, test-token"}
WRONG_HEADER = {"sec-websocket-protocol": "bearer, bad-token"}


def _make_app_state():
    return AppState(token="test-token", registry=ForwarderRegistry(), event_hub=EventHub())


class _App:
    """Minimal stub for websocket.app.state.app_state."""

    def __init__(self, app_state):
        self.state = type("S", (), {"app_state": app_state})()


class _WebSocketSpy:
    def __init__(self, headers, app_state, *, disconnect_after=1):
        self.headers = headers
        self.app = _App(app_state)
        self.sent = []
        self._send_count = 0
        self._disconnect_after = disconnect_after
        self.closed_code = None
        self.accepted_subprotocol = None

    async def close(self, code=None):
        self.closed_code = code

    async def accept(self, subprotocol=None):
        self.accepted_subprotocol = subprotocol

    async def send_text(self, text):
        self.sent.append(text)
        self._send_count += 1
        if self._send_count >= self._disconnect_after:
            raise WebSocketDisconnect()


@pytest.mark.unit
class TestEventsWs:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_valid_token_receives_hello(self):
        from cli_tool.sidecar.routers.ws import events_ws

        app_state = _make_app_state()
        ws = _WebSocketSpy(VALID_HEADER, app_state, disconnect_after=1)

        self._run(events_ws(ws))

        assert len(ws.sent) >= 1
        msg = json.loads(ws.sent[0])
        assert msg["event"] == "hello"
        assert msg["payload"]["status"] == "connected"

    def test_invalid_token_closes(self):
        from cli_tool.sidecar.routers.ws import events_ws

        app_state = _make_app_state()
        ws = _WebSocketSpy(WRONG_HEADER, app_state, disconnect_after=999)

        self._run(events_ws(ws))

        assert ws.closed_code == 4401
        assert ws.sent == []

    def test_published_event_forwarded(self):
        from cli_tool.sidecar.routers.ws import events_ws

        app_state = _make_app_state()
        ws = _WebSocketSpy(VALID_HEADER, app_state, disconnect_after=2)

        async def run():
            handler_task = asyncio.create_task(events_ws(ws))
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            app_state.event_hub.publish("test.event", {"x": 1})
            await handler_task

        asyncio.run(run())

        assert len(ws.sent) >= 2
        second = json.loads(ws.sent[1])
        assert second["event"] == "test.event"
        assert second["x"] == 1

    def test_unsubscribe_on_disconnect(self):
        from cli_tool.sidecar.routers.ws import events_ws

        app_state = _make_app_state()
        ws = _WebSocketSpy(VALID_HEADER, app_state, disconnect_after=1)

        self._run(events_ws(ws))

        assert len(app_state.event_hub._subscribers) == 0
