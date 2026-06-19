"""CRUD /api/v1/instances."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cli_tool.commands.ssm.core.config import SSMConfigManager
from cli_tool.sidecar.deps import require_bearer

router = APIRouter(prefix="/instances", tags=["instances"], dependencies=[Depends(require_bearer)])


class InstanceIn(BaseModel):
    instance_id: str
    region: str = "us-east-1"
    profile: Optional[str] = None


class InstancePatch(BaseModel):
    instance_id: Optional[str] = None
    region: Optional[str] = None
    profile: Optional[str] = None


@router.get("")
def list_instances() -> dict[str, Any]:
    return SSMConfigManager().list_instances()


@router.post("/{name}", status_code=status.HTTP_201_CREATED)
def create_instance(name: str, body: InstanceIn) -> dict[str, Any]:
    mgr = SSMConfigManager()
    if mgr.get_instance(name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Instance '{name}' already exists")
    mgr.add_instance(name=name, instance_id=body.instance_id, region=body.region, profile=body.profile)
    return mgr.get_instance(name)


@router.get("/{name}")
def get_instance(name: str) -> dict[str, Any]:
    inst = SSMConfigManager().get_instance(name)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Instance '{name}' not found")
    return inst


@router.patch("/{name}")
def patch_instance(name: str, body: InstancePatch) -> dict[str, Any]:
    mgr = SSMConfigManager()
    inst = mgr.get_instance(name)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Instance '{name}' not found")
    updates = body.model_dump(exclude_none=True)
    inst.update(updates)
    mgr.add_instance(
        name=name,
        instance_id=inst["instance_id"],
        region=inst.get("region", "us-east-1"),
        profile=inst.get("profile"),
    )
    return mgr.get_instance(name)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(name: str) -> None:
    removed = SSMConfigManager().remove_instance(name)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Instance '{name}' not found")
