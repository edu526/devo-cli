# devo autocomplete

Setup shell autocomplete for Devo CLI.

## Synopsis

```bash
devo autocomplete [OPTIONS]
```

## Description

Detects your shell and shows/installs shell autocomplete. By default, shows instructions for manual setup. Use `--install` to automatically add autocomplete to your shell config.

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--install` | `-i` | Automatically install autocomplete to shell config |
| `--yes` | `-y` | Skip confirmation prompt when installing |
| `--help` | | Show help message and exit |

## Supported Shells

- **bash** - Bourne Again Shell
- **zsh** - Z Shell
- **fish** - Friendly Interactive Shell

The command automatically detects your current shell.

## Usage

### Show Instructions (Default)

```bash
devo autocomplete
```

Shows manual installation instructions for your shell.

### Automatic Installation

```bash
# Install with confirmation
devo autocomplete --install

# Install without confirmation
devo autocomplete --install --yes
```

The command will:

1. Detect your shell
2. Add autocomplete configuration to your shell config file
3. Show instructions to reload your shell

## Installation Details

=== "Bash"

    Adds to `~/.bashrc`:

    ```bash
    eval "$(_DEVO_COMPLETE=bash_source devo)"
    ```

    Reload:

    ```bash
    source ~/.bashrc
    ```

=== "Zsh"

    Adds to `~/.zshrc`:

    ```bash
    eval "$(_DEVO_COMPLETE=zsh_source devo)"
    ```

    Reload:

    ```bash
    source ~/.zshrc
    ```

=== "Fish"

    Adds to `~/.config/fish/completions/devo.fish`:

    ```fish
    eval (env _DEVO_COMPLETE=fish_source devo)
    ```

    Reload:

    ```fish
    source ~/.config/fish/config.fish
    ```

## Examples

### Basic Usage

```bash
# Show instructions
devo autocomplete

# Install automatically
devo autocomplete --install
```

### After Installation

```bash
# Type 'devo ' and press TAB
devo <TAB>

# Shows available commands:
autocomplete  aws-login  code-reviewer  commit  config  ...

# Type 'devo aws-login ' and press TAB
devo aws-login <TAB>

# Shows subcommands:
configure  list  login  refresh  set-default
```

## Features

- **Auto-detection**: Automatically detects your shell
- **Safe Installation**: Checks if already installed before adding
- **Multiple Shells**: Supports bash, zsh, and fish
- **Command Completion**: Complete command names
- **Option Completion**: Complete option flags
- **Argument Completion**: Complete file paths and values

## Troubleshooting

### Completion not working after installation

**Solution:** Reload your shell configuration:

=== "Bash"

    ```bash
    source ~/.bashrc
    ```

=== "Zsh"

    ```bash
    source ~/.zshrc
    ```

=== "Fish"

    ```fish
    source ~/.config/fish/config.fish
    ```

Or restart your terminal.

### "Command not found: _DEVO_COMPLETE"

**Solution:** Ensure Devo CLI is in your PATH:

```bash
which devo
# Should show the path to devo binary
```

### Completion shows old commands

**Solution:** Reinstall autocomplete:

```bash
devo autocomplete --install --yes
source ~/.bashrc  # or ~/.zshrc
```

## Manual Installation

If automatic installation doesn't work, add the completion code manually:

=== "Bash"

    Edit `~/.bashrc`:

    ```bash
    eval "$(_DEVO_COMPLETE=bash_source devo)"
    ```

=== "Zsh"

    Edit `~/.zshrc`:

    ```bash
    eval "$(_DEVO_COMPLETE=zsh_source devo)"
    ```

=== "Fish"

    Create `~/.config/fish/completions/devo.fish`:

    ```fish
    eval (env _DEVO_COMPLETE=fish_source devo)
    ```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (unsupported shell, installation failed, etc.) |

## See Also

- [Shell Completion Guide](../guides/shell-completion.md) - Detailed setup guide
- [Installation](../getting-started/installation.md) - Install Devo CLI

## Notes

- Requires Devo CLI to be installed and in PATH
- Completion is powered by Click framework
- Works with all Devo CLI commands and options
- Updates automatically when new commands are added
