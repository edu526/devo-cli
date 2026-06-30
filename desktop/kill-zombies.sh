#!/usr/bin/env bash
set +e

# Kill any running devo or devo-sidecar processes
pkill -9 -f 'devo' 2>/dev/null
pkill -9 -f 'devo-sidecar' 2>/dev/null

# Kill python processes running the sidecar module
pkill -9 -f 'cli_tool.sidecar' 2>/dev/null

exit 0
