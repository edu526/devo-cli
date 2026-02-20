# CI/CD Pipeline

This project uses GitHub Actions for continuous integration and automated releases with Semantic Release.

## Overview

The CI/CD pipeline consists of three main workflows:

1. **Tests** - Run on every push and PR
2. **Semantic Release** - Automated versioning on push to main
3. **Build and Release** - Multi-platform binary builds on tags

## Workflows

### 1. Tests (`test.yml`)

**Trigger:** Every push or pull request to `main` or `develop`

**What it does:**
- Runs linting (flake8)
- Runs unit tests (pytest)
- Tests on Python 3.12

**Duration:** ~2 minutes

**Example:**
```bash
git push origin main
# → Triggers test workflow
```

---

### 2. Semantic Release (`release.yml`)

**Trigger:** Push to `main` branch

**What it does:**
1. Analyzes commits using Conventional Commits
2. Determines next version based on commit types:
   - `feat:` → Minor version (1.0.0 → 1.1.0)
   - `fix:` → Patch version (1.0.0 → 1.0.1)
   - `feat!:` or `BREAKING CHANGE:` → Major version (1.0.0 → 2.0.0)
3. Updates CHANGELOG.md
4. Commits changes with `[skip ci]`
5. Creates and pushes git tag (e.g., v1.2.0)
6. Triggers build workflow via repository_dispatch

**Duration:** ~1 minute

**Example:**
```bash
git commit -m "feat: add new feature"
git push origin main
# → Semantic Release creates v1.1.0
# → Triggers build workflow
```

---

### 3. Build and Release (`build-binaries.yml`)

**Trigger:**
- Tag push (v*)
- Repository dispatch from Semantic Release
- Manual trigger

**What it does:**

#### Job 1: Test
- Runs linting and tests
- Ensures code quality before building

#### Job 2: Build Binaries (Matrix)
Builds binaries in parallel for:
- **Linux amd64** (ubuntu-latest)
- **macOS Intel** (macos-13)
- **macOS Apple Silicon** (macos-14)
- **Windows amd64** (windows-latest)

Each platform:
1. Checks out code
2. Sets up Python 3.12
3. Runs build script
4. Uploads binary as artifact

#### Job 3: Create Release
- Downloads all artifacts
- Prepares release files
- Generates SHA256 checksums
- Uploads to GitHub Release

**Duration:** ~15 minutes (parallel execution)

**Example:**
```bash
# Automatic (via Semantic Release)
git commit -m "feat: add feature"
git push origin main
# → Semantic Release creates tag
# → Build workflow runs automatically

# Manual
git tag v1.0.0
git push origin v1.0.0
# → Build workflow runs
```

---

## Complete Flow

```text
Developer commits with conventional format
    ↓
Push to main
    ↓
┌─────────────────────────────────────┐
│ WORKFLOW 1: test.yml                │
│ - Lint code                          │
│ - Run tests                          │
│ Duration: ~2 min                     │
└─────────────────────────────────────┘
    ↓ (runs in parallel)
┌─────────────────────────────────────┐
│ WORKFLOW 2: release.yml             │
│ - Analyze commits                    │
│ - Determine version                  │
│ - Update CHANGELOG.md                │
│ - Create tag (v1.2.0)                │
│ - Push tag                           │
│ Duration: ~1 min                     │
└─────────────────────────────────────┘
    ↓ (triggered by tag)
┌─────────────────────────────────────┐
│ WORKFLOW 3: build-binaries.yml      │
│ - Run tests                          │
│ - Build binaries (4 platforms)       │
│ - Create GitHub Release              │
│ Duration: ~15 min                    │
└─────────────────────────────────────┘
    ↓
GitHub Release with all artifacts
```

**Total time:** ~18 minutes from commit to release

---

## Build Matrix

| Platform | OS Runner | Python | Build Script | Duration |
|----------|-----------|--------|--------------|----------|
| Linux amd64 | ubuntu-latest | 3.12 | scripts/build.sh | ~3 min |
| macOS Intel | macos-13 | 3.12 | scripts/build.sh | ~5 min |
| macOS M1/M2 | macos-14 | 3.12 | scripts/build.sh | ~5 min |
| Windows | windows-latest | 3.12 | scripts/build-windows.bat | ~4 min |

**Total build time:** ~15 minutes (parallel execution)

---

## Artifacts

### Binaries

- `devo-linux-amd64` - Linux 64-bit (~70-80 MB)
- `devo-darwin-amd64` - macOS Intel (~70-80 MB)
- `devo-darwin-arm64` - macOS Apple Silicon (~70-80 MB)
- `devo-windows-amd64.exe` - Windows 64-bit (~70-80 MB)

### Checksums

- `SHA256SUMS` - SHA256 checksums for all files

---

## Conventional Commits

The pipeline uses Conventional Commits to determine version bumps:

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `feat:` | Minor (0.X.0) | `feat: add validation` |
| `fix:` | Patch (0.0.X) | `fix: resolve bug` |
| `perf:` | Patch (0.0.X) | `perf: improve speed` |
| `docs:` | Patch (0.0.X) | `docs: update README` |
| `style:` | Patch (0.0.X) | `style: format code` |
| `refactor:` | Patch (0.0.X) | `refactor: simplify` |
| `test:` | Patch (0.0.X) | `test: add tests` |
| `build:` | Patch (0.0.X) | `build: update deps` |
| `ci:` | Patch (0.0.X) | `ci: fix workflow` |
| `chore:` | No release | `chore: update config` |
| `feat!:` or `BREAKING CHANGE:` | Major (X.0.0) | Breaking changes |

---

## Manual Triggers

### Trigger Test Workflow
```bash
# Push to main or develop
git push origin main
```

### Trigger Release Workflow
```bash
# Push to main with conventional commits
git commit -m "feat: add feature"
git push origin main
```

### Trigger Build Workflow
```bash
# Option 1: Via Semantic Release (automatic)
git commit -m "feat: add feature"
git push origin main

# Option 2: Manual tag
git tag v1.0.0
git push origin v1.0.0

# Option 3: GitHub UI
# Go to Actions → Build and Release → Run workflow
```

---

## Monitoring

### View Workflow Runs
1. Go to **Actions** tab in GitHub
2. See all workflow runs
3. Click on a run to see details

### View Logs
1. Click on a workflow run
2. Click on a job (e.g., "Build linux-amd64")
3. Expand steps to see logs

### Download Artifacts
1. Go to a completed workflow run
2. Scroll to **Artifacts** section
3. Click to download

---

## Troubleshooting

### Workflow not triggering

**Check:**
- Workflow file is in `.github/workflows/`
- YAML syntax is valid
- Branch/tag matches trigger conditions
- GitHub Actions is enabled

### Build fails on specific platform

**Check:**
- Build script works locally on that platform
- Dependencies are correctly installed
- Python version matches (3.12)
- Review job logs for errors

### Release not created

**Check:**
- Commits follow conventional format
- Commits are on `main` branch
- Commit types trigger releases (not `chore:`)
- All build jobs completed successfully
- `GITHUB_TOKEN` has write permissions

### Wrong version bump

**Check:**
- Commit type is correct
- Breaking changes use `!` or `BREAKING CHANGE:`
- Multiple commits are analyzed together
- Review Semantic Release logs

---

## Secrets and Permissions

### Required Secrets
- `GITHUB_TOKEN` - Automatically provided by GitHub (no setup needed)

### Required Permissions
The workflows need:
- `contents: write` - To create releases and push tags
- `issues: write` - For Semantic Release
- `pull-requests: write` - For Semantic Release

These are configured in `.github/workflows/release.yml`:
```yaml
permissions:
  contents: write
  issues: write
  pull-requests: write
```

---

## Cost

### Public Repositories
- ✅ Unlimited minutes
- ✅ All features free

### Private Repositories
- 2000 minutes/month free
- ~18 minutes per release
- ~2 minutes per test run
- ~111 releases/month within free tier

---

## Best Practices

1. **Always use conventional commits**
   - Enables automatic versioning
   - Generates meaningful changelogs

2. **Test locally before pushing**
   - Run `make test` before committing
   - Build binaries locally with `make build-binary`

3. **Review CHANGELOG.md**
   - Check generated changelog after release
   - Ensure commit messages are clear

4. **Monitor workflow runs**
   - Check Actions tab after pushing
   - Fix failures quickly

5. **Use semantic versioning**
   - Major: Breaking changes
   - Minor: New features
   - Patch: Bug fixes

---

## Next Steps

- Set up branch protection rules
- Configure required status checks
- Add code coverage reporting
- Set up automated dependency updates (Dependabot)
- Configure security scanning (CodeQL)
