"""Shell completion installer."""

from pathlib import Path
from typing import Optional


class CompletionInstaller:
    """Manages shell completion installation."""

    SHELL_CONFIGS = {
        "bash": {
            "line": 'eval "$(_DEVO_COMPLETE=bash_source devo)"',
            "file": Path.home() / ".bashrc",
        },
        "zsh": {
            "line": 'eval "$(_DEVO_COMPLETE=zsh_source devo)"',
            "file": Path.home() / ".zshrc",
        },
        "fish": {
            "line": "_DEVO_COMPLETE=fish_source devo | source",
            "file": Path.home() / ".config" / "fish" / "config.fish",
        },
    }

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

    @classmethod
    def is_supported_shell(cls, shell_name: str) -> bool:
        """Check if shell is supported."""
        return shell_name in cls.SHELL_CONFIGS

    @classmethod
    def get_instructions(cls, shell_name: str) -> Optional[str]:
        """Get manual installation instructions for shell."""
        return cls.SHELL_INSTRUCTIONS.get(shell_name)

    @classmethod
    def is_already_configured(cls, shell_name: str) -> bool:
        """Check if completion is already configured for shell."""
        if shell_name not in cls.SHELL_CONFIGS:
            return False

        rc_file = cls.SHELL_CONFIGS[shell_name]["file"]
        if not rc_file.exists():
            return False

        content = rc_file.read_text()
        return "_DEVO_COMPLETE" in content

    @classmethod
    def install(cls, shell_name: str) -> tuple[bool, str]:
        """Install completion for shell.

        Args:
            shell_name: Name of the shell (bash, zsh, fish)

        Returns:
            Tuple of (success, message)
        """
        if shell_name not in cls.SHELL_CONFIGS:
            return False, f"Unsupported shell: {shell_name}"

        config = cls.SHELL_CONFIGS[shell_name]
        rc_file = config["file"]
        completion_line = config["line"]

        # Check if already configured
        if cls.is_already_configured(shell_name):
            return True, f"Shell completion already configured in {rc_file}"

        try:
            # Create parent directory if it doesn't exist (for fish)
            rc_file.parent.mkdir(parents=True, exist_ok=True)

            # Add completion
            with open(rc_file, "a") as f:
                f.write("\n# Devo CLI completion\n")
                f.write(f"{completion_line}\n")

            return True, f"Shell completion configured in {rc_file}"

        except Exception as e:
            return False, f"Error setting up completion: {e}"

    @classmethod
    def get_config_file(cls, shell_name: str) -> Optional[Path]:
        """Get the config file path for shell."""
        if shell_name not in cls.SHELL_CONFIGS:
            return None
        return cls.SHELL_CONFIGS[shell_name]["file"]

    @classmethod
    def get_completion_line(cls, shell_name: str) -> Optional[str]:
        """Get the completion line for shell."""
        if shell_name not in cls.SHELL_CONFIGS:
            return None
        return cls.SHELL_CONFIGS[shell_name]["line"]
