import os
from pathlib import Path

import click

# https://click.palletsprojects.com/en/stable/shell-completion/
SHELL_INSTRUCTIONS = {
    "bash": """To enable shell completion in Bash, run:

  eval "$(_DEVO_COMPLETE=bash_source devo)"

To make it permanent, add that line to your `~/.bashrc` file.""",
    "zsh": """To enable shell completion in Zsh, run:

  eval "$(_DEVO_COMPLETE=zsh_source devo)"

To make it permanent, add that line to your `~/.zshrc` file.""",
    "fish": """To enable shell completion in Fish, run:

  _DEVO_COMPLETE=fish_source devo | source

To make it permanent, add that line to your `~/.config/fish/config.fish` file.""",
}


def setup_completion_for_shell(shell_name: str, auto_confirm: bool = False) -> bool:
    """Setup shell completion for the given shell.

    Args:
        shell_name: Name of the shell (bash, zsh, fish)
        auto_confirm: If True, skip confirmation prompt

    Returns:
        True if setup was successful, False otherwise
    """
    completion_configs = {
        "bash": {"line": 'eval "$(_DEVO_COMPLETE=bash_source devo)"', "file": Path.home() / ".bashrc"},
        "zsh": {"line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"', "file": Path.home() / ".zshrc"},
        "fish": {"line": "_DEVO_COMPLETE=fish_source devo | source", "file": Path.home() / ".config" / "fish" / "config.fish"},
    }

    if shell_name not in completion_configs:
        return False

    config = completion_configs[shell_name]
    rc_file = config["file"]
    completion_line = config["line"]

    # Check if already configured
    if rc_file.exists():
        content = rc_file.read_text()
        if "_DEVO_COMPLETE" in content:
            click.echo(f"✅ Shell completion already configured in {rc_file}")
            return True

    # Ask for confirmation unless auto_confirm is True
    if not auto_confirm:
        click.echo(f"\nThis will add the following line to {rc_file}:")
        click.echo(f"  {completion_line}")
        click.echo()
        if not click.confirm("Do you want to continue?"):
            click.echo("Setup cancelled")
            return False

    try:
        # Create parent directory if it doesn't exist (for fish)
        rc_file.parent.mkdir(parents=True, exist_ok=True)

        # Add completion
        with open(rc_file, "a") as f:
            f.write("\n# Devo CLI completion\n")
            f.write(f"{completion_line}\n")

        click.echo(f"\n✅ Shell completion configured in {rc_file}")
        click.echo("\n💡 To activate it now, run:")
        click.echo(f"  source {rc_file}")
        return True

    except Exception as e:
        click.echo(f"\n❌ Error setting up completion: {e}", err=True)
        return False


@click.group()
def cli():
    pass


@cli.command()
@click.option("--install", "-i", is_flag=True, help="Automatically install completion to shell config")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt when installing")
def completion(install, yes):
    """Detects your shell and shows/installs shell completion.

    By default, shows instructions for manual setup.
    Use --install to automatically add completion to your shell config.
    """
    shell = os.environ.get("SHELL", "")
    shell_name = os.path.basename(shell).lower().replace(".exe", "")

    click.echo(f"🔍 Detected shell: {shell_name}")
    click.echo()

    if shell_name not in SHELL_INSTRUCTIONS:
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
        setup_completion_for_shell(shell_name, auto_confirm=yes)
    else:
        # Show manual instructions
        click.echo(SHELL_INSTRUCTIONS[shell_name])
        click.echo()
        click.echo("💡 Tip: Use 'devo completion --install' to set it up automatically")


if __name__ == "__main__":
    cli()
