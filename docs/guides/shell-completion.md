# Shell Completion Guide

Enable tab completion for Devo CLI commands in your shell.

## Overview

Shell completion allows you to:

- Press TAB to autocomplete commands
- See available options and subcommands
- Speed up command entry
- Discover commands interactively

## Quick Setup

### Zsh

Add to `~/.zshrc`:

```bash
eval "$(_DEVO_COMPLETE=zsh_source devo)"
```

Then reload:

```bash
source ~/.zshrc
```

### Bash

Add to `~/.bashrc`:

```bash
eval "$(_DEVO_COMPLETE=bash_source devo)"
```

Then reload:

```bash
source ~/.bashrc
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

## Verification

Test completion works:

```bash
# Type and press TAB
devo <TAB>

# Should show:
# code-reviewer  codeartifact-login  commit  config  upgrade

# Try with options
devo commit --<TAB>

# Should show:
# --add  --all  --help  --profile  --pull-request  --push
```

## Usage Examples

### Command Completion

```bash
devo c<TAB>
# Completes to: devo code-reviewer, commit, config, codeartifact-login

devo co<TAB>
# Shows: code-reviewer  codeartifact-login  commit  config
```

### Option Completion

```bash
devo commit --<TAB>
# Shows all available options:
# --add  --all  --help  --profile  --pull-request  --push

devo config <TAB>
# Shows subcommands:
# edit  export  get  import  path  reset  set  show  validate
```

### Profile Completion

If you have AWS profiles configured:

```bash
devo --profile <TAB>
# Shows available AWS profiles from ~/.aws/config
```

## Advanced Configuration

### Zsh with Oh My Zsh

If using Oh My Zsh, add to `~/.zshrc`:

```bash
# Enable completion
autoload -Uz compinit && compinit

# Add Devo completion
eval "$(_DEVO_COMPLETE=zsh_source devo)"
```

### Bash with Bash Completion

If using bash-completion package:

```bash
# Install bash-completion if needed
# macOS: brew install bash-completion
# Ubuntu: sudo apt install bash-completion

# Add to ~/.bashrc
if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
fi

eval "$(_DEVO_COMPLETE=bash_source devo)"
```

### Fish with Fisher

If using Fisher plugin manager:

```fish
# Add to ~/.config/fish/config.fish
_DEVO_COMPLETE=fish_source devo | source
```

## Troubleshooting

### Completion Not Working

1. **Verify Devo is in PATH**:
   ```bash
   which devo
   devo --version
   ```

2. **Reload shell configuration**:
   ```bash
   # Zsh
   source ~/.zshrc

   # Bash
   source ~/.bashrc

   # Fish
   source ~/.config/fish/config.fish
   ```

3. **Check completion is loaded**:
   ```bash
   # Zsh
   echo $_comps[devo]

   # Bash
   complete -p devo
   ```

### Slow Completion

If completion is slow, you can generate a static completion file:

#### Zsh

```bash
# Generate completion file
_DEVO_COMPLETE=zsh_source devo > ~/.zsh/completions/_devo

# Add to ~/.zshrc
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit && compinit
```

#### Bash

```bash
# Generate completion file
_DEVO_COMPLETE=bash_source devo > ~/.bash_completions/devo

# Add to ~/.bashrc
source ~/.bash_completions/devo
```

### Completion Shows Wrong Commands

Clear completion cache:

```bash
# Zsh
rm ~/.zcompdump*
compinit

# Bash
complete -r devo
source ~/.bashrc
```

### Permission Denied

Ensure completion directory exists and is writable:

```bash
# Zsh
mkdir -p ~/.zsh/completions
chmod 755 ~/.zsh/completions

# Bash
mkdir -p ~/.bash_completions
chmod 755 ~/.bash_completions
```

## Uninstalling Completion

### Zsh

Remove from `~/.zshrc`:

```bash
# Remove this line:
eval "$(_DEVO_COMPLETE=zsh_source devo)"
```

Then reload:

```bash
source ~/.zshrc
```

### Bash

Remove from `~/.bashrc`:

```bash
# Remove this line:
eval "$(_DEVO_COMPLETE=bash_source devo)"
```

Then reload:

```bash
source ~/.bashrc
```

### Fish

Remove from `~/.config/fish/config.fish`:

```fish
# Remove this line:
_DEVO_COMPLETE=fish_source devo | source
```

Then reload:

```fish
source ~/.config/fish/config.fish
```

## Completion Features

### Command Completion

- Main commands: `commit`, `code-reviewer`, `config`, etc.
- Subcommands: `config show`, `config set`, etc.

### Option Completion

- Short options: `-a`, `-p`, `-pr`
- Long options: `--add`, `--push`, `--pull-request`
- Global options: `--profile`, `--help`, `--version`

### Argument Completion

- AWS profiles (from `~/.aws/config`)
- Configuration keys (for `config get/set`)
- File paths (where applicable)

## Tips

1. **Double TAB**: Press TAB twice to see all options
2. **Partial Match**: Type partial command and TAB to complete
3. **Help Text**: Use `--help` to see all options
4. **Explore**: Use TAB to discover available commands

## See Also

- [Installation Guide](../getting-started/installation.md)
- [Commands Reference](../commands/index.md)
- [Configuration](../getting-started/configuration.md)
