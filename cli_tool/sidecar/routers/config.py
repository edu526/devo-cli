"""GET/PUT/PATCH /api/v1/config and /api/v1/config/schema."""

import copy
from typing import Any

from fastapi import APIRouter, Depends

from cli_tool.core.utils.config_manager import get_default_config, load_config, save_config
from cli_tool.sidecar.deps import require_bearer

router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(require_bearer)])


def _json_merge_patch(target: dict, patch: dict) -> dict:
    """RFC 7396 JSON Merge Patch."""
    result = copy.deepcopy(target)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _json_merge_patch(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


@router.get("")
def get_config() -> dict[str, Any]:
    return load_config()


@router.put("")
def put_config(body: dict[str, Any]) -> dict[str, Any]:
    save_config(body)
    return body


@router.patch("")
def patch_config(body: dict[str, Any]) -> dict[str, Any]:
    current = load_config()
    merged = _json_merge_patch(current, body)
    save_config(merged)
    return merged


@router.get("/schema")
def get_config_schema() -> dict[str, Any]:
    defaults = get_default_config()
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Devo Config",
        "type": "object",
        "properties": {
            "ssm": {
                "type": "object",
                "properties": {
                    "databases": {"type": "object", "additionalProperties": {"type": "object"}},
                    "instances": {"type": "object", "additionalProperties": {"type": "object"}},
                },
            },
            "aws_login": {
                "type": "object",
                "properties": {
                    "set_env_profile": {"type": "boolean"},
                },
            },
            "bedrock": {
                "type": "object",
                "properties": {
                    "model_id": {"type": "string"},
                    "region": {"type": "string"},
                },
            },
            "version_check": {
                "type": "object",
                "properties": {"enabled": {"type": "boolean"}},
            },
            "telemetry": {
                "type": "object",
                "properties": {"enabled": {"type": "boolean"}},
            },
        },
        "additionalProperties": True,
        "default": defaults,
    }
