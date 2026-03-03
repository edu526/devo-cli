# devo upgrade

Upgrade the CLI tool to the latest version from GitHub Releases.

## Synopsis

```bash
devo upgrade [OPTIONS]
```

## Description

Automatically downloads and installs the latest version of Devo CLI from GitHub Releases. Supports binary upgrades for Linux, macOS, and Windows.

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Force upgrade without confirmation |
| `--check` | `-c` | Check for updates without upgrading |
| `--help` | | Show help message and exit |

## Usage

### Check for Updates

```bash
# Check if new version is available
devo upgrade --check
```

**Output:**

```text
Current version: 1.2.0
Latest version: 1.3.0
New version available!
```

or

```
Current version: 1.3.0
Latest version: 1.3.0
You are already on the latest version.
```

### Upgrade

```bash
# Upgrade with confirmation
devo upgrade

# Upgrade without confirmation
devo upgrade --force
```

**Interactive flow:**

```text
Current version: 1.2.0
Latest version: 1.3.0

New version available!

Changelog:
- feat: Add new SSM database commands
- fix: Improve error handling in commit command
- docs: Update documentation

Upgrade to version 1.3.0? [Y/n]: y

Downloading devo-linux-amd64...
✓ Download complete
✓ Verifying binary...
✓ Installing...
✓ Upgrade successful!

Devo CLI upgraded to version 1.3.0
```

## How It Works

1. **Version Check**: Compares current version with latest GitHub release
2. **Download**: Downloads platform-specific binary from GitHub Releases
3. **Verification**: Verifies binary integrity
4. **Backup**: Creates backup of current binary
5. **Installation**: Replaces current binary with new version
6. **Cleanup**: Removes temporary files

## Platform Support

| Platform | Binary Format | Notes |
|----------|---------------|-------|
| Linux | Single file | Direct replacement |
| macOS | Tarball (.tar.gz) | Extracts to directory |
| Windows | ZIP (.zip) | Extracts to directory |

## Installation Locations

The upgrade command detects your installation location:

- `/usr/local/bin/devo` - System-wide installation
- `~/.local/bin/devo` - User installation
- Custom locations - Detected from current binary path

## Examples

### Basic Upgrade

```bash
# Check for updates
devo upgrade --check

# Upgrade if available
devo upgrade
```

### Force Upgrade

```bash
# Upgrade without confirmation
devo upgrade --force
```

### Automated Upgrade (CI/CD)

```bash
# Non-interactive upgrade
devo upgrade --force

# Check exit code
if [ $? -eq 0 ]; then
  echo "Upgrade successful"
else
  echo "Upgrade failed"
fi
```

## Automatic Version Checks

Devo CLI automatically checks for new versions periodically (configurable):

```bash
# Disable automatic version checks
devo config set version_check.enabled false

# Enable automatic version checks
devo config set version_check.enabled true
```

When a new version is available, you'll see a notification:

```
A new version of Devo CLI is available: 1.3.0 (current: 1.2.0)
Run 'devo upgrade' to update.
```

## Rollback

If the upgrade fails or you want to rollback:

```bash
# The old binary is backed up as devo.backup
# Restore it manually:

# Linux/macOS
sudo mv /usr/local/bin/devo.backup /usr/local/bin/devo

# Or for user installation
mv ~/.local/bin/devo.backup ~/.local/bin/devo
```

## Troubleshooting

### Permission denied

```
Error: Permission denied
```

**Solution:** Run with sudo for system-wide installation:

```bash
sudo devo upgrade
```

Or upgrade to user directory:

```bash
# Install to ~/.local/bin instead
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash
```

### Download failed

```
Error: Failed to download binary
```

**Possible causes:**

- No internet connection
- GitHub is down
- Firewall blocking access

**Solution:**

```bash
# Check internet connection
curl -I https://github.com

# Try again
devo upgrade --force
```

### Binary verification failed

```
Error: Binary verification failed
```

**Solution:**

```bash
# Download manually from GitHub Releases
# https://github.com/edu526/devo-cli/releases/latest
```

### Already on latest version

```bash
# Force reinstall current version
# Download from GitHub Releases and install manually
```

## Security

- Binaries are downloaded from official GitHub Releases
- SHA256 checksums are verified (when available)
- HTTPS is used for all downloads
- Old binary is backed up before replacement

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success (upgraded or already on latest) |
| 1 | Error (download failed, permission denied, etc.) |

## See Also

- [Installation Guide](../getting-started/installation.md) - Initial installation
- [GitHub Releases](https://github.com/edu526/devo-cli/releases) - View all releases
- [Changelog](https://github.com/edu526/devo-cli/blob/main/CHANGELOG.md) - Version history

## Notes

- Requires internet connection
- May require sudo for system-wide installations
- Automatic version checks can be disabled in config
- Old binary is backed up as `devo.backup`
- Works with binary installations only (not pip installations)
