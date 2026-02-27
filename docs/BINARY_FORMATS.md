# Binary Distribution Formats

This document explains the different binary formats used for each platform and why.

## Overview

Devo CLI uses PyInstaller to create standalone binaries. Different platforms use different packaging modes optimized for their use case.

## Platform-Specific Formats

### Linux: Single Binary (onefile)

**Format:** Single executable file  
**File:** `devo-linux-amd64`  
**Size:** ~50-80 MB

**Why onefile?**
- Easy distribution (single file to download)
- Simple installation (just copy to PATH)
- Acceptable startup time on Linux systems
- Standard for Linux CLI tools

**Startup time:** ~0.5-1s (extraction overhead acceptable)

### macOS: Directory Bundle (onedir)

**Format:** Directory with executable and dependencies  
**Distribution:** `.tar.gz` archive  
**File:** `devo-darwin-arm64.tar.gz` or `devo-darwin-amd64.tar.gz`  
**Extracted size:** ~60-90 MB

**Why onedir?**
- **Fast startup:** ~0.1-0.3s (no extraction needed)
- Avoids 2-5s startup delay from onefile mode
- Better user experience for frequent CLI usage
- Standard for macOS applications

**Startup time:** ~0.1-0.3s (instant, no extraction)

### Windows: Directory Bundle (onedir)

**Format:** Directory with executable and dependencies  
**Distribution:** `.zip` archive  
**File:** `devo-windows-amd64.zip`  
**Extracted size:** ~60-90 MB

**Why onedir?**
- **Fast startup:** ~0.1-0.3s (no extraction needed)
- Avoids extraction overhead
- Better antivirus compatibility
- Standard for Windows applications

**Startup time:** ~0.1-0.3s (instant, no extraction)

## Performance Comparison

| Platform | Mode | Startup Time | Distribution | Size |
|----------|------|--------------|--------------|------|
| Linux | onefile | ~0.5-1s | Single file | ~50-80 MB |
| macOS | onedir | ~0.1-0.3s | .tar.gz | ~60-90 MB |
| Windows | onedir | ~0.1-0.3s | .zip | ~60-90 MB |

## Why Different Modes?

### onefile Mode (Linux)
- Extracts to temporary directory on each run
- Adds 2-5s startup overhead on macOS/Windows
- Acceptable on Linux due to faster I/O
- Simpler distribution (single file)

### onedir Mode (macOS/Windows)
- No extraction needed (files already on disk)
- Near-instant startup
- Better for frequent CLI usage
- Requires directory structure

## Installation

### Linux
```bash
# Download single binary
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-linux-amd64 -o devo
chmod +x devo
sudo mv devo /usr/local/bin/
```

### macOS
```bash
# Download and extract tarball
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-darwin-arm64.tar.gz -o devo.tar.gz
tar -xzf devo.tar.gz
sudo mv devo-darwin-arm64 /usr/local/bin/devo-app
sudo ln -s /usr/local/bin/devo-app/devo /usr/local/bin/devo
```

### Windows
```powershell
# Download and extract zip
Invoke-WebRequest -Uri "https://github.com/edu526/devo-cli/releases/latest/download/devo-windows-amd64.zip" -OutFile "devo.zip"
Expand-Archive devo.zip -DestinationPath "C:\Program Files\devo"
# Add to PATH
```

## Upgrade Behavior

The `devo upgrade` command handles each format automatically:

- **Linux:** Downloads single binary, replaces in place
- **macOS:** Downloads tarball, extracts, replaces directory
- **Windows:** Downloads zip, extracts, uses PowerShell script for replacement

## Building

### Build for Current Platform
```bash
./scripts/build.sh
```

Output:
- Linux: `dist/devo` (single file)
- macOS: `dist/devo/` (directory)
- Windows: `dist/devo/` (directory)

### Build Release
```bash
./scripts/build.sh --release
```

Output:
- Linux: `release/vX.Y.Z/devo-linux-amd64`
- macOS: `release/vX.Y.Z/devo-darwin-arm64.tar.gz`
- Windows: `release/vX.Y.Z/devo-windows-amd64.zip`

## Technical Details

### PyInstaller Configuration

See `devo.spec` for the full configuration:

```python
if sys.platform == 'linux':
    # onefile mode
    exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, ...)
else:
    # onedir mode (macOS/Windows)
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, ...)
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, ...)
```

### Why Not onefile Everywhere?

We tested onefile mode on all platforms and found:

- **Linux:** 0.5-1s startup (acceptable)
- **macOS:** 2-5s startup (too slow for CLI tool)
- **Windows:** 2-5s startup (too slow for CLI tool)

The onedir mode eliminates this overhead on macOS/Windows while keeping Linux simple with a single file.

## See Also

- [Building Guide](development/building.md) - How to build binaries
- [Installation Guide](getting-started/installation.md) - How to install
- [Upgrade Command](commands/upgrade.md) - How upgrade works
