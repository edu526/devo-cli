"""POST /api/v1/auth/refresh — rotate the bearer token.

Unlike the rest of the sidecar's endpoints, this one does not require the
bearer dependency: the caller is allowed (and expected) to hold a token
that is about to expire, or to retry after a 401. We validate the *current*
token and return a *new* one in the same response.

The endpoint intentionally accepts expired tokens too, so the frontend can
seamlessly rotate without a hard logout. Tokens older than `2 * TTL` are
rejected outright — the user must restart the sidecar (which only happens
on app relaunch).
"""

import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from cli_tool.sidecar.deps import get_app_state
from cli_tool.sidecar.state import AppState

router = APIRouter(prefix="/auth", tags=["auth"])

# Maximum age of a token accepted at /auth/refresh. Older than this and we
# force a full re-authentication (which currently means app restart).
_REFRESH_GRACE_MULTIPLIER = 2


@router.post("/refresh")
def refresh_token(
    request: Request,
    authorization: str | None = Header(default=None),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, object]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )

    provided = authorization[len("Bearer ") :].strip()
    if not provided or provided != app_state.token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )

    age = app_state.token_age_seconds()
    max_age = app_state.token_ttl_seconds * _REFRESH_GRACE_MULTIPLIER
    if age > max_age:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token too old to refresh; please restart the app",
        )

    new_token = app_state.issue_token()
    return {
        "token": new_token,
        "expires_at": app_state.token_expires_at(),
        "issued_at": time.time(),
    }
