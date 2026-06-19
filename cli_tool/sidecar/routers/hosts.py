"""GET/POST/DELETE /api/v1/hosts."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cli_tool.sidecar.deps import require_bearer
from cli_tool.sidecar.services.hosts_service import NeedsElevation, add_host, list_hosts, remove_host

router = APIRouter(prefix="/hosts", tags=["hosts"], dependencies=[Depends(require_bearer)])


class HostIn(BaseModel):
    ip: str
    hostname: str


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


@router.delete("/{hostname}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host(hostname: str) -> None:
    try:
        remove_host(hostname)
    except NeedsElevation as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Elevated privileges required", "command": exc.command},
        )
