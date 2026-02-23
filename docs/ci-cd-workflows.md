# CI/CD Workflows

This document describes the CI/CD workflows for the Devo CLI project.

## PR Workflow (Fast - ~5 minutes)

**File:** `.github/workflows/test.yml`

**Triggers:**
- Pull requests to `main` or `develop`
- Pushes to `main` or `develop`

**Jobs:**

### 1. Lint & Format Check (~1 min)
- Runs flake8 for code quality
- Checks black formatting
- Checks isort import ordering

### 2. Unit Tests (~2 min)
- Runs pytest with all unit tests
- Uses Python 3.12 on Ubuntu
- Runs pre-commit hooks

### 3. Binary Build Test (~2 min)
- Builds Linux binary only (fastest platform)
- Tests binary execution (`--version`)
- Validates binary size
- Ensures PyInstaller build works

**Purpose:** Fast feedback to developers. Catches most issues before merge.

## Release Workflow (Complete - ~20 minutes)

**File:** `.github/workflows/release.yml`

**Triggers:**
- Push to `main` branch
- Manual workflow dispatch

**Jobs:**

### 1. Check Version
- Determines if new release is needed
- Uses semantic-release to calculate next version

### 2. Build Binaries (parallel)
- **Linux** (amd64)
- **macOS** (amd64 Intel)
- **macOS** (arm64 Apple Silicon)
- **Windows** (amd64) - builds and packages as ZIP

### 3. Create Release
- Creates git tag
- Updates CHANGELOG.md
- Creates GitHub release

### 4. Upload Assets
- Uploads all platform binaries
- Generates SHA256 checksums
- Attaches to GitHub release

### 5. Notify
- Sends Telegram notification on success/failure

**Purpose:** Complete build and distribution for all platforms.

## Workflow Strategy

### Why Two Workflows?

**PR Workflow (Fast):**
- Provides quick feedback (5 min vs 20 min)
- Catches 95% of issues early
- Saves CI/CD resources
- Single Linux build validates PyInstaller works

**Release Workflow (Complete):**
- Builds all platforms only when needed
- Ensures production binaries work
- Runs only on main branch

### What Gets Tested in PRs?

✅ Code quality (linting, formatting)
✅ Unit tests
✅ Binary compilation (Linux)
✅ Binary execution

❌ Multi-platform builds (only in release)
❌ Distribution packaging (only in release)

## Local Testing

Before pushing, run:

```bash
# Lint and format
make lint
make format

# Run tests
make test

# Test binary build (optional)
make build-binary
./dist/devo --version
```

## Troubleshooting

### PR Workflow Fails

**Lint errors:**
```bash
make format  # Auto-fix formatting
make lint    # Check remaining issues
```

**Test failures:**
```bash
pytest -v  # Run tests locally
```

**Binary build fails:**
```bash
bash scripts/build.sh  # Test build locally
```

### Release Workflow Fails

**Version not detected:**
- Ensure commits follow conventional format
- Check semantic-release configuration

**Binary build fails:**
- Check platform-specific build scripts
- Review PyInstaller spec file

**Upload fails:**
- Verify GitHub token permissions
- Check asset naming matches expected pattern

## Configuration Files

- `.github/workflows/test.yml` - PR workflow
- `.github/workflows/release.yml` - Release workflow
- `.github/workflows/test-reusable.yml` - Shared test job
- `devo.spec` - PyInstaller configuration
- `scripts/build.sh` - Linux/macOS build script
- `scripts/build-windows.bat` - Windows build script
- `scripts/package-windows.ps1` - Windows ZIP packaging
