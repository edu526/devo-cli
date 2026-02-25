# CI/CD Workflows

This document describes the CI/CD workflows for the Devo CLI project.

## Test Workflow (Pull Requests)

**File:** `.github/workflows/test.yml`

**Triggers:**
- Pull requests targeting `main` branch

**Jobs:**

### 1. Run Tests
- Runs pytest with all unit tests
- Uses Python 3.12 on Ubuntu
- Runs pre-commit hooks (flake8, isort)

### 2. Build Test (All Platforms)
- Builds binaries on all platforms (Linux, macOS Intel, macOS ARM, Windows)
- Tests binary execution (`--version`)
- Validates binary size
- Ensures PyInstaller build works on each platform

**Purpose:** Fast feedback to developers. Catches issues before merge.

## Release Workflow (Main Branch)

**File:** `.github/workflows/release.yml`

**Triggers:**
- Push to `main` branch
- Manual workflow dispatch

**Jobs:**

### 1. Run Tests
- Same as test workflow
- Ensures code quality before release

### 2. Check Version
- Uses python-semantic-release to analyze commits
- Determines if new release is needed
- Calculates next version number
- Skips if no conventional commits found

### 3. Build Binaries (Parallel)
- **Linux** (amd64)
- **macOS** (amd64 Intel)
- **macOS** (arm64 Apple Silicon)
- **Windows** (amd64) - builds and packages as ZIP
- Only runs if new release is needed

### 4. Create Release
- Uses python-semantic-release to:
  - Create git tag
  - Update CHANGELOG.md
  - Commit changes
  - Create GitHub release

### 5. Upload Assets
- Downloads all binary artifacts
- Generates SHA256 checksums
- Uploads to GitHub release

### 6. Notify Telegram (Optional)
- Sends notification on success/failure/no-release
- Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID configured

**Purpose:** Automated versioning and distribution for all platforms.

## Workflow Strategy

### Why Two Workflows?

**Test Workflow (Pull Requests):**
- Runs on every PR
- Tests code quality and binary builds
- Catches issues before merge
- Builds binaries on all platforms to ensure compatibility

**Release Workflow (Main Branch):**
- Only runs on main branch
- Analyzes commits to determine if release is needed
- Automatically versions and publishes releases
- Distributes binaries for all platforms

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

### Test Workflow Fails

**Lint/format errors:**
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

**No release created:**
- Ensure commits follow conventional format (feat:, fix:, etc.)
- Check that commits exist since last release

**Binary build fails:**
- Check platform-specific build scripts
- Review PyInstaller spec file (devo.spec)

**Upload fails:**
- Verify GitHub token permissions
- Check that release was created successfully

## Configuration Files

- `.github/workflows/test.yml` - Test workflow for PRs
- `.github/workflows/release.yml` - Release workflow for main branch
- `.github/workflows/test-reusable.yml` - Shared test job
- `devo.spec` - PyInstaller configuration
- `scripts/build.sh` - Linux/macOS build script
- `scripts/build-windows.bat` - Windows build script
- `scripts/package-windows.ps1` - Windows ZIP packaging
