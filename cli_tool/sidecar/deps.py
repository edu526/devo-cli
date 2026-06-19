"""FastAPI dependency injectors."""

from fastapi import Depends, Header, HTTPException, Request, status

from cli_tool.sidecar.state import AppState


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


async def require_bearer(
    authorization: str | None = Header(default=None),
    app_state: AppState = Depends(get_app_state),
) -> None:
    """Validate the Authorization header against the current token.

    Rejects with 401 if:
    - the header is missing or malformed
    - the token does not match the sidecar's current token (invalidated)
    - the token is older than the configured TTL (expired)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided = authorization[len("Bearer ") :].strip()
    if not provided or provided != app_state.token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if app_state.token_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
