# Devo CLI 🚀

[![Documentation](https://github.com/edu526/devo-cli/actions/workflows/docs.yml/badge.svg)](https://edu526.github.io/devo-cli) [![Release](https://github.com/edu526/devo-cli/actions/workflows/release.yml/badge.svg)](https://github.com/edu526/devo-cli/releases) [![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![GitHub release](https://img.shields.io/github/v/release/edu526/devo-cli)](https://github.com/edu526/devo-cli/releases/latest) [![GitHub issues](https://img.shields.io/github/issues/edu526/devo-cli)](https://github.com/edu526/devo-cli/issues)

AI-powered command-line tool for developers with AWS Bedrock integration.

## Features

- 📝 AI-powered commit message generation
- 🤖 AI code review with security analysis
- 🔄 Self-updating capability
- 📦 Standalone binaries (no Python required)

## Quick Install

**Linux/macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
```

**Requirements:** AWS credentials configured (`aws configure`)

## Usage

```bash
# AI commit message generation
devo commit

# AI code review
devo code-reviewer --base-branch main

# Update to latest version
devo upgrade

# CodeArtifact login
devo codeartifact-login

# Configuration management
devo config show
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Use specific AWS profile
devo --profile my-profile commit
```

### Commit Command Options

```bash
devo commit [OPTIONS]

Options:
  -a, --add            Add all changes before committing
  -p, --push           Push to current branch
  -pr, --pull-request  Open browser to create GitHub PR
  -A, --all            Execute add, commit, push, and PR in sequence
  --profile TEXT       AWS profile to use
```

## Configuration

Configuration stored in `~/.devo/config.json`:

```bash
devo config show                    # View current config
devo config set aws.region us-west-2
devo config get bedrock.model_id
devo config edit                    # Open in editor
devo config export backup.json      # Export config
devo config import backup.json      # Import config
devo config reset                   # Reset to defaults
```

See [Configuration Guide](./docs/configuration.md) for details.

## Shell Autocompletion

```bash
# Zsh (add to ~/.zshrc)
eval "$(_DEVO_COMPLETE=zsh_source devo)"

# Bash (add to ~/.bashrc)
eval "$(_DEVO_COMPLETE=bash_source devo)"

# Fish (add to ~/.config/fish/config.fish)
_DEVO_COMPLETE=fish_source devo | source
```

## Development

### Quick Start

```bash
git clone https://github.com/edu526/devo-cli.git
cd devo-cli
./setup-dev.sh
```

### Manual Setup

```bash
make venv
source venv/bin/activate
make install-dev
make completion
```

### Building Binaries

```bash
make build-binary    # Build for current platform
make build-all       # Build with platform naming
```

### Release Process

Uses Semantic Release with Conventional Commits:

```bash
# Feature (1.0.0 → 1.1.0)
git commit -m "feat: add new command"

# Bug fix (1.0.0 → 1.0.1)
git commit -m "fix: resolve parsing error"

# Breaking change (1.0.0 → 2.0.0)
git commit -m "feat!: redesign CLI

BREAKING CHANGE: Command structure changed"
```

Push to main triggers automated release with binaries for all platforms.

## Documentation

📚 **[Full Documentation](https://edu526.github.io/devo-cli)**

Quick links:
- [Configuration Guide](./docs/configuration.md)
- [Development Guide](./docs/development.md)
- [CI/CD Pipeline](./docs/cicd.md)
- [Semantic Release](./docs/semantic-release.md)
- [Binary Distribution](./docs/binary-distribution.md)
- [Contributing Guidelines](./docs/contributing.md)

## Troubleshooting

**Windows:**
- Execution policy error: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- Access denied: Choose user-only installation option

**Linux/macOS:**
- Command not found: Restart terminal or add to PATH manually

**Runtime:**
- No AWS credentials: Run `aws configure`
- Disable version check: Set `DEVO_SKIP_VERSION_CHECK=1`

## License

MIT License - See LICENSE file for details
