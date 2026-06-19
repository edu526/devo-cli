"""GET /api/v1/version — no auth required.

Reports the sidecar build metadata. Used by the Tauri updater client
to decide whether to prompt the user to upgrade. `update_available` is
always false here — the desktop frontend consults the Tauri updater
plugin directly to check the upstream manifest.
"""

from typing import Any

from fastapi import APIRouter

from cli_tool._version import version as sidecar_version

router = APIRouter(tags=["version"])


def _build_version_payload() -> dict[str, Any]:
    return {
        "sidecar_version": sidecar_version,
        "server_version": sidecar_version,
        "build_date": _read_build_date(),
        "update_available": False,
    }


def _read_build_date() -> str | None:
    """Best-effort read of a build date baked into the PyInstaller bundle.

    The PyInstaller spec could embed a file; for now we fall back to None
    and rely on the sidecar_version for display.
    """
    return None


@router.get("/version")
def get_version() -> dict[str, Any]:
    return _build_version_payload()
