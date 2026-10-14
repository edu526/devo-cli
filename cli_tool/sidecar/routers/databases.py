"""CRUD /api/v1/databases."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from cli_tool.commands.ssm.core import hostname_forwarding
from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.sidecar.deps import get_app_state, require_bearer
from cli_tool.sidecar.services.database_discovery import discover_databases

router = APIRouter(prefix="/databases", tags=["databases"], dependencies=[Depends(require_bearer)])

_NAME_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"
_INACTIVE_STATES = ("stopped", "error", "expired_credentials")


def _rename(mgr: SSMConfigManager, name: str, new_name: str) -> None:
    """Rename a database, keeping all its settings and its place in the list."""
    config = mgr.load()
    config["databases"] = {(new_name if key == name else key): value for key, value in config["databases"].items()}
    mgr.save(config)


class DatabaseIn(BaseModel):
    bastion: str
    host: str
    port: int
    region: str = "us-east-1"
    profile: Optional[str] = None
    local_port: Optional[int] = None
    local_address: str = "127.0.0.1"


class DatabasePatch(BaseModel):
    # A different name renames it (its tunnel must be stopped).
    name: Optional[str] = Field(None, pattern=_NAME_PATTERN)
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


@router.get(":discover")
def discover(region: str, profile: Optional[str] = None) -> dict[str, Any]:
    """RDS databases `profile` can see in `region`, to pick one in the form.
    Always 200: {"databases": [...], "error": str | None}."""
    return discover_databases(profile, region)


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
def patch_database(name: str, body: DatabasePatch, request: Request) -> dict[str, Any]:
    mgr = SSMConfigManager()
    db = mgr.get_database(name)
    if db is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Database '{name}' not found")
    updates = body.model_dump(exclude_none=True)
    new_name = updates.pop("name", name)
    if new_name != name:
        # Its tunnel is tracked by name: renaming under it would orphan it.
        record = get_app_state(request).registry.get(name)
        if record is not None and record.state not in _INACTIVE_STATES:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Stop the connection to '{name}' before renaming it")
        if mgr.get_database(new_name) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Database '{new_name}' already exists")
        _rename(mgr, name, new_name)
        name = new_name
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
        # Not editable here (it goes with the hosts file, see /hosts/forwarding),
        # but rebuilding the entry must not drop it.
        hostname_forwarding=db.get(hostname_forwarding.KEY),
    )
    return mgr.get_database(name)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_database(name: str) -> None:
    removed = SSMConfigManager().remove_database(name)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Database '{name}' not found")
