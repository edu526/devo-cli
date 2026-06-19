"""Regression: rate-limited endpoints must return CORS headers on 429.

slowapi injects X-RateLimit-* headers into the response object after
the handler returns. When the handler signature is just
``(request: Request) -> dict``, slowapi's _inject_headers raises
``Exception: parameter 'response' must be an instance of
starlette.responses.Response`` — which propagates as a 500 *without*
CORS headers, and the browser console reports it as a CORS error.

The fix: every rate-limited endpoint must accept a
``response: Response`` parameter so slowapi has a real Response object
to mutate. The pattern is also documented in slowapi's README.

This test exercises all four rate-limited endpoints against a real
uvicorn subprocess (slowapi does not behave the same way under
TestClient — see tests/conftest.py for why DEVO_TESTING=1 disables
the limiter in unit tests).
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Mark this as a slow integration test.
import pytest

pytestmark = pytest.mark.integration


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return True
            except OSError:
                time.sleep(0.1)
    return False


@pytest.fixture(scope="module")
def live_sidecar():
    """Spawn a real uvicorn sidecar (slowapi active) on a free port."""
    env = os.environ.copy()
    env.pop("DEVO_TESTING", None)
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "cli_tool.sidecar", "--port", "0"],
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    port = token = None
    try:
        deadline = time.time() + 10
        for line in proc.stdout:
            if "DEVO_SIDECAR_READY" in line:
                for part in line.split():
                    if part.startswith("port="):
                        port = int(part.split("=", 1)[1])
                    elif part.startswith("token="):
                        token = part.split("=", 1)[1]
                break
            if time.time() > deadline:
                break
        assert port and token, f"sidecar did not print READY in time (port={port}, token={token})"
        assert _wait_for_port("127.0.0.1", port, timeout=5.0), f"port {port} not bound"
        yield port, token
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _post(url: str, token: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        method="POST",
        headers={
            "Origin": "http://localhost:5173",
            "Authorization": f"Bearer {token}",
        },
    )


def _hit_twice(url: str, token: str) -> None:
    """POST twice, second call must 429 *with* CORS header."""
    try:
        with urllib.request.urlopen(_post(url, token), timeout=5) as r1:
            assert r1.status in (200, 202), f"first call: {r1.status} {r1.read()!r}"
            assert r1.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    except urllib.error.HTTPError as e:
        pytest.fail(f"first call to {url} failed: {e.code} {e.read()!r}")

    try:
        with urllib.request.urlopen(_post(url, token), timeout=5) as r2:
            pytest.fail(f"second call to {url} should have been 429, got {r2.status}")
    except urllib.error.HTTPError as e:
        assert e.code == 429, f"second call to {url}: expected 429, got {e.code}"
        cors = e.headers.get("Access-Control-Allow-Origin")
        assert cors == "http://localhost:5173", (
            f"{url}: 429 missing CORS header. Browser will block and report "
            f"'Origin not allowed by Access-Control-Allow-Origin'. "
            f"Headers: {dict(e.headers)}"
        )


def test_refresh_all_cors_on_429(live_sidecar):
    port, token = live_sidecar
    _hit_twice(f"http://127.0.0.1:{port}/api/v1/profiles:refresh_all", token)


def test_start_all_cors_on_429(live_sidecar):
    port, token = live_sidecar
    _hit_twice(f"http://127.0.0.1:{port}/api/v1/connections:start_all", token)
