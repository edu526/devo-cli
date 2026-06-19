"""Shared slowapi limiter instance for the sidecar.

A single Limiter is wired up here so the SlowAPIMiddleware and the
`@limiter.limit(...)` decorators on individual endpoints share state.
The default key function is the client's IP — acceptable because the
sidecar binds to 127.0.0.1.

The limiter is replaced with a no-op shim when DEVO_TESTING=1 (set by
tests/conftest.py). Slowapi's extension depends on the ASGI middleware
tracking the response, which is fragile under fastapi.testclient.TestClient
— we sidestep the issue by swapping in a `Limiter(enabled=False, ...)`
instance for the duration of the test run. The decorators still match
their `limiter.limit(...)` calls (the shim is a real Limiter), so
production wiring is unchanged.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _build_limiter() -> Limiter:
    if os.environ.get("DEVO_TESTING") == "1":
        return Limiter(key_func=get_remote_address, enabled=False)
    return Limiter(key_func=get_remote_address, headers_enabled=True)


# `headers_enabled=True` makes slowapi attach `X-RateLimit-Limit`,
# `X-RateLimit-Remaining` and `Retry-After` headers on 429 responses.
limiter = _build_limiter()
