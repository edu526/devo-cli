"""Shell autocomplete command."""

import os

import click

from cli_tool.commands.autocomplete.core import CompletionInstaller


@click.command()
@click.option("--install", "-i", is_flag=True, help="Automatically install autocomplete to shell config")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt when installing")
def autocomplete(install, yes):
    """Detects your shell and shows/installs shell autocomplete.

    By default, shows instructions for manual setup.
    Use --install to automatically add autocomplete to your shell config.
    """
    shell = os.environ.get("SHELL", "")
    shell_name = os.path.basename(shell).lower().replace(".exe", "")

    click.echo(f"🔍 Detected shell: {shell_name}")
    click.echo()

    if not CompletionInstaller.is_supported_shell(shell_name):
        click.echo("⚠️  Your shell is not officially supported by Click.")
        click.echo()
        click.echo("Supported shells:")
        click.echo("  • bash (version 4.4+)")
        click.echo("  • zsh")
        click.echo("  • fish")
        click.echo()
        click.echo("If you're using a different shell, you may need to:")
        click.echo("  1. Switch to a supported shell for completion")
        click.echo("  2. Check PyPI for third-party completion packages")
        click.echo("  3. Implement custom completion for your shell")
        return

    # If --install flag is provided, setup automatically
    if install:
        _install_completion(shell_name, yes)
    else:
        _show_instructions(shell_name)


def _install_completion(shell_name: str, auto_confirm: bool):
    """Install completion for shell."""
    rc_file = CompletionInstaller.get_config_file(shell_name)
    completion_line = CompletionInstaller.get_completion_line(shell_name)

    # Check if already configured
    if CompletionInstaller.is_already_configured(shell_name):
        click.echo(f"✅ Shell completion already configured in {rc_file}")
        return

    # Ask for confirmation unless auto_confirm is True
    if not auto_confirm:
        click.echo(f"\nThis will add the following line to {rc_file}:")
        click.echo(f"  {completion_line}")
        click.echo()
        if not click.confirm("Do you want to continue?"):
            click.echo("Setup cancelled")
            return

    # Install completion
    success, message = CompletionInstaller.install(shell_name)

    if success:
        click.echo(f"\n✅ {message}")
        click.echo("\n💡 To activate it now, run:")
        click.echo(f"  source {rc_file}")
    else:
        click.echo(f"\n❌ {message}", err=True)


def _show_instructions(shell_name: str):
    """Show manual installation instructions."""
    instructions = CompletionInstaller.get_instructions(shell_name)
    click.echo(instructions)
    click.echo()
    click.echo("💡 Tip: Use 'devo autocomplete --install' to set it up automatically")
