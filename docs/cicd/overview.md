# CI/CD Overview

This project uses two GitHub Actions workflows to test code and publish releases automatically.

## Workflow Strategy

### Why Two Workflows?

**Test Workflow** (`.github/workflows/test.yml`) — runs on every pull request:

- Runs pytest and pre-commit hooks (flake8, isort)
- Builds binaries on all platforms to catch compatibility issues early
- Fast feedback before merge — no release artifacts are published

**Release Workflow** (`.github/workflows/release.yml`) — runs on push to `main`:

- Re-runs the full test suite
- Uses python-semantic-release to analyze commits and determine the next version
- Builds binaries for all platforms in parallel
- Creates a GitHub Release with binaries, checksums, and auto-generated release notes
- Skips release entirely if no conventional commits are found

## Configuration Files

| File | Purpose |
|------|---------|
| `.github/workflows/test.yml` | Test workflow for pull requests |
| `.github/workflows/release.yml` | Release workflow for main branch |
| `.github/workflows/test-reusable.yml` | Shared test job used by both workflows |
| `devo.spec` | PyInstaller configuration |
| `scripts/build.sh` | Linux/macOS build script |
| `scripts/build-windows.bat` | Windows build script |
| `scripts/package-windows.ps1` | Windows ZIP packaging |

## See Also

- [GitHub Actions](github-actions.md) — full workflow reference, secrets, notifications, monitoring
- [Semantic Release](semantic-release.md) — conventional commits and automated versioning
- [Building Binaries](../development/building.md) — local binary builds
