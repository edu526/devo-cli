"""devo sidecar — desktop sidecar server commands."""

import click


@click.group("sidecar")
def sidecar():
    """Desktop sidecar HTTP/WS server."""


@sidecar.command("serve")
@click.option("--port", default=0, show_default=True, help="Port to listen on (0 = random free port).")
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option(
    "--log-level",
    default="warning",
    show_default=True,
    type=click.Choice(["critical", "error", "warning", "info", "debug"], case_sensitive=False),
)
def serve(port: int, host: str, log_level: str):
    """Start the sidecar server. Prints DEVO_SIDECAR_READY to stdout when bound."""
    from cli_tool.sidecar.bootstrap import run

    run(port=port, host=host, log_level=log_level)
