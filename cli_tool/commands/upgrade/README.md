# Self-Update

Automatic update system for Devo CLI binaries.

## Structure

```
cli_tool/commands/upgrade/
├── __init__.py              # Public API exports
├── README.md                # This file
├── commands/                # CLI command definitions
│   ├── __init__.py          # Command registration
│   └── upgrade.py           # Upgrade command
└── core/                    # Business logic
    ├── __init__.py
    └── updater.py           # BinaryUpdater
```

## Usage

```bash
# Check for updates and upgrade
devo upgrade

# Skip version check (force upgrade)
devo upgrade --force
```

## Features

- Automatic version checking against GitHub releases
- Platform-specific binary downloads (Linux, macOS, Windows)
- Safe upgrade with backup and rollback
- Binary verification after upgrade
- Automatic cleanup of old versions

## How It Works

1. Checks current version from `devo --version`
2. Fetches latest release from GitHub API
3. Compares versions (semantic versioning)
4. Downloads platform-specific binary
5. Creates backup of current binary
6. Replaces binary with new version
7. Verifies new binary works
8. Cleans up backup and temporary files

## Platform Support

### Linux
- Downloads: `devo-linux`
- Location: `/usr/local/bin/devo` or `~/.local/bin/devo`
- Format: Single executable file

### macOS
- Downloads: `devo-macos.tar.gz`
- Location: `/usr/local/bin/devo` or `~/.local/bin/devo`
- Format: Tarball with onedir structure

### Windows
- Downloads: `devo-windows.zip`
- Location: `%LOCALAPPDATA%\Programs\devo\devo.exe`
- Format: ZIP with onedir structure
- Special handling for locked executables

## Architecture

### Commands Layer (`commands/`)
- `upgrade.py`: CLI command with Click decorators
- User interaction and progress display
- Error handling and rollback

### Core Layer (`core/`)
- `updater.py`: BinaryUpdater class
- GitHub API integration
- Binary download and verification
- Platform-specific upgrade logic
- No Click dependencies

## Version Checking

Automatic version check runs after each command execution (unless disabled):

```bash
# Disable version check
export DEVO_SKIP_VERSION_CHECK=1
```

Shows notification if newer version available:
```
💡 New version available: 3.1.0 (current: 3.0.0)
   Run 'devo upgrade' to update
```

## Safety Features

- Creates backup before upgrade
- Verifies new binary after installation
- Automatic rollback on failure
- Preserves file permissions
- Handles locked files on Windows

## Troubleshooting

### Permission Denied (Linux/macOS)
```bash
# Install to user directory instead
mkdir -p ~/.local/bin
mv /usr/local/bin/devo ~/.local/bin/
export PATH="$HOME/.local/bin:$PATH"
```

### Binary Not Found After Upgrade
```bash
# Verify PATH includes installation directory
echo $PATH

# Restart terminal or reload shell config
source ~/.bashrc  # or ~/.zshrc
```

### Windows: Access Denied
- Close all terminal windows running devo
- Run upgrade from fresh terminal
- If still fails, manually download from GitHub releases

## Manual Installation

If automatic upgrade fails, download manually:

1. Visit: https://github.com/edu526/devo-cli/releases/latest
2. Download platform-specific binary
3. Replace existing binary
4. Verify: `devo --version`
