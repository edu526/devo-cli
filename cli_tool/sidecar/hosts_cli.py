"""Minimal `cli_tool.cli` stand-in for the frozen sidecar binary.

The desktop app elevates hosts-file writes by running
`<python_bin> -m cli_tool.cli ssm hosts <cmd> ...`, where `python_bin` is the
sidecar's `sys.executable`. In a PyInstaller build that is `devo-sidecar(.exe)`,
which has no `-m` support — so `__main__` routes that argv shape here, exposing
only the `ssm hosts` commands (the full CLI isn't bundled in the sidecar).
"""

import click

from cli_tool.commands.ssm.commands.hosts import register_hosts_commands

MODULE_FLAG = ["-m", "cli_tool.cli"]


@click.group()
def cli():
    """Devo hosts management (sidecar)."""


@cli.group()
def ssm():
    """SSM commands."""


register_hosts_commands(ssm)


def is_cli_invocation(argv: list[str]) -> bool:
    return argv[:2] == MODULE_FLAG


def run(argv: list[str]) -> None:
    cli.main(args=argv[2:], prog_name="devo")
