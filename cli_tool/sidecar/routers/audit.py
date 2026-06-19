"""GET /api/v1/audit — read the audit log (bearer-protected)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from cli_tool.sidecar.deps import require_bearer
from cli_tool.sidecar.services.audit_service import read_recent

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_bearer)])


@router.get("")
def list_audit(
    since: str | None = Query(
        default=None,
        description="ISO-8601 timestamp; only records at or after this are returned",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid `since` value: {exc}",
            ) from exc
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
    return read_recent(since=since_dt, limit=limit)
