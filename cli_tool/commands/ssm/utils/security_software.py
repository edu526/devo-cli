"""Which antivirus Windows reports as active, to name what blocks the hosts file."""

import json
import platform
import subprocess
from typing import Any

_QUERY = (
    "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | "
    "Select-Object displayName, productState | ConvertTo-Json -Compress"
)


def active_antivirus() -> list[str]:
    """Display names of the antivirus products Windows Security Center reports
    as on (e.g. ["Kaspersky"]). Empty off Windows or when it can't be asked."""
    if platform.system() != "Windows":
        return []
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _QUERY],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        products: Any = json.loads(result.stdout or "[]")
    except Exception:
        return []
    if isinstance(products, dict):
        products = [products]
    return [p["displayName"] for p in products if isinstance(p, dict) and p.get("displayName") and _scanner_on(p.get("productState"))]


def _scanner_on(product_state: Any) -> bool:
    """Bits 8-15 of productState are the real-time scanner: 0x10/0x11 on,
    0x00/0x01 off (e.g. Windows Defender goes off while another antivirus runs)."""
    try:
        return (int(product_state) >> 8) & 0x10 == 0x10
    except (TypeError, ValueError):
        return False
