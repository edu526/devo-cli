# Nuitka Build Experiment

This branch tests Nuitka as an alternative to PyInstaller for building Windows binaries.

## Goal

Improve Windows CLI startup performance by using Nuitka (Python-to-C compiler) instead of PyInstaller (bundler).

## Expected Benefits

- **Faster startup**: 2-3x faster than PyInstaller (no extraction overhead)
- **Smaller binaries**: Native code is more compact
- **Better compatibility**: No antivirus false positives
- **True native**: Compiled to machine code, not bundled Python

## Prerequisites

### Windows
```bash
# Install Nuitka
pip install nuitka

# Install C compiler (choose one):
# Option 1: Visual Studio Build Tools (recommended)
#   Download: https://visualstudio.microsoft.com/downloads/
#   Select: "Desktop development with C++"

# Option 2: MinGW64
#   Download: https://www.mingw-w64.org/
#   Add to PATH
```

### Linux/Mac
```bash
# Install Nuitka
pip install nuitka

# GCC should already be installed
# If not: sudo apt install gcc (Ubuntu) or xcode-select --install (Mac)
```

## Quick Start

### 1. Build with Nuitka
```bash
python nuitka-build.py
```

This will:
- Check prerequisites (Nuitka, C compiler)
- Clean previous builds
- Compile Python to C to native executable
- Test the binary
- Takes 5-15 minutes on first build

### 2. Benchmark Performance
```bash
python benchmark.py
```

This compares:
- Python development mode
- PyInstaller binary (if available)
- Nuitka binary

### 3. Test Thoroughly
```bash
# Windows
dist\devo-nuitka.exe --version
dist\devo-nuitka.exe --help
dist\devo-nuitka.exe generate --help
dist\devo-nuitka.exe commit --help

# Linux/Mac
./dist/devo-nuitka --version
./dist/devo-nuitka --help
./dist/devo-nuitka generate --help
./dist/devo-nuitka commit --help
```

## Files Added

- `nuitka-build.py` - Build script for Nuitka compilation
- `benchmark.py` - Performance comparison tool
- `README_NUITKA.md` - This file

## Expected Results

### Startup Time (--version command)
- Python: ~1.5s
- PyInstaller: ~0.8s
- Nuitka: ~0.3s (target)

### Binary Size
- PyInstaller: ~60MB (folder)
- Nuitka: ~30MB (single file)

### Build Time
- PyInstaller: ~2 minutes
- Nuitka: ~10 minutes (first build), ~5 minutes (incremental)

## Known Issues

### Potential Compatibility Problems
1. **boto3/botocore**: Large AWS SDK, may need plugins
2. **strands-agents**: Unknown compatibility, needs testing
3. **Dynamic imports**: If any exist, may fail compilation

### Solutions
- Add Nuitka plugins for problematic packages
- Use `--include-package` for missing modules
- Modify code to avoid dynamic imports if needed

## Decision Criteria

### Migrate to Nuitka if:
- ✓ Compilation succeeds without major issues
- ✓ All commands work correctly
- ✓ Startup is 2x+ faster than PyInstaller
- ✓ Build time is acceptable for CI/CD

### Stick with PyInstaller if:
- ✗ Compilation fails or requires extensive fixes
- ✗ Runtime errors in compiled binary
- ✗ Performance gain is minimal (<30%)
- ✗ Build time is too long for workflow

## Next Steps

1. **Build**: Run `python nuitka-build.py`
2. **Benchmark**: Run `python benchmark.py`
3. **Test**: Test all CLI commands thoroughly
4. **Decide**: Based on results, migrate or revert
5. **Document**: Update main README if migrating

## Rollback

If Nuitka doesn't work well:

```bash
# Switch back to main branch
git checkout main

# PyInstaller build still works
pyinstaller devo.spec
```

## Questions?

See Nuitka documentation: https://nuitka.net/doc/user-manual.html
