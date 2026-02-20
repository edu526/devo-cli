# Binary Distribution Guide

This guide explains how to build and distribute standalone binaries of the Devo CLI tool.

## Overview

The Devo CLI can be distributed as standalone binaries that don't require Python to be installed. This is useful for:

- Users without Python installed
- Simplified installation process
- Corporate environments with restricted Python access
- CI/CD pipelines that need a single executable

## Building Binaries

### Prerequisites

- Python 3.12+ installed
- Virtual environment activated
- All dependencies installed (`pip install -r requirements.txt`)
- PyInstaller will be installed automatically by the build scripts

### Linux/macOS

```bash
# Build for current platform
./scripts/build.sh

# Build with platform-specific naming and versioning
./scripts/build.sh --release
```

### Windows

```cmd
# Build for Windows
scripts\build-windows.bat
```

## Build Output

Binaries are created in:
- `dist/devo` - Single executable (Linux/macOS)
- `dist/devo.exe` - Single executable (Windows)
- `release/vX.Y.Z/` - Platform-specific binaries with checksums

## Binary Size

Expected binary sizes:
- Linux: ~60-80 MB
- macOS: ~70-90 MB
- Windows: ~70-90 MB

The size includes:
- Python runtime
- All dependencies (click, jinja2, rich, strands-agents, boto3, etc.)
- Templates and data files

## Distribution Methods

### GitHub Releases (Primary)

All releases are published to GitHub Releases with binaries for all platforms.

**Download URL:**

```text
https://github.com/edu526/devo-cli/releases
```

**Latest release:**

```bash
# Linux
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-linux-amd64 -o devo

# macOS Intel
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-darwin-amd64 -o devo

# macOS Apple Silicon
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-darwin-arm64 -o devo

# Windows
curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-windows-amd64.exe -o devo.exe
```

### Installation Script

An automated installation script is provided at the root of the repository (`install.sh`).

**Usage:**

```bash
# Download and run
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash

# Or download first, then run
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh -o install.sh
chmod +x install.sh
./install.sh
```

The script will:
- Detect your platform and architecture
- Download the appropriate binary
- Verify the binary works
- Offer installation options (system-wide or user-only)
- Configure PATH if needed

## Usage

The binary works exactly like the pip-installed version:

```bash
# Check version
./devo --version

# Get help
./devo --help

# Use commands
./devo commit
./devo generate
./devo code-reviewer
```

## AWS Credentials

The binary requires AWS credentials to be configured:

```bash
# Configure AWS credentials
aws configure

# Or use environment variables
export AWS_PROFILE=your-profile
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
```

## Limitations

1. **Size**: Binaries are large (~70-90 MB) due to bundled dependencies
2. **Startup time**: Slightly slower than native Python (~1-2 seconds)
3. **Platform-specific**: Must build separately for each OS/architecture
4. **Updates**: Users must manually download new versions (no auto-update in binary mode)

## Troubleshooting

### Binary won't run on Linux

```bash
# Check if executable
chmod +x devo

# Check dependencies
ldd devo
```

### macOS security warning

```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine devo

# Or allow in System Preferences > Security & Privacy
```

### Windows antivirus blocking

- Add exception for the binary in Windows Defender
- Sign the binary with a code signing certificate (recommended for production)

## CI/CD Integration

### GitHub Actions

```yaml
name: Build Binaries

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build binary (Linux/macOS)
        if: runner.os != 'Windows'
        run: ./build-binaries.sh

      - name: Build binary (Windows)
        if: runner.os == 'Windows'
        run: build-windows.bat

      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: devo-${{ runner.os }}
          path: dist/devo*
```

## Binary Advantages

| Feature | Details |
|---------|---------|
| Python required | ❌ No - Standalone executable |
| Size | ~70-90 MB (includes Python runtime) |
| Startup time | ~1-2s (slightly slower than native Python) |
| Updates | Download new version from GitHub Releases |
| Distribution | Single file - easy to distribute |
| Best for | End users, CI/CD, production environments |

## Recommendations

1. **Primary distribution**: GitHub Releases with binaries
2. **Provide installation script**: Easy one-line install
3. **Document clearly**: Installation instructions in README
4. **Automate builds**: GitHub Actions builds on every release
5. **Provide checksums**: SHA256SUMS for verification
6. **Version in filename**: devo-platform-arch format

## Next Steps

- Set up automated binary builds in CI/CD
- Create installation scripts for each platform
- Add binary distribution to documentation
- Consider using GitHub Releases for distribution
