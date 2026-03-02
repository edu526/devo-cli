# Devo CLI 🚀

[![Documentation](https://github.com/edu526/devo-cli/actions/workflows/docs.yml/badge.svg)](https://edu526.github.io/devo-cli) [![Release](https://github.com/edu526/devo-cli/actions/workflows/release.yml/badge.svg)](https://github.com/edu526/devo-cli/releases) [![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![GitHub release](https://img.shields.io/github/v/release/edu526/devo-cli)](https://github.com/edu526/devo-cli/releases/latest) [![GitHub issues](https://img.shields.io/github/issues/edu526/devo-cli)](https://github.com/edu526/devo-cli/issues)

AI-powered command-line tool for developers with AWS Bedrock integration.

## Features

- 📝 AI-powered commit message generation
- 🤖 AI code review with security analysis
- 🔐 AWS SSO authentication and credential management
- 🗄️ DynamoDB table management and export utilities
- 📡 EventBridge rule management
- 🖥️ AWS Systems Manager Session Manager integration
- 📦 CodeArtifact authentication
- ⚙️ Configuration management system
- 🔄 Self-updating capability
- 📦 Standalone binaries (no Python required)
- ⚡ Fast startup on macOS/Windows (optimized onedir builds)
- 🐚 Shell autocompletion support

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

### AI-Powered Features

```bash
# AI commit message generation
devo commit

# AI code review
devo code-reviewer --base-branch main
```

### AWS Integration

```bash
# AWS SSO login
devo aws-login
devo aws-login list
devo aws-login refresh

# CodeArtifact authentication
devo codeartifact-login
```

### AWS Services

```bash
# DynamoDB operations
devo dynamodb list
devo dynamodb export my-table --filter "userId = user123"

# EventBridge rules
devo eventbridge list
devo eventbridge enable my-rule

# SSM Session Manager
devo ssm database connect my-db
devo ssm instance shell i-1234567890abcdef0
devo ssm forward my-service 8080
```

### Configuration & Tools

```bash
# Configuration management
devo config show
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Shell autocompletion
devo autocomplete --install

# Update to latest version
devo upgrade

# Use specific AWS profile
devo --profile my-profile dynamodb list
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

## Available Commands

### AI-Powered Features

- `commit` - Generate conventional commit messages from staged changes
- `code-reviewer` - AI-powered code review with security analysis

### AWS Authentication

- `aws-login` - AWS SSO authentication and credential management
  - `list` - List all profiles with status
  - `login [PROFILE]` - Login to specific profile
  - `refresh` - Refresh expired credentials
  - `set-default [PROFILE]` - Set default profile
  - `configure [PROFILE]` - Configure new SSO profile

- `codeartifact-login` - Authenticate with AWS CodeArtifact

### AWS Services

- `dynamodb` - DynamoDB table management
  - `list` - List all tables
  - `describe TABLE` - Describe table structure
  - `export TABLE` - Export table data (CSV, JSON, JSONL, TSV)
  - `list-templates` - List saved export templates

- `eventbridge` - EventBridge rule management
  - `list` - List all rules
  - `enable RULE` - Enable a rule
  - `disable RULE` - Disable a rule
  - `describe RULE` - Describe rule details

- `ssm` - AWS Systems Manager Session Manager
  - `database connect NAME` - Connect to RDS database via SSM
  - `instance shell INSTANCE_ID` - Start shell session
  - `forward SERVICE PORT` - Port forwarding
  - `hosts setup` - Setup /etc/hosts entries

### Configuration & Tools

- `config` - Configuration management
  - `show` - View current configuration
  - `set KEY VALUE` - Set configuration value
  - `get KEY` - Get configuration value
  - `edit` - Open config in editor
  - `export FILE` - Export configuration
  - `import FILE` - Import configuration
  - `reset` - Reset to defaults

- `autocomplete` - Shell autocompletion setup
  - `--install` - Automatically install completion

- `upgrade` - Update to latest version

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

### Git Hooks

The project uses pre-commit hooks for code quality:

```bash
# Install hooks (run once after cloning)
pre-commit install              # Install pre-commit hooks
pre-commit install --hook-type pre-push  # Install pre-push hooks
```

**Pre-commit hooks** (run on every commit):
- Code formatting (black, isort)
- Linting (flake8)
- File checks (large files, merge conflicts, etc.)
- Commit message validation (conventional commits)

**Pre-push hooks** (run before pushing):
- Unit tests (`pytest -m unit`)

To skip hooks temporarily (not recommended):
```bash
git commit --no-verify    # Skip pre-commit hooks
git push --no-verify      # Skip pre-push hooks
```

To run hooks manually:
```bash
pre-commit run --all-files              # Run all pre-commit hooks
pre-commit run --hook-stage push --all-files  # Run pre-push hooks
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

### User Guides
- [Configuration Guide](./docs/configuration.md)
- [AWS Login Guide](./cli_tool/commands/aws_login/README.md)
- [DynamoDB Guide](./cli_tool/commands/dynamodb/README.md)
- [SSM Session Manager Guide](./cli_tool/commands/ssm/README.md)
- [EventBridge Guide](./cli_tool/commands/eventbridge/README.md)

### Command References
- [commit](./cli_tool/commands/commit/README.md) - AI commit message generation
- [code-reviewer](./cli_tool/commands/code_reviewer/README.md) - AI code review
- [aws-login](./cli_tool/commands/aws_login/README.md) - AWS SSO authentication
- [codeartifact-login](./cli_tool/commands/codeartifact/README.md) - CodeArtifact auth
- [config](./cli_tool/commands/config_cmd/README.md) - Configuration management
- [autocomplete](./cli_tool/commands/autocomplete/README.md) - Shell completion
- [upgrade](./cli_tool/commands/upgrade/README.md) - Self-update system

### Developer Guides
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
