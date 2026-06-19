"""GET/POST/DELETE /api/v1/hosts."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cli_tool.sidecar.deps import require_bearer
from cli_tool.sidecar.services.hosts_service import NeedsElevation, add_host, list_hosts, remove_host, setup_hosts

router = APIRouter(prefix="/hosts", tags=["hosts"], dependencies=[Depends(require_bearer)])


class HostIn(BaseModel):
    ip: str
    hostname: str


class SetupIn(BaseModel):
    db_names: Optional[list[str]] = None


@router.get("")
def get_hosts() -> list[dict[str, Any]]:
    return list_hosts()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_host(body: HostIn) -> dict[str, Any]:
    try:
        add_host(body.ip, body.hostname)
    except NeedsElevation as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Elevated privileges required", "command": exc.command},
        )
    return {"ip": body.ip, "hostname": body.hostname}


@router.post("/setup", status_code=status.HTTP_200_OK)
def setup_endpoint(body: SetupIn | None = None) -> dict[str, Any]:
    try:
        return setup_hosts(body.db_names if body else None)
    except NeedsElevation as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Elevated privileges required", "command": exc.command},
        )


@router.delete("/{hostname}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host(hostname: str) -> None:
    try:
        remove_host(hostname)
    except NeedsElevation as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Elevated privileges required", "command": exc.command},
        )
