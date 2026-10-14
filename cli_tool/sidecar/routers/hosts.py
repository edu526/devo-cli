"""GET/POST/PUT/DELETE /api/v1/hosts."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cli_tool.sidecar.deps import require_bearer
from cli_tool.sidecar.services.hosts_service import (
    NeedsElevation,
    add_host,
    hosts_lock_reason,
    hosts_status,
    list_hosts,
    remove_host,
    set_database_forwarding,
    set_forwarding,
    setup_hosts,
)

router = APIRouter(prefix="/hosts", tags=["hosts"], dependencies=[Depends(require_bearer)])


class HostIn(BaseModel):
    ip: str
    hostname: str


class SetupIn(BaseModel):
    db_names: Optional[list[str]] = None


class ForwardingIn(BaseModel):
    enabled: bool


def _elevation_required(exc: NeedsElevation) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail={
            "message": "Elevated privileges required",
            "command": exc.command,
            "action": exc.action,
            "params": exc.params,
        },
    )


@router.get("")
def get_hosts() -> list[dict[str, Any]]:
    return list_hosts()


@router.get("/status")
def get_status() -> dict[str, Any]:
    return hosts_status()


@router.get("/lock-reason")
def get_lock_reason() -> dict[str, str]:
    """Why the hosts file can't be written even as administrator."""
    return hosts_lock_reason()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_host(body: HostIn) -> dict[str, Any]:
    try:
        add_host(body.ip, body.hostname)
    except NeedsElevation as exc:
        raise _elevation_required(exc)
    return {"ip": body.ip, "hostname": body.hostname}


@router.post("/setup", status_code=status.HTTP_200_OK)
def setup_endpoint(body: SetupIn | None = None) -> dict[str, Any]:
    try:
        return setup_hosts(body.db_names if body else None)
    except NeedsElevation as exc:
        raise _elevation_required(exc)


@router.put("/forwarding")
def put_forwarding(body: ForwardingIn) -> dict[str, Any]:
    """Pause/resume hostname forwarding for every database."""
    try:
        return set_forwarding(body.enabled)
    except NeedsElevation as exc:
        raise _elevation_required(exc)


@router.put("/forwarding/{name}")
def put_database_forwarding(name: str, body: ForwardingIn) -> dict[str, Any]:
    """Pause/resume hostname forwarding for one database."""
    try:
        return set_database_forwarding(name, body.enabled)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NeedsElevation as exc:
        raise _elevation_required(exc)


@router.delete("/{hostname}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host(hostname: str) -> None:
    try:
        remove_host(hostname)
    except NeedsElevation as exc:
        raise _elevation_required(exc)
