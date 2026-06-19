"""CRUD /api/v1/databases."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.sidecar.deps import require_bearer

router = APIRouter(prefix="/databases", tags=["databases"], dependencies=[Depends(require_bearer)])


class DatabaseIn(BaseModel):
    bastion: str
    host: str
    port: int
    region: str = "us-east-1"
    profile: Optional[str] = None
    local_port: Optional[int] = None
    local_address: str = "127.0.0.1"


class DatabasePatch(BaseModel):
    bastion: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    region: Optional[str] = None
    profile: Optional[str] = None
    local_port: Optional[int] = None
    local_address: Optional[str] = None


@router.get("")
def list_databases() -> dict[str, Any]:
    return SSMConfigManager().list_databases()


@router.post("/{name}", status_code=status.HTTP_201_CREATED)
def create_database(name: str, body: DatabaseIn) -> dict[str, Any]:
    mgr = SSMConfigManager()
    if mgr.get_database(name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Database '{name}' already exists")
    mgr.add_database(
        name=name,
        bastion=body.bastion,
        host=body.host,
        port=body.port,
        region=body.region,
        profile=body.profile,
        local_port=body.local_port,
        local_address=body.local_address,
    )
    return mgr.get_database(name)


@router.get("/{name}")
def get_database(name: str) -> dict[str, Any]:
    db = SSMConfigManager().get_database(name)
    if db is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Database '{name}' not found")
    return db


@router.patch("/{name}")
def patch_database(name: str, body: DatabasePatch) -> dict[str, Any]:
    mgr = SSMConfigManager()
    db = mgr.get_database(name)
    if db is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Database '{name}' not found")
    updates = body.model_dump(exclude_none=True)
    db.update(updates)
    # Write back via add_database (overwrites)
    mgr.add_database(
        name=name,
        bastion=db["bastion"],
        host=db["host"],
        port=db["port"],
        region=db.get("region", "us-east-1"),
        profile=db.get("profile"),
        local_port=db.get("local_port"),
        local_address=db.get("local_address", "127.0.0.1"),
    )
    return mgr.get_database(name)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_database(name: str) -> None:
    removed = SSMConfigManager().remove_database(name)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Database '{name}' not found")
