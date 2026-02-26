# devo upgrade

Self-update the Devo CLI to the latest version.

## Synopsis

```bash
devo upgrade [OPTIONS]
```

## Description

Automatically downloads and installs the latest version of Devo CLI from the configured release repository. Checks for updates, downloads the appropriate binary for your platform, verifies integrity, and replaces the current installation.

## Usage

::: mkdocs-click
    :module: cli_tool.commands.upgrade
    :command: upgrade
    :prog_name: devo
    :depth: 1

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

## Supported Platforms

| Platform | Architecture | Binary Name |
|----------|-------------|-------------|
| Linux | amd64 | `devo-linux-amd64` |
| macOS | amd64 | `devo-darwin-amd64` |
| macOS | arm64 | `devo-darwin-arm64` |
| Windows | amd64 | `devo-windows-amd64.exe` |

## Upgrade Process

1. Fetches latest release information from GitHub
2. Compares current version with latest version
3. Downloads appropriate binary for platform
4. Verifies download integrity (SHA256)
5. Replaces current binary
6. Confirms successful upgrade

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEVO_SKIP_VERSION_CHECK` | Skip version check on startup | `false` |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success (upgraded or already latest) |
| 1 | Error (download failed, permission denied, etc.) |

## Examples

```bash
# Check and install latest version
devo upgrade

# Output example:
# Current version: 1.1.0
# Latest version: 1.2.0
# Downloading...
# ✓ Successfully upgraded to v1.2.0
```

## Version Check

Check current version:

```bash
devo --version
```

## See Also

- [Installation Guide](../getting-started/installation.md) - Initial installation
- [Configuration Guide](../getting-started/configuration.md) - Configure settings
