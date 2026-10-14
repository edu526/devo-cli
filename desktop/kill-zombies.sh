#!/usr/bin/env bash
# Kill the dev processes a previous `pnpm tauri dev` may have left behind.
#
# Only this checkout's: an installed Devo (devo-desktop and its own
# devo-sidecar) can be running at the same time and must survive, and `devo`
# is also the CLI's command name. Killing by name used to take them down too.
set +e

target="$(cd "$(dirname "$0")" && pwd)/src-tauri/target/"
# pkill matches a regex: escape the path
pattern="^$(printf '%s' "$target" | sed 's/[][\.*^$+?(){}|]/\\&/g')"

# The dev app and the dev sidecar wrapper
pkill -9 -f "$pattern" 2>/dev/null

# Clean up vite dev server if it got orphaned
lsof -i :5173 -t | xargs -r kill -9 2>/dev/null

# Python sidecars (`-m cli_tool.sidecar`) only exist in dev: an installed
# sidecar is the frozen devo-sidecar binary.
pkill -9 -f -- '-m cli_tool.sidecar' 2>/dev/null

exit 0
