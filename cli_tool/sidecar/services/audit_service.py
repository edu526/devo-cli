"""Audit log: persist a JSONL record for every API request.

Records are appended to `~/.devo/audit.log` with daily rotation. Old files
beyond `RETENTION_DAYS` are pruned on each open. Token values are hashed
(never written in plain text).

The middleware records `method`, `path`, `status_code`, `client_ip`,
`token_hash` and the wall-clock timestamp. Bodies are never captured.
"""

import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

AUDIT_LOG_DIR = Path.home() / ".devo"
AUDIT_LOG_PREFIX = "audit"
AUDIT_LOG_SUFFIX = ".log"
RETENTION_DAYS = 30


def _hash_token(token: str | None) -> str:
    """Return a 16-char hex prefix of SHA-256 for the bearer token (or '-')."""
    if not token:
        return "-"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _current_log_path(now: date | None = None) -> Path:
    """Path to the active log file for `now` (defaults to today UTC)."""
    d = now or datetime.now(timezone.utc).date()
    return AUDIT_LOG_DIR / f"{AUDIT_LOG_PREFIX}-{d.isoformat()}{AUDIT_LOG_SUFFIX}"


def prune_old_logs(now: date | None = None) -> int:
    """Delete audit logs older than RETENTION_DAYS. Returns the count removed."""
    if not AUDIT_LOG_DIR.exists():
        return 0
    cutoff = (now or datetime.now(timezone.utc).date()) - timedelta(days=RETENTION_DAYS)
    removed = 0
    for path in AUDIT_LOG_DIR.glob(f"{AUDIT_LOG_PREFIX}-*{AUDIT_LOG_SUFFIX}"):
        try:
            stamp = path.stem.replace(f"{AUDIT_LOG_PREFIX}-", "")
            d = date.fromisoformat(stamp)
        except ValueError:
            continue
        if d < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError as exc:
                logger.warning("Failed to delete old audit log %s: %s", path, exc)
    return removed


def log_event(
    *,
    method: str,
    path: str,
    status_code: int,
    client_ip: str,
    token: str | None,
    duration_ms: float,
    log_path: Path | None = None,
) -> None:
    """Append a single audit record to the daily log file."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "method": method,
        "path": path,
        "status": status_code,
        "ip": client_ip,
        "token": _hash_token(token),
        "duration_ms": round(duration_ms, 2),
    }
    path = log_path or _current_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as exc:
        # The audit log is best-effort: if disk is full or the file
        # disappeared, do not crash the request pipeline.
        logger.warning("Failed to write audit record: %s", exc)


def read_recent(since: datetime | None = None, limit: int = 100) -> list[dict]:
    """Return the most recent audit records across all rotated log files.

    Records are returned newest-first. `since` filters by timestamp (>=).
    """
    if not AUDIT_LOG_DIR.exists():
        return []

    files = sorted(
        AUDIT_LOG_DIR.glob(f"{AUDIT_LOG_PREFIX}-*{AUDIT_LOG_SUFFIX}"),
        reverse=True,
    )
    out: list[dict] = []
    for path in files:
        if len(out) >= limit:
            break
        try:
            with path.open("r", encoding="utf-8") as f:
                # Read backwards through the file for efficiency
                lines = f.readlines()
        except OSError as exc:
            logger.warning("Failed to read audit log %s: %s", path, exc)
            continue
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since is not None:
                try:
                    ts = datetime.fromisoformat(rec.get("ts", ""))
                except ValueError:
                    continue
                if ts < since:
                    continue
            out.append(rec)
            if len(out) >= limit:
                break
    return out


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that writes one record per request to the audit log."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        # Capture the Authorization header before the request is consumed
        auth = request.headers.get("authorization") or ""
        token = None
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip() or None

        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0

        client_ip = request.client.host if request.client else "-"
        try:
            log_event(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                client_ip=client_ip,
                token=token,
                duration_ms=duration_ms,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Audit log middleware failure: %s", exc)
        return response
