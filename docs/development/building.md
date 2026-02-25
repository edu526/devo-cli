# Building Binaries

Guide for building standalone binaries of Devo CLI using PyInstaller.

## Overview

Devo CLI can be distributed as standalone binaries that don't require Python installation. This is done using PyInstaller to bundle Python, dependencies, and the CLI into a single executable.

## Prerequisites

- Python 3.12+
- Virtual environment activated
- Development dependencies installed

```bash
# Setup development environment
./setup-dev.sh

# Or manually
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Quick Build

### Build for Current Platform

```bash
make build-binary
```

This creates a binary in `dist/` directory:
- Linux: `dist/devo`
- macOS: `dist/devo`
- Windows: `dist/devo.exe`

### Build with Platform-Specific Naming

```bash
make build-all
```

Creates binaries with platform identifiers:
- Linux AMD64: `dist/devo-linux-amd64`
- macOS Intel: `dist/devo-darwin-amd64`
- macOS Apple Silicon: `dist/devo-darwin-arm64`
- Windows: `dist/devo-windows-amd64.exe`

## Manual Build

### Using PyInstaller Directly

```bash
# Activate virtual environment
source venv/bin/activate

# Build binary
pyinstaller --onefile \
  --name devo \
  --add-data "cli_tool:cli_tool" \
  cli_tool/cli.py
```

### Custom Build Options

```bash
# With console window (default)
pyinstaller --onefile --name devo cli_tool/cli.py

# Without console window (Windows GUI)
pyinstaller --onefile --noconsole --name devo cli_tool/cli.py

# With icon
pyinstaller --onefile --icon=icon.ico --name devo cli_tool/cli.py

# With additional data files
pyinstaller --onefile \
  --add-data "config:config" \
  --add-data "templates:templates" \
  --name devo cli_tool/cli.py
```

## Platform-Specific Builds

### Linux

```bash
# Build on Linux
make build-binary

# Output
dist/devo-linux-amd64

# Test
./dist/devo-linux-amd64 --version
```

### macOS

```bash
# Build on macOS
make build-binary

# Output (depends on architecture)
dist/devo-darwin-amd64  # Intel
dist/devo-darwin-arm64  # Apple Silicon

# Test
./dist/devo-darwin-amd64 --version
```

### Windows

```bash
# Build on Windows
make build-binary

# Output
dist/devo-windows-amd64.exe

# Test
.\dist\devo-windows-amd64.exe --version
```

## Cross-Platform Building

PyInstaller cannot cross-compile. To build for multiple platforms:

1. **Use CI/CD**: GitHub Actions builds for all platforms automatically
2. **Use VMs**: Build on each platform separately
3. **Use Docker**: Build Linux binaries in containers

### GitHub Actions (Recommended)

The project includes GitHub Actions workflow that builds for all platforms:

```yaml
# .github/workflows/release.yml
- Build on ubuntu-latest → Linux binary
- Build on macos-latest → macOS Intel binary
- Build on macos-14 → macOS ARM binary
- Build on windows-latest → Windows binary
```

See [CI/CD Overview](../cicd/overview.md) for details.

## Build Configuration

### PyInstaller Spec File

For advanced configuration, create a `.spec` file:

```bash
# Generate spec file
pyi-makespec --onefile --name devo cli_tool/cli.py

# Edit devo.spec as needed

# Build from spec
pyinstaller devo.spec
```

Example `devo.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['cli_tool/cli.py'],
    pathex=[],
    binaries=[],
    datas=[('cli_tool', 'cli_tool')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='devo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

## Optimization

### Reduce Binary Size

```bash
# Use UPX compression
pyinstaller --onefile --upx-dir=/path/to/upx cli_tool/cli.py

# Exclude unnecessary modules
pyinstaller --onefile \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  cli_tool/cli.py

# Strip debug symbols (Linux/macOS)
strip dist/devo
```

### Improve Startup Time

```bash
# Disable bytecode optimization
pyinstaller --onefile --no-optimize cli_tool/cli.py

# Use --onedir instead of --onefile (faster but multiple files)
pyinstaller --onedir cli_tool/cli.py
```

## Testing Binaries

### Basic Tests

```bash
# Version check
./dist/devo --version

# Help text
./dist/devo --help

# Command execution
./dist/devo config show
```

### Comprehensive Tests

```bash
# Run test suite against binary
export DEVO_BINARY=./dist/devo
pytest tests/

# Manual testing
./dist/devo commit --help
./dist/devo code-reviewer --help
./dist/devo config show
```

## Distribution

### Create Release Package

```bash
# Linux/macOS - tar.gz
tar -czf devo-linux-amd64.tar.gz -C dist devo-linux-amd64

# Windows - zip
powershell Compress-Archive dist/devo-windows-amd64.exe devo-windows-amd64.zip
```

### Generate Checksums

```bash
# SHA256 checksums
cd dist
sha256sum devo-* > SHA256SUMS

# Verify
sha256sum -c SHA256SUMS
```

### Upload to GitHub Releases

Automated via GitHub Actions, or manually:

```bash
# Using GitHub CLI
gh release create v1.0.0 \
  dist/devo-linux-amd64 \
  dist/devo-darwin-amd64 \
  dist/devo-darwin-arm64 \
  dist/devo-windows-amd64.exe \
  dist/SHA256SUMS
```

## Troubleshooting

### Import Errors

If binary fails with import errors:

```bash
# Add hidden imports
pyinstaller --onefile \
  --hidden-import=pkg_resources \
  --hidden-import=boto3 \
  cli_tool/cli.py
```

### Missing Data Files

If binary can't find data files:

```bash
# Add data files
pyinstaller --onefile \
  --add-data "cli_tool:cli_tool" \
  --add-data "config:config" \
  cli_tool/cli.py
```

### Large Binary Size

```bash
# Check what's included
pyinstaller --onefile --log-level=DEBUG cli_tool/cli.py

# Exclude unnecessary modules
pyinstaller --onefile \
  --exclude-module tkinter \
  --exclude-module test \
  cli_tool/cli.py
```

### Antivirus False Positives

Some antivirus software flags PyInstaller binaries:

1. Submit binary to antivirus vendors for whitelisting
2. Sign binary with code signing certificate
3. Build from source instead of using binary

## Code Signing

### macOS

```bash
# Sign binary
codesign --sign "Developer ID Application" dist/devo

# Verify signature
codesign --verify --verbose dist/devo

# Notarize for Gatekeeper
xcrun notarytool submit dist/devo.zip --wait
```

### Windows

```bash
# Sign with certificate
signtool sign /f certificate.pfx /p password dist/devo.exe

# Verify signature
signtool verify /pa dist/devo.exe
```

## Makefile Targets

Available make targets for building:

```bash
make build-binary    # Build for current platform
make build-all       # Build with platform naming
make clean           # Remove build artifacts
make dist-clean      # Remove dist directory
```

## See Also

- [Development Setup](setup.md) - Development environment setup
- [CI/CD Overview](../cicd/overview.md) - Automated builds
- [Contributing](contributing.md) - Contributing guidelines
