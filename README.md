# Devo CLI Tool 🚀

A command-line interface tool for developers with AI-powered features.

## Features

- 🔄 Project scaffolding and code generation
- 📝 AI-powered commit message generation
- 🤖 AI code review with AWS Bedrock
- 🔄 Self-updating capability
- 📦 Multi-platform binary distribution

## Prerequisites

- AWS CLI configured with appropriate permissions
- Git for version control

**Note:** Python is NOT required for end users (binaries are standalone). Developers need Python 3.12+.

## Installation

### Quick Install (Recommended)

Install with a single command:

**Linux/macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
```

This will:

- ✅ Detect your platform and architecture
- ✅ Download the latest binary
- ✅ Verify the download
- ✅ Install to the appropriate location
- ✅ Update PATH automatically
- ✅ Guide you through setup if needed

**Install specific version:**

Linux/macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash -s v1.1.0
```

Windows:
```powershell
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex -Version v1.1.0
```

### Manual Installation

Download the pre-built binary for your platform from [GitHub Releases](https://github.com/edu526/devo-cli/releases):

**Linux:**

```bash
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-linux-amd64 -o devo
chmod +x devo
sudo mv devo /usr/local/bin/
```

**macOS Intel:**

```bash
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-darwin-amd64 -o devo
chmod +x devo
sudo mv devo /usr/local/bin/
```

**macOS Apple Silicon:**

```bash
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-darwin-arm64 -o devo
chmod +x devo
sudo mv devo /usr/local/bin/
```

**Windows (PowerShell):**

```powershell
# Download the installer script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1" -OutFile "install-devo.ps1"

# Run the installer
.\install-devo.ps1

# Or download binary directly
Invoke-WebRequest -Uri "https://github.com/edu526/devo-cli/releases/latest/download/devo-windows-amd64.exe" -OutFile "devo.exe"
```

**Benefits:**

- ✅ No Python installation required
- ✅ Single executable file
- ✅ Works immediately
- ✅ ~70-80 MB download

**Requirements:**

- AWS credentials configured (`aws configure`)

## Usage

```bash
# Show available commands
devo --help

# Show CLI version
devo --version

# Use specific AWS profile
devo --profile my-profile <command>
```

**Note:** The CLI automatically checks for updates once per day and shows a notification if a new version is available. You can disable this by setting `DEVO_SKIP_VERSION_CHECK=1`.

### Configuration

Manage CLI configuration stored in `~/.devo/config.json`:

```bash
# Show current configuration
devo config show

# Set a configuration value
devo config set aws.region us-west-2
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Get a configuration value
devo config get aws.region

# Edit configuration in your editor
devo config edit

# Manage CodeArtifact registries
devo config registry list
devo config registry add --domain my-domain --repository my-repo --namespace @myorg
devo config registry remove 2

# Export/Import configuration
devo config export my-config.json
devo config import my-config.json
devo config import backup-config.json --merge

# Reset to defaults
devo config reset
```

See [Configuration Guide](./docs/configuration.md) for detailed information.

### Commands

```bash
devo commit
# Options for `devo commit`:
#   --add, -a            Add all changes to the staging area before committing
#   --push, -p           Push to the current branch
#   --pull-request, -pr  Open the browser to create a Pull Request in GitHub
#   --all, -A            Execute add, commit, push, and pull-request in sequence
#   --profile TEXT       AWS profile to use

# Update CLI to latest version
devo upgrade

# AI-powered code review
devo code-reviewer --base-branch main

# Login to CodeArtifact for npm
devo codeartifact-login
```

## Shell Autocompletion

Enable tab completion for commands and options:

```bash
# Show instructions for your shell
devo completion

# For Zsh (add to ~/.zshrc)
eval "$(_DEVO_COMPLETE=zsh_source devo)"

# For Bash (add to ~/.bashrc)
eval "$(_DEVO_COMPLETE=bash_source devo)"

# For Fish (add to ~/.config/fish/config.fish)
_DEVO_COMPLETE=fish_source devo | source
```

After setup, restart your terminal or run:

```bash
source ~/.zshrc   # or ~/.bashrc
```

## Development

### Quick Start for Developers

```bash
# Clone the repository
git clone https://github.com/edu526/devo-cli.git
cd devo-cli

# Run the setup script (does everything automatically)
chmod +x setup-dev.sh
./setup-dev.sh

# You're ready! Try it:
devo --help
```

That's it! The setup script will:

- ✅ Create and activate virtual environment
- ✅ Install the CLI in development mode
- ✅ Install all dependencies
- ✅ Setup shell autocompletion
- ✅ Refresh shell cache

### Manual Development Setup

```bash
# Create virtual environment
make venv
source venv/bin/activate

# Install in editable mode
make install-dev

# Setup shell autocompletion
make completion

# Refresh shell cache
make refresh
```

See [Development Guide](./docs/development.md) for detailed instructions.

### Building Binaries

For developers who want to build standalone binaries:

```bash
# Build binary for current platform
make build-binary

# Build with platform-specific naming
make build-all

# Test the binary
./dist/devo --version
```

See [Binary Distribution Guide](./docs/binary-distribution.md) for detailed instructions.

### Release Process

This project uses **Semantic Release** for automated versioning and releases.

#### Using Conventional Commits

```bash
# Feature (minor bump: 1.0.0 → 1.1.0)
git commit -m "feat: add new command"

# Bug fix (patch bump: 1.0.0 → 1.0.1)
git commit -m "fix: resolve parsing error"

# Breaking change (major bump: 1.0.0 → 2.0.0)
git commit -m "feat!: redesign CLI interface

BREAKING CHANGE: Command structure changed"

# Push to main
git push origin main
```

GitHub Actions will automatically:

- Analyze commits using Semantic Release
- Determine the next version
- Update CHANGELOG.md
- Create and push a git tag
- Build binaries for all platforms (Linux, macOS, Windows)
- Create GitHub Release with all artifacts

Download binaries from: [GitHub Releases](https://github.com/edu526/devo-cli/releases)

See [Semantic Release Guide](./docs/semantic-release.md) for detailed information.

### Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** feat, fix, docs, style, refactor, perf, test, build, ci, chore

## Documentation

- [Configuration Guide](./docs/configuration.md) - Environment variables and settings
- [Development Guide](./docs/development.md) - Setup and development workflow
- [CI/CD Pipeline](./docs/cicd.md) - GitHub Actions workflows and pipeline
- [Semantic Release](./docs/semantic-release.md) - Automated versioning
- [Binary Distribution](./docs/binary-distribution.md) - Building and distributing binaries
- [Contributing Guidelines](./docs/contributing.md) - How to contribute
- [Versioning](./docs/versioning.md) - Version management

## Project Structure

```text
devo-cli/
├── cli_tool/              # Main package
├── scripts/               # Build and installation scripts
├── tests/                 # Test suite
├── docs/                  # Documentation
├── .github/workflows/     # GitHub Actions workflows
├── pyproject.toml         # Project configuration
└── README.md             # This file
```

## Contributing

We welcome contributions! Please see [Contributing Guidelines](./docs/contributing.md) for details.

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:

- Check the [documentation](./docs/)
- Open an issue on GitHub
- Contact the development team
