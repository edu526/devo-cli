#!/usr/bin/env bash
# scripts/build_sidecar_placeholder.sh
#
# Generates a shell-wrapper placeholder for the devo-sidecar binary expected by
# Tauri (externalBin). The real PyInstaller-built binary is produced by the
# desktop.yml CI workflow and copied here; in dev this wrapper is used so
# `cargo check` succeeds without bundling the entire Python interpreter.
#
# Usage:
#   scripts/build_sidecar_placeholder.sh                       # auto-detect host triple
#   TRIPLE=x86_64-unknown-linux-gnu scripts/build_sidecar_placeholder.sh
#
# The wrapper simply exec's the Python module that lives in the monorepo
# virtualenv — same behavior as the debug-mode spawn in src-tauri/src/sidecar.rs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_DIR="$REPO_ROOT/desktop/src-tauri/binaries"

# Detect host triple (rustc target triple format)
if [ -z "${TRIPLE:-}" ]; then
    if command -v rustc >/dev/null 2>&1; then
        TRIPLE="$(rustc -vV | sed -n 's|host: ||p')"
    else
        case "$(uname -s)" in
            Linux*)   TRIPLE="$(uname -m)-unknown-linux-gnu" ;;
            Darwin*)  TRIPLE="$(uname -m)-apple-darwin" ;;
            MINGW*|MSYS*|CYGWIN*) TRIPLE="$(uname -m)-pc-windows-msvc" ;;
            *)        echo "ERROR: cannot detect triple, pass TRIPLE=..." >&2; exit 1 ;;
        esac
    fi
fi

mkdir -p "$BIN_DIR"
OUT="$BIN_DIR/devo-sidecar-${TRIPLE}"

# Windows .cmd wrapper, Unix shell wrapper
case "$TRIPLE" in
    *windows*)
        cat > "${OUT}.cmd" <<'EOF'
@echo off
rem Dev placeholder — replaced by PyInstaller binary in CI/release builds.
python -m cli_tool.sidecar %*
EOF
        OUT="${OUT}.cmd"
        ;;
    *)
        cat > "$OUT" <<'EOF'
#!/bin/sh
# Dev placeholder — replaced by PyInstaller binary in CI/release builds.
# In debug mode, src/sidecar.rs spawns python directly and never calls this file.
exec python3 -m cli_tool.sidecar "$@"
EOF
        chmod +x "$OUT"
        ;;
esac

echo "Wrote placeholder: $OUT"
