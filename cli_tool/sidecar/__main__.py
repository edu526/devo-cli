"""PyInstaller / python -m cli_tool.sidecar entry point."""

import sys

from cli_tool.sidecar.bootstrap import run

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Devo sidecar server")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--log-level", default="warning")
    args = parser.parse_args(sys.argv[1:])
    run(port=args.port, host=args.host, log_level=args.log_level)
