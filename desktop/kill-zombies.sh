#!/usr/bin/env bash
set +e

# Kill any running devo or devo-sidecar processes
pkill -9 -x 'devo' 2>/dev/null
pkill -9 -x 'devo-sidecar' 2>/dev/null

# Clean up vite dev server if it got orphaned
lsof -i :5173 -t | xargs -r kill -9 2>/dev/null

# Kill python processes running the sidecar module
pkill -9 -f 'cli_tool.sidecar' 2>/dev/null

exit 0
