"""WebSocket /api/v1/events — real-time event stream."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["events"])


@router.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    app_state = websocket.app.state.app_state

    # Auth via Sec-WebSocket-Protocol header: "bearer, <token>"
    token_header = websocket.headers.get("sec-websocket-protocol", "")
    if token_header:
        parts = [p.strip() for p in token_header.split(",")]
        client_token = parts[1] if len(parts) >= 2 else ""
    else:
        client_token = ""

    # Must accept before closing — close codes only valid after WS handshake
    if client_token != app_state.token:
        await websocket.accept()
        await websocket.close(code=4401)
        return

    await websocket.accept(subprotocol="bearer")

    q = app_state.event_hub.subscribe()
    try:
        await websocket.send_text(json.dumps({"event": "hello", "payload": {"status": "connected"}}))

        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30.0)
                await websocket.send_text(json.dumps(msg))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"event": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        app_state.event_hub.unsubscribe(q)
