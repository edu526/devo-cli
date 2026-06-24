"""Doctor command — runs environment diagnostics and reports status."""

import sys

import click
from rich.console import Console
from rich.table import Table

from cli_tool.commands.doctor.core.checks import run_checks
from cli_tool.core.ui import theme

_console = Console()


def _render(results: list[dict]) -> None:
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Status", width=9, no_wrap=True)
    table.add_column("Check", style="bold", width=24)
    table.add_column("Detail")

    for r in results:
        table.add_row(_status_label(r["status"]), r["name"], r["detail"])

    _console.print(table)
    _console.print(_summary_line(results))


def _status_label(status: str) -> str:
    if status == "ok":
        return f"[{theme.SUCCESS}]\u2713 ok[/{theme.SUCCESS}]"
    if status == "warn":
        return f"[{theme.WARNING}]\u26a0 warn[/{theme.WARNING}]"
    return f"[{theme.ERROR}]\u2717 fail[/{theme.ERROR}]"


def _summary_line(results: list[dict]) -> str:
    ok = sum(1 for r in results if r["status"] == "ok")
    warn = sum(1 for r in results if r["status"] == "warn")
    fail = sum(1 for r in results if r["status"] == "error")
    parts = [f"[{theme.SUCCESS}]{ok} ok[/{theme.SUCCESS}]"]
    if warn:
        parts.append(f"[{theme.WARNING}]{warn} warning{'s' if warn != 1 else ''}[/{theme.WARNING}]")
    if fail:
        parts.append(f"[{theme.ERROR}]{fail} failure{'s' if fail != 1 else ''}[/{theme.ERROR}]")
    summary = " \u00b7 ".join(parts)
    return f"\n{summary} \u2014 {len(results)} checks"


@click.command()
def doctor():
    """Diagnose devo-cli installation and environment."""
    results = run_checks()
    _render(results)
    has_failures = any(r["status"] == "error" for r in results)
    sys.exit(1 if has_failures else 0)
