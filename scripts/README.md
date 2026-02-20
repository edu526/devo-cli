# Build Scripts

This directory contains build and installation scripts for the Devo CLI project.

## Main Build Script

### build.sh
Unified build script for all environments (local development, CI/CD, all platforms).

**Usage:**
```bash
# Simple build (local development)
./scripts/build.sh

# Build with versioned release
./scripts/build.sh --release

# CI/CD mode (installs dependencies, fetches git history)
./scripts/build.sh --ci --release

# Show help
./scripts/build.sh --help
```

**Modes:**

1. **Local Development** (default)
   - Uses existing virtual environment
   - Installs PyInstaller if needed
   - Builds to `dist/devo`

2. **Release Mode** (`--release`)
   - Creates versioned release directory
   - Platform-specific naming: `devo-{platform}-{arch}`
   - Generates SHA256 checksums
   - Output: `release/vX.Y.Z/`

3. **CI/CD Mode** (`--ci`)
   - Installs all dependencies
   - Fetches full git history for versioning
   - Perfect for Bitbucket Pipelines

**Examples:**
```bash
# Local quick build
./scripts/build.sh

# Local release build
./scripts/build.sh --release

# CI/CD (Bitbucket Pipelines)
./scripts/build.sh --ci --release
```

## Platform-Specific Scripts

### build-windows.bat
Builds a standalone binary for Windows.

**Usage:**
```cmd
scripts\build-windows.bat
```

**Output:**
- `dist\devo.exe` - Windows executable

## Installation Scripts

### install-binary.sh
User-friendly installation script for downloading and installing Devo CLI binaries.

**Usage:**
```bash
# Install latest version
curl -fsSL https://your-domain.com/install.sh | bash

# Install specific version
./scripts/install-binary.sh v1.0.0
```

**Features:**
- Auto-detects platform and architecture
- Downloads binary from configured URL
- Verifies binary integrity
- Offers multiple installation locations
- Checks PATH configuration

**Installation Options:**
1. `/usr/local/bin` - System-wide (requires sudo)
2. `~/.local/bin` - User-only (no sudo)
3. Current directory - Manual setup

## Directory Structure

```
scripts/
├── README.md              # This file
├── build.sh               # Unified build script (Linux/macOS)
├── build-windows.bat      # Windows build script
└── install-binary.sh      # User installation script
```

## Integration

### Makefile
```bash
make build-binary  # Calls scripts/build.sh
make build-all     # Calls scripts/build.sh --release
```

### Bitbucket Pipelines
```yaml
- bash scripts/build.sh --ci --release
```

## Development Workflow

1. **Local development:**
   ```bash
   make build-binary
   ./dist/devo --version
   ```

2. **Create release:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   # Bitbucket runs scripts/build.sh --ci --release
   ```

3. **Distribute:**
   - Download from Bitbucket Pipelines artifacts
   - Upload to S3 or Bitbucket Downloads
   - Users install with `install-binary.sh`

## Platform Support

| Platform | Script | Status |
|----------|--------|--------|
| Linux (amd64, arm64) | build.sh | ✅ |
| macOS (amd64, arm64) | build.sh | ✅ |
| Windows (amd64) | build-windows.bat | ✅ |

## Troubleshooting

### Permission denied
```bash
chmod +x scripts/*.sh
```

### Virtual environment not found
```bash
make venv
source venv/bin/activate
```

### PyInstaller errors
```bash
pip install --upgrade pyinstaller
make clean
make build-binary
```

## Configuration

### Update Distribution URL
Edit `scripts/install-binary.sh`:
```bash
BASE_URL="https://your-domain.com/devo-cli"
```

### Customize Build
Edit `devo.spec` in project root for PyInstaller configuration.

## Why One Script?

Previously we had 3 separate scripts (`build-binaries.sh`, `build-binary-linux.sh`, `build-all-platforms.sh`) that did similar things. Now we have one unified script with flags:

- **Simpler**: One script to maintain
- **Flexible**: Different modes for different needs
- **DRY**: No code duplication
- **Clear**: Explicit flags show intent
