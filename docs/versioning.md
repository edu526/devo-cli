# Automatic Versioning with Tags

This project now uses `setuptools_scm` to automatically generate versions based on Git tags.

## How it works

1. **Without tags**: Version will be something like `0.0.0.post54+gf1b93a15b.d20250903` (development version)
2. **With tags**: Version will follow the tag, for example `v1.2.0` → `1.2.0`

## How to create a release

### 1. Prepare the code
```bash
# Make sure all changes are committed
git add .
git commit -m "feat: prepare release v1.2.0"
git push origin main
```

### 2. Create and push the tag
```bash
# Create the tag (use semantic versioning)
git tag v1.2.0

# Push the tag
git push origin v1.2.0
```

### 3. Automatic deployment

When pushing the tag, GitHub Actions will automatically:
- Run tests
- Analyze commits with Semantic Release
- Build binaries for all platforms (Linux, macOS, Windows)
- Create GitHub Release with all artifacts

## Tag examples

- `v1.0.0` - Major release
- `v1.1.0` - Minor release (new features)
- `v1.1.1` - Patch (bugfixes)
- `v2.0.0-rc1` - Release candidate
- `v1.1.1-beta1` - Beta release

## Check the version

```bash
# See current version (without tag)
python -c "from setuptools_scm import get_version; print(get_version())"

# After installing the package
devo --version
```

## Tips

1. **Always use the `v` prefix** in tags (e.g.: `v1.2.0`, not `1.2.0`)
2. **Follow semantic versioning**: MAJOR.MINOR.PATCH
3. **Don't manually change** the version in `setup.py` - it's generated automatically
4. **The `_version.py` file** is generated automatically and should not be edited or committed to the repo

## Rollback

If you need to delete a tag:
```bash
# Delete tag locally
git tag -d v1.2.0

# Delete tag from remote repository
git push origin --delete v1.2.0
```
