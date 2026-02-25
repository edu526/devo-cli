# Installation

Devo CLI can be installed as a standalone binary (recommended) or from source for development.

## Binary Installation (Recommended)

No Python installation required. Download and run the installer:

### Linux/macOS

```bash
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash
```

The installer will:
1. Detect your platform (Linux/macOS, architecture)
2. Download the latest binary
3. Install to `/usr/local/bin` (system-wide) or `~/.local/bin` (user-only)
4. Verify installation

### Windows

Open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
```

The installer will:
1. Download the latest Windows binary
2. Install to `C:\Program Files\devo` or user directory
3. Add to PATH automatically
4. Verify installation

**Note:** If you get an execution policy error, run:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Manual Binary Installation

Download the binary for your platform from [GitHub Releases](https://github.com/edu526/devo-cli/releases):

### Linux

```bash
# Download
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-linux-amd64 -o devo

# Make executable
chmod +x devo

# Move to PATH
sudo mv devo /usr/local/bin/
# or for user-only:
mkdir -p ~/.local/bin && mv devo ~/.local/bin/
```

### macOS

```bash
# Download (Intel)
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-darwin-amd64 -o devo

# Download (Apple Silicon)
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-darwin-arm64 -o devo

# Make executable
chmod +x devo

# Move to PATH
sudo mv devo /usr/local/bin/
```

### Windows

1. Download `devo-windows-amd64.exe` from [releases](https://github.com/edu526/devo-cli/releases/latest)
2. Rename to `devo.exe`
3. Move to a directory in your PATH (e.g., `C:\Program Files\devo\`)
4. Add directory to PATH if needed

## Python Package Installation (Development)

For development or if you prefer pip:

```bash
# Clone repository
git clone https://github.com/edu526/devo-cli.git
cd devo-cli

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .
```

## Verify Installation

```bash
# Check version
devo --version

# Show help
devo --help

# Test a command
devo config show
```

## AWS Configuration

Devo CLI requires AWS credentials to use AI features:

```bash
# Configure AWS CLI
aws configure

# Or use AWS SSO
aws sso login --profile my-profile
```

See [AWS Setup Guide](../guides/aws-setup.md) for detailed instructions.

## Shell Completion

Enable tab completion for your shell:

```bash
# Zsh (add to ~/.zshrc)
eval "$(_DEVO_COMPLETE=zsh_source devo)"

# Bash (add to ~/.bashrc)
eval "$(_DEVO_COMPLETE=bash_source devo)"

# Fish (add to ~/.config/fish/config.fish)
_DEVO_COMPLETE=fish_source devo | source
```

See [Shell Completion Guide](../guides/shell-completion.md) for more details.

## Updating

Update to the latest version:

```bash
devo upgrade
```

## Uninstallation

### Binary Installation

```bash
# Linux/macOS
sudo rm /usr/local/bin/devo
# or
rm ~/.local/bin/devo

# Windows
# Remove from C:\Program Files\devo or user directory
# Remove from PATH
```

### Python Installation

```bash
pip uninstall devo-cli
```

## Troubleshooting

See [Troubleshooting Guide](../reference/troubleshooting.md) for common issues.

### Command Not Found

After installation, restart your terminal or run:

```bash
# Linux/macOS
source ~/.bashrc  # or ~/.zshrc

# Windows
# Restart PowerShell
```

### Permission Denied

```bash
# Linux/macOS - make executable
chmod +x /path/to/devo

# Windows - run as administrator
```

### AWS Credentials

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Configure if needed
aws configure
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started in 5 minutes
- [Configuration](configuration.md) - Configure AWS and Bedrock settings
- [Commands](../commands/index.md) - Learn available commands
