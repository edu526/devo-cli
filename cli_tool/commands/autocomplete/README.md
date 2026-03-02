# Shell Autocomplete

Shell autocomplete support for Devo CLI using Click's built-in completion system.

## Features

- Auto-detects current shell (bash, zsh, fish)
- Shows manual installation instructions
- Automatic installation with `--install` flag
- Checks if autocomplete is already configured
- Supports confirmation prompts (can be skipped with `--yes`)

## Usage

### Show Instructions

```bash
devo autocomplete
```

Detects your shell and shows manual installation instructions.

### Auto-Install

```bash
devo autocomplete --install
```

Automatically adds autocomplete to your shell config file with confirmation prompt.

### Auto-Install (Skip Confirmation)

```bash
devo autocomplete --install --yes
```

Installs without asking for confirmation.

## Supported Shells

- **bash** (version 4.4+) - Adds to `~/.bashrc`
- **zsh** - Adds to `~/.zshrc`
- **fish** - Adds to `~/.config/fish/config.fish`

## Architecture

### Commands Layer (`commands/`)

- `autocomplete.py` - CLI command with Click decorators
  - Detects shell from `$SHELL` environment variable
  - Handles user interaction and output formatting
  - Delegates logic to `CompletionInstaller`

### Core Layer (`core/`)

- `installer.py` - `CompletionInstaller` class
  - Shell configuration management
  - Installation logic
  - Validation and checks
  - No Click dependencies

## How It Works

1. Reads `$SHELL` environment variable
2. Extracts shell name (bash, zsh, fish)
3. Checks if shell is supported
4. Shows instructions or installs based on flags
5. Verifies if autocomplete is already configured
6. Adds completion line to appropriate config file

## Completion Lines

- **bash**: `eval "$(_DEVO_COMPLETE=bash_source devo)"`
- **zsh**: `eval "$(_DEVO_COMPLETE=zsh_source devo)"`
- **fish**: `_DEVO_COMPLETE=fish_source devo | source`

## Configuration Files

- **bash**: `~/.bashrc`
- **zsh**: `~/.zshrc`
- **fish**: `~/.config/fish/config.fish`

## Examples

### Manual Setup (bash)

```bash
$ devo autocomplete
🔍 Detected shell: bash

To enable shell completion in Bash, run:

  eval "$(_DEVO_COMPLETE=bash_source devo)"

To make it permanent, add that line to your `~/.bashrc` file.

💡 Tip: Use 'devo autocomplete --install' to set it up automatically
```

### Automatic Installation

```bash
$ devo autocomplete --install
🔍 Detected shell: bash

This will add the following line to /home/user/.bashrc:
  eval "$(_DEVO_COMPLETE=bash_source devo)"

Do you want to continue? [y/N]: y

✅ Shell completion configured in /home/user/.bashrc

💡 To activate it now, run:
  source /home/user/.bashrc
```

### Already Configured

```bash
$ devo autocomplete --install
🔍 Detected shell: bash

✅ Shell completion already configured in /home/user/.bashrc
```

## References

- [Click Shell Completion Documentation](https://click.palletsprojects.com/en/stable/shell-completion/)
