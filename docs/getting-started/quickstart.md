# Quick Start Guide

Get up and running with Devo CLI in 5 minutes.

## Installation

### Linux/macOS

```bash
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
```

## Configure AWS Credentials

Devo CLI requires AWS credentials to use AI features:

```bash
# Configure AWS CLI
aws configure
```

Enter your:

- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Default output format (e.g., `json`)

## Verify Installation

```bash
# Check version
devo --version

# Show help
devo --help
```

## First Commands

### Generate a Commit Message

```bash
# Stage your changes
git add .

# Generate AI-powered commit message
devo commit
```

### Review Your Code

```bash
# Review staged changes
devo code-reviewer
```

### Check Configuration

```bash
# View current configuration
devo config show
```

## Enable Shell Completion (Optional)

Add to your shell configuration file:

**Zsh (~/.zshrc):**
```bash
eval "$(_DEVO_COMPLETE=zsh_source devo)"
```

**Bash (~/.bashrc):**
```bash
eval "$(_DEVO_COMPLETE=bash_source devo)"
```

**Fish (~/.config/fish/config.fish):**
```bash
_DEVO_COMPLETE=fish_source devo | source
```

Then restart your terminal or run `source ~/.zshrc` (or equivalent).

## Common Workflows

### Daily Development

```bash
# 1. Make changes to your code
# ... edit files ...

# 2. Stage changes
git add .

# 3. Generate commit message
devo commit

# 4. Review code (optional)
devo code-reviewer

# 5. Push changes
git push
```

### Working with AWS Profiles

```bash
# Use specific AWS profile
devo --profile production commit

# Or set default profile
export AWS_PROFILE=production
devo commit
```

### Update Devo CLI

```bash
# Update to latest version
devo upgrade
```

## Next Steps

- [Installation Guide](installation.md) - Detailed installation options
- [Configuration](configuration.md) - Configure CLI settings (Bedrock, GitHub, CodeArtifact, version check)
- [Commands Reference](../commands/index.md) - Learn all available commands
- [AWS Setup](../guides/aws-setup.md) - Detailed AWS configuration

## Troubleshooting

### Command Not Found

Restart your terminal or add to PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### AWS Credentials Error

Configure AWS credentials:

```bash
aws configure
```

### Need Help?

```bash
# Get help for any command
devo --help
devo commit --help
devo config --help
```

See [Troubleshooting Guide](../reference/troubleshooting.md) for more help.
