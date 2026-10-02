"""PyInstaller / python -m cli_tool.sidecar entry point."""

import sys

# Force UTF-8 encoding for standard output and error to prevent UnicodeEncodeError
# on Windows when printing symbols like '✓'
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from cli_tool.sidecar import hosts_cli
from cli_tool.sidecar.bootstrap import run

if __name__ == "__main__":
    import argparse

    # Elevated hosts-file writes re-invoke this binary as
    # `devo-sidecar -m cli_tool.cli ssm hosts ...` (see hosts_cli).
    if hosts_cli.is_cli_invocation(sys.argv[1:]):
        hosts_cli.run(sys.argv[1:])

    parser = argparse.ArgumentParser(description="Devo sidecar server")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--log-level", default="warning")
    args = parser.parse_args(sys.argv[1:])
    run(port=args.port, host=args.host, log_level=args.log_level)
