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
def live_sidecar(tmp_path_factory):
    """Spawn a real uvicorn sidecar (slowapi active) on a free port."""
    env = os.environ.copy()
    env.pop("DEVO_TESTING", None)
    env["PYTHONUNBUFFERED"] = "1"

    # Isolate from user's real config so start_all doesn't hit AWS
    tmp_home = str(tmp_path_factory.mktemp("home"))
    env["HOME"] = tmp_home
    env["USERPROFILE"] = tmp_home

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


def _trigger_429(url: str, token: str) -> None:
    """POST until 429 is returned *with* CORS header."""
    for i in range(35):
        try:
            with urllib.request.urlopen(_post(url, token), timeout=1.0) as r:
                pass  # Success, keep hitting
        except urllib.error.HTTPError as e:
            if e.code == 429:
                cors = e.headers.get("Access-Control-Allow-Origin")
                assert cors == "http://localhost:5173", (
                    f"{url}: 429 missing CORS header. Browser will block and report "
                    f"'Origin not allowed by Access-Control-Allow-Origin'. "
                    f"Headers: {dict(e.headers)}"
                )
                return
            else:
                pytest.fail(f"call to {url} failed: {e.code} {e.read()!r}")
        except (urllib.error.URLError, TimeoutError):
            pass  # timeout is fine, request still counts against rate limit

    pytest.fail(f"Did not receive 429 from {url} after 35 calls")


def test_refresh_all_cors_on_429(live_sidecar):
    port, token = live_sidecar
    _trigger_429(f"http://127.0.0.1:{port}/api/v1/profiles:refresh_all", token)


def test_start_all_cors_on_429(live_sidecar):
    port, token = live_sidecar
    _trigger_429(f"http://127.0.0.1:{port}/api/v1/connections:start_all", token)
