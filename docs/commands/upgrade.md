# devo upgrade

Self-update the Devo CLI to the latest version.

## Overview

The `upgrade` command automatically downloads and installs the latest version of Devo CLI from the configured release repository.

## Usage

::: mkdocs-click
    :module: cli_tool.commands.upgrade
    :command: upgrade
    :prog_name: devo
    :depth: 1

## How It Works

1. Checks for the latest version available
2. Downloads the appropriate binary for your platform
3. Verifies the download integrity
4. Replaces the current installation
5. Confirms successful upgrade

## Supported Platforms

- Linux (amd64)
- macOS (amd64, arm64)
- Windows (amd64)

## Examples

```bash
# Check and install latest version
devo upgrade

# The command will show current and new version
Current version: 1.1.0
Latest version: 1.2.0
Downloading...
✓ Successfully upgraded to v1.2.0
```

## Version Information

Check your current version:

```bash
devo --version
```

## Troubleshooting

If upgrade fails:

1. Check your internet connection
2. Verify you have write permissions to the installation directory
3. Try manual installation from the release page
4. Check GitHub releases for platform-specific binaries

## Manual Installation

If automatic upgrade doesn't work, download manually:

```bash
# Linux/macOS
curl -L https://github.com/your-org/devo-cli/releases/latest/download/devo-linux-amd64 -o devo
chmod +x devo
sudo mv devo /usr/local/bin/

# Windows
# Download from releases page and add to PATH
```
