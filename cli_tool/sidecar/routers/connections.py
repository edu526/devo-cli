"""Connection lifecycle endpoints /api/v1/connections."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from cli_tool.sidecar.deps import get_app_state, require_bearer
from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.services.connection_service import (
    list_connections,
    start_all_connections,
    start_connection,
    stop_all_connections,
    stop_connection,
)
from cli_tool.sidecar.state import AppState

router = APIRouter(prefix="/connections", tags=["connections"], dependencies=[Depends(require_bearer)])


def _state(request: Request) -> AppState:
    return get_app_state(request)


@router.get("")
def get_connections(request: Request) -> list[dict[str, Any]]:
    app_state = _state(request)
    return list_connections(app_state.registry)


@router.post(":start_all", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
def start_all(request: Request, response: Response) -> list[dict[str, Any]]:
    app_state = _state(request)
    return start_all_connections(app_state.registry, app_state.event_hub)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def stop_all(request: Request) -> None:
    app_state = _state(request)
    stop_all_connections(app_state.registry)


@router.post("/{name}", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute")
def start_one(name: str, request: Request, response: Response) -> dict[str, Any]:
    app_state = _state(request)
    try:
        return start_connection(name, app_state.registry, app_state.event_hub)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def stop_one(name: str, request: Request) -> None:
    app_state = _state(request)
    rec = app_state.registry.get(name)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Connection '{name}' not active")
    stop_connection(name, app_state.registry)
