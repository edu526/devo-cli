# Documentation

Complete documentation for the Devo CLI project.

## Getting Started

- [Development Guide](development.md) - Setup and development workflow
- [Contributing Guidelines](contributing.md) - How to contribute

## CI/CD & Releases

- [CI/CD Pipeline](cicd.md) - GitHub Actions workflows and automation
- [Semantic Release](semantic-release.md) - Automated versioning with conventional commits
- [Versioning](versioning.md) - Version management strategy

## Distribution

- [Binary Distribution](binary-distribution.md) - Building and distributing standalone binaries

## Quick Reference

### Development
```bash
# Setup
./setup-dev.sh

# Build locally
make build-binary

# Run tests
make test
```

### Releases
```bash
# Commit with conventional format
git commit -m "feat: add new feature"

# Push to main
git push origin main

# Semantic Release handles the rest:
# - Determines version
# - Updates CHANGELOG
# - Creates tag
# - Triggers builds
# - Creates GitHub Release
```

### Commit Types
- `feat:` - New feature (minor version bump)
- `fix:` - Bug fix (patch version bump)
- `docs:` - Documentation changes
- `chore:` - No release
- `feat!:` - Breaking change (major version bump)

## File Organization

```
docs/
├── README.md                    # This file
├── cicd.md                      # CI/CD pipeline documentation
├── semantic-release.md          # Semantic Release guide
├── binary-distribution.md       # Binary distribution guide
├── development.md               # Development guide
├── contributing.md              # Contributing guidelines
└── versioning.md                # Versioning strategy
```
