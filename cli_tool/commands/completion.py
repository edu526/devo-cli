import os

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


@click.group()
def cli():
    pass


@cli.command()
def completion():
    """Detects your shell and shows shell completion instructions."""
    shell = os.environ.get("SHELL", "")
    shell_name = os.path.basename(shell).lower().replace(".exe", "")

    click.echo(f"🔍 Detected shell: {shell_name}")

    if shell_name in SHELL_INSTRUCTIONS:
        click.echo(SHELL_INSTRUCTIONS[shell_name])
    else:
        click.echo("⚠️  Your shell is not officially supported (supported: bash, zsh, fish).")


if __name__ == "__main__":
    cli()
