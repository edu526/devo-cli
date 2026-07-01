"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from cli_tool.sidecar.rate_limit import limiter
from cli_tool.sidecar.routers import (
    audit,
    auth,
    codeartifact,
    config,
    connections,
    databases,
    hosts,
    instances,
    log_router,
    preflight,
    profiles,
    version,
    ws,
)
from cli_tool.sidecar.services.config_watcher import start_config_watcher
from cli_tool.sidecar.services.profile_service import watch_profiles
from cli_tool.sidecar.state import AppState

logger = logging.getLogger(__name__)

# CORS allowlist is intentionally restrictive. Tauri 2 webview origins
# (verified against tauri 2.11.1 manager::get_app_url):
#   - `tauri://localhost`         — macOS / Linux (dev & production)
#   - `http://tauri.localhost`    — Windows dev
#   - `https://tauri.localhost`   — Windows production
#   - `http://localhost:5173`     — Vite dev server (see desktop/vite.config.ts)
# All are non-network-accessible in the Tauri model.
_DEFAULT_ALLOWED_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:5173",
)

# Cap incoming JSON bodies at 1 MB. The sidecar's largest legitimate
# payload (a config patch) is well under 64 KB. The constant is exported
# so tests can assert against it.
MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024
_BODY_LOG_PREVIEW_CHARS = 200


def create_app(app_state: AppState) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Start background tasks
        import asyncio

        from cli_tool.sidecar.services.log_streamer import (
            attach_log_streamer,
            detach_log_streamer,
        )

        profile_task = asyncio.create_task(watch_profiles(app_state.event_hub))
        app_state._active_tasks.append(profile_task)

        watcher = start_config_watcher(app_state.event_hub)
        log_handler = attach_log_streamer(app_state)

        yield

        # Shutdown
        profile_task.cancel()
        try:
            await profile_task
        except asyncio.CancelledError:
            pass

        if watcher:
            watcher.stop()
            watcher.join()

        app_state.registry.stop_all()
        detach_log_streamer(log_handler)

    app = FastAPI(title="Devo Sidecar", version="1.0.0", lifespan=lifespan)
    app.state.app_state = app_state

    # Body size limit: reject oversize payloads with 413 *before* they hit
    # any handler. This protects against accidental DoS via huge JSON
    # bodies (a developer mistake with a large base64 file, for example).
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)

    # Audit log: persist one JSONL record per request. Placed *inside*
    # the CORS middleware chain so the logged path is the canonical API
    # path (no preflight OPTIONS noise).
    from cli_tool.sidecar.services.audit_service import AuditLogMiddleware

    app.add_middleware(AuditLogMiddleware)

    # Rate limiting: SlowAPIMiddleware inspects the WSGI scope for the
    # `slowapi` extension that `@limiter.limit` decorators populate.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Allow requests only from the Tauri webview and the local Vite dev
    # server. The allowlist is overridable via DEVO_SIDECAR_ALLOWED_ORIGINS
    # (comma-separated) for staging / E2E environments. Bare `http://localhost`
    # and `http://127.0.0.1` are intentionally excluded because they would
    # let any local app hit the sidecar.
    allowed_origins_env = os.environ.get("DEVO_SIDECAR_ALLOWED_ORIGINS", "").strip()
    if allowed_origins_env:
        allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
    else:
        allowed_origins = list(_DEFAULT_ALLOWED_ORIGINS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api/v1"
    app.include_router(preflight.router, prefix=api_prefix)
    app.include_router(version.router, prefix=api_prefix)
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(audit.router, prefix=api_prefix)
    app.include_router(config.router, prefix=api_prefix)
    app.include_router(databases.router, prefix=api_prefix)
    app.include_router(instances.router, prefix=api_prefix)
    app.include_router(hosts.router, prefix=api_prefix)
    app.include_router(profiles.router, prefix=api_prefix)
    app.include_router(connections.router, prefix=api_prefix)
    app.include_router(ws.router, prefix=api_prefix)
    app.include_router(log_router.router, prefix=api_prefix)
    app.include_router(codeartifact.router, prefix=api_prefix)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    @app.get("/api/v1/openapi.json", include_in_schema=False)
    def openapi_spec():
        """Return the OpenAPI 3.x spec for the sidecar.

        Exposed so the frontend can fetch it at build/test time and
        verify that its `api.ts` client is still in sync with the
        backend. The response schema is the standard `fastapi.openapi`
        shape, with a few extra fields (`info.title`, `info.version`)
        customized for Devo.
        """
        return app.openapi()

    return app


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured cap.

    FastAPI/Starlette will happily buffer a 100 MB body in memory if the
    handler is async. We short-circuit at the middleware layer with a 413
    so the buffer is never allocated. The cap is enforced on Content-Length
    only — chunked transfer-encoding is not used by the desktop client.
    """

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
            if size > self.max_bytes:
                logger.warning(
                    "Rejected oversize request: %s %s (%d bytes > %d)",
                    request.method,
                    request.url.path,
                    size,
                    self.max_bytes,
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": (f"Request body too large ({size} bytes; " f"max {self.max_bytes})")},
                )
        return await call_next(request)
