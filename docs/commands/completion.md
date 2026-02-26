# devo completion

Generate shell completion scripts for Devo CLI.

## Overview

The `completion` command generates shell completion scripts that enable tab completion for Devo CLI commands, options, and arguments.

## Usage

```bash
devo completion [SHELL]
```

**Supported Shells:**

- `bash`
- `zsh`
- `fish`

If no shell is specified, the command detects your current shell automatically.

## Installation

### Bash

Add to `~/.bashrc`:

```bash
eval "$(_DEVO_COMPLETE=bash_source devo)"
```

Then reload:

```bash
source ~/.bashrc
```

### Zsh

Add to `~/.zshrc`:

```bash
eval "$(_DEVO_COMPLETE=zsh_source devo)"
```

Then reload:

```bash
source ~/.zshrc
```

### Fish

Add to `~/.config/fish/config.fish`:

```fish
_DEVO_COMPLETE=fish_source devo | source
```

Then reload:

```fish
source ~/.config/fish/config.fish
```

## Quick Setup

Run the completion command to get shell-specific instructions:

```bash
devo completion
```

This will:

1. Detect your current shell
2. Show installation instructions
3. Optionally install automatically (if supported)

## Examples

### Generate Completion Script

```bash
# For current shell
devo completion

# For specific shell
devo completion bash
devo completion zsh
devo completion fish
```

### Save to File

```bash
# Bash
devo completion bash > ~/.bash_completions/devo

# Zsh
devo completion zsh > ~/.zsh/completions/_devo

# Fish
devo completion fish > ~/.config/fish/completions/devo.fish
```

## Features

Once installed, tab completion provides:

### Command Completion

```bash
devo <TAB>
# Shows: code-reviewer  codeartifact-login  commit  completion  config  dynamodb  eventbridge  upgrade
```

### Option Completion

```bash
devo commit --<TAB>
# Shows: --add  --all  --help  --profile  --pull-request  --push
```

### Subcommand Completion

```bash
devo config <TAB>
# Shows: edit  export  get  import  path  reset  set  show  validate
```

### Profile Completion

```bash
devo --profile <TAB>
# Shows available AWS profiles from ~/.aws/config
```

## Verification

Test completion is working:

```bash
# Type and press TAB
devo c<TAB>

# Should complete or show:
# code-reviewer  codeartifact-login  commit  completion  config
```

## Troubleshooting

### Completion Not Working

1. **Reload shell configuration:**
   ```bash
   source ~/.bashrc  # or ~/.zshrc
   ```

2. **Verify devo is in PATH:**
   ```bash
   which devo
   ```

3. **Check completion is loaded:**
   ```bash
   # Bash
   complete -p devo

   # Zsh
   echo $_comps[devo]
   ```

### Slow Completion

Generate static completion file:

```bash
# Bash
_DEVO_COMPLETE=bash_source devo > ~/.bash_completions/devo
source ~/.bash_completions/devo

# Zsh
_DEVO_COMPLETE=zsh_source devo > ~/.zsh/completions/_devo
# Add to fpath in ~/.zshrc:
fpath=(~/.zsh/completions $fpath)
```

### Wrong Shell Detected

Specify shell explicitly:

```bash
devo completion bash
devo completion zsh
devo completion fish
```

## Uninstalling

Remove completion configuration from your shell profile:

### Bash

Remove from `~/.bashrc`:
```bash
# Remove this line:
eval "$(_DEVO_COMPLETE=bash_source devo)"
```

### Zsh

Remove from `~/.zshrc`:
```bash
# Remove this line:
eval "$(_DEVO_COMPLETE=zsh_source devo)"
```

### Fish

Remove from `~/.config/fish/config.fish`:
```fish
# Remove this line:
_DEVO_COMPLETE=fish_source devo | source
```

Then reload your shell.

## Advanced Usage

### Custom Completion Location

```bash
# Create completion directory
mkdir -p ~/.local/share/bash-completion/completions

# Generate completion
_DEVO_COMPLETE=bash_source devo > ~/.local/share/bash-completion/completions/devo

# Add to ~/.bashrc
source ~/.local/share/bash-completion/completions/devo
```

### Multiple Shells

If you use multiple shells, install completion for each:

```bash
# Bash
eval "$(_DEVO_COMPLETE=bash_source devo)" >> ~/.bashrc

# Zsh
eval "$(_DEVO_COMPLETE=zsh_source devo)" >> ~/.zshrc

# Fish
echo "_DEVO_COMPLETE=fish_source devo | source" >> ~/.config/fish/config.fish
```

## See Also

- [Shell Completion Guide](../guides/shell-completion.md) - Detailed completion setup
- [Installation](../getting-started/installation.md) - Installation guide
- [Commands Overview](index.md) - All available commands
