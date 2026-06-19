"""GET /api/v1/logs — tail the sidecar log file."""

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response

from cli_tool.sidecar.deps import require_bearer
from cli_tool.sidecar.rate_limit import limiter

router = APIRouter(prefix="/logs", tags=["logs"], dependencies=[Depends(require_bearer)])

_LOG_FILE = Path.home() / ".devo" / "sidecar.log"


@router.get("")
def get_logs(lines: int = Query(300, ge=1, le=5000)) -> list[str]:
    if not _LOG_FILE.exists():
        return []
    with _LOG_FILE.open("r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return [line.rstrip("\n") for line in all_lines[-lines:]]


@router.delete("", status_code=204)
@limiter.limit("5/hour")
def clear_logs(request: Request, response: Response) -> None:
    if _LOG_FILE.exists():
        _LOG_FILE.write_text("", encoding="utf-8")
