"""Devo CLI branding — ASCII banner, version header, and identity constants."""

from contextlib import contextmanager
from io import StringIO

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner

TAGLINE = "Developer productivity CLI · AI-powered workflows"
WEBSITE = "devo.heyedu.dev"
WEBSITE_URL = "https://devo.heyedu.dev"
WEBSITE_LINK = f"[link={WEBSITE_URL}]{WEBSITE}[/link]"

# fmt: off
BANNER = (
    " ██████╗ ███████╗██╗   ██╗ ██████╗ \n"
    " ██╔══██╗██╔════╝██║   ██║██╔═══██╗\n"
    " ██║  ██║█████╗  ██║   ██║██║   ██║\n"
    " ██║  ██║██╔══╝  ╚██╗ ██╔╝██║   ██║\n"
    " ██████╔╝███████╗ ╚████╔╝ ╚██████╔╝\n"
    " ╚═════╝ ╚══════╝  ╚═══╝   ╚═════╝ "
)
# fmt: on


def _get_version() -> str:
    try:
        from cli_tool._version import version

        return version
    except ImportError:
        return "unknown"


def render_banner(console: Console | None = None) -> None:
    """Print the Devo ASCII banner with tagline to the given console."""
    _c = console or Console()
    _c.print(f"[bold cyan]{BANNER}[/bold cyan]")
    _c.print(f"  [dim]{TAGLINE}[/dim]  [dim cyan]{WEBSITE_LINK}[/dim cyan]\n")


def render_version_header(console: Console | None = None) -> None:
    """Print the branded version panel (with DEV badge when applicable)."""
    _c = console or Console()
    raw = _get_version()
    is_dev = ".dev" in raw or "+" in raw
    base_version = raw.split(".dev")[0].split("+")[0]

    version_line = f"[bold cyan]devo[/bold cyan]  [cyan]v{base_version}[/cyan]"
    if is_dev:
        version_line += "  [bold yellow on dark_orange] DEV [/bold yellow on dark_orange]"

    _c.print(
        Panel(
            f"{version_line}\n" f"[dim]{'─' * 44}[/dim]\n" f"[dim]{TAGLINE}[/dim]\n" f"[dim cyan]{WEBSITE_LINK}[/dim cyan]",
            border_style="cyan",
            padding=(0, 2),
            expand=False,
        )
    )


def banner_as_ansi(width: int = 80) -> str:
    """Return the banner as an ANSI-coded string (for embedding in Click help output)."""
    sio = StringIO()
    c = Console(file=sio, force_terminal=True, highlight=False, width=width)
    render_banner(c)
    return sio.getvalue()


@contextmanager
def spinner(message: str, style: str = "cyan"):
    """Context manager that shows an animated spinner while a block runs.

    Usage::

        from cli_tool.core.ui.brand import spinner

        with spinner("Fetching DynamoDB tables..."):
            tables = get_tables()
    """
    _console = Console()
    widget = Spinner("dots", text=f" [{style}]{message}[/{style}]")
    with Live(widget, console=_console, transient=True, refresh_per_second=12):
        yield
