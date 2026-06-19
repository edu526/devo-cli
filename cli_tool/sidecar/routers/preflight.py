"""GET /api/v1/preflight — no auth required."""

from fastapi import APIRouter

from cli_tool.sidecar.services.preflight_service import check_preflight

router = APIRouter(tags=["preflight"])


@router.get("/preflight")
def get_preflight():
    return check_preflight()
