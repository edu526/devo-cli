# Semantic Release

This project uses [python-semantic-release](https://python-semantic-release.readthedocs.io/) for automated versioning and releases.

## How It Works

### Conventional Commits

Semantic Release analyzes commit messages following the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>
```

### Version Bumping

Based on commit types:

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `feat:` | Minor (0.X.0) | `feat: add new command` |
| `fix:` | Patch (0.0.X) | `fix: resolve bug in parser` |
| `perf:` | Patch (0.0.X) | `perf: improve startup time` |
| `BREAKING CHANGE:` | Major (X.0.0) | `feat!: redesign CLI interface` |

### Workflow

```
Developer commits with conventional format
    ↓
Push to main branch
    ↓
Release Workflow
    ├─ Analyze commits (python-semantic-release)
    ├─ Determine next version
    ├─ Build binaries
    ├─ Create git tag
    ├─ Update CHANGELOG.md
    ├─ Create GitHub release
    └─ Upload binaries
```

## Commit Message Format

### Types

- `feat:` - New feature (minor version bump)
- `fix:` - Bug fix (patch version bump)
- `perf:` - Performance improvement (patch version bump)
- `docs:` - Documentation changes (patch version bump)
- `style:` - Code style changes (patch version bump)
- `refactor:` - Code refactoring (patch version bump)
- `test:` - Test changes (patch version bump)
- `build:` - Build system changes (patch version bump)
- `ci:` - CI configuration changes (patch version bump)
- `chore:` - Other changes (no version bump)

### Examples

**Feature (minor bump):**
```bash
git commit -m "feat: add code generation command"
git commit -m "feat(cli): add --verbose flag to all commands"
```

**Bug fix (patch bump):**
```bash
git commit -m "fix: resolve template rendering issue"
git commit -m "fix(parser): handle empty input correctly"
```

**Breaking change (major bump):**
```bash
git commit -m "feat!: redesign CLI interface

BREAKING CHANGE: Command structure has changed"
```

**Documentation (patch bump):**
```bash
git commit -m "docs: update installation instructions"
```

**No release:**
```bash
git commit -m "chore: update dependencies"
git commit -m "ci: fix workflow syntax"
```

## Usage

### Automatic Release (Recommended)

Just push to main with conventional commits:

```bash
# Make changes
git add .
git commit -m "feat: add new feature"
git push origin main

# GitHub Actions automatically:
# 1. Analyzes commits
# 2. Determines version (e.g., 1.1.0)
# 3. Builds binaries
# 4. Creates tag v1.1.0
# 5. Updates CHANGELOG.md
# 6. Creates GitHub Release with binaries
```

### Manual Trigger

You can manually trigger the release workflow:

1. Go to Actions → Release
2. Click "Run workflow"
3. Select branch (main)
4. Click "Run workflow"

## Generated Files

Semantic Release automatically updates:

- `CHANGELOG.md` - Auto-generated changelog
- Git tags - Version tags (e.g., `v1.2.3`)
- GitHub Release - With binaries and release notes

## CHANGELOG.md

Automatically generated with sections:

- **Features** - New features (`feat:`)
- **Bug Fixes** - Bug fixes (`fix:`)
- **Performance Improvements** - Performance improvements (`perf:`)
- **Documentation** - Documentation changes (`docs:`)

## Skipping Release

To skip release for a commit:

```bash
git commit -m "chore: update README [skip ci]"
```

Or use `chore:` type (doesn't trigger release).

## Troubleshooting

### No release created

**Check:**
- Commits follow conventional format
- Commits are on `main` branch
- Commit types trigger releases (not `chore:`)
- Workflow has write permissions

### Wrong version bump

**Check:**
- Commit type is correct
- Breaking changes use `!` or `BREAKING CHANGE:`
- Multiple commits are analyzed together

### CHANGELOG not updated

**Check:**
- Workflow completed successfully
- Git push succeeded
- File is committed to repository

## Best Practices

1. **Always use conventional commits** - Enables automatic versioning
2. **Write clear commit messages** - Subject line: what changed
3. **Group related changes** - One feature = one commit
4. **Use scopes for clarity** - `feat(cli):`, `fix(parser):`
5. **Document breaking changes** - Use `!` and `BREAKING CHANGE:`

## Examples

### Feature Release

```bash
# Commit
git commit -m "feat: add template validation"
git push origin main

# Result
# → Version: 1.1.0
# → Tag: v1.1.0
# → CHANGELOG: Added under "Features"
# → Release: Created with binaries
```

### Bug Fix Release

```bash
# Commit
git commit -m "fix: resolve parsing error"
git push origin main

# Result
# → Version: 1.0.1
# → Tag: v1.0.1
# → CHANGELOG: Added under "Bug Fixes"
# → Release: Created with binaries
```

### Breaking Change Release

```bash
# Commit
git commit -m "feat!: redesign command structure

BREAKING CHANGE: Commands now use subcommands"
git push origin main

# Result
# → Version: 2.0.0
# → Tag: v2.0.0
# → CHANGELOG: Added under "BREAKING CHANGES"
# → Release: Created with binaries
```

## Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [python-semantic-release](https://python-semantic-release.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)
