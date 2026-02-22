#!/usr/bin/env python3
"""
Nuitka build script for Devo CLI
Compiles Python to native executable for better Windows performance
"""

import os
import shutil
import subprocess
import sys


def check_nuitka():
    """Check if Nuitka is installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"✓ Nuitka found: {result.stdout.strip()}")
            return True
    except Exception:
        pass

    print("✗ Nuitka not found")
    print("\nInstall with: pip install nuitka")
    return False


def check_compiler():
    """Check if C compiler is available."""
    # Check for MSVC (Windows)
    if sys.platform == "win32":
        result = subprocess.run(["where", "cl.exe"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ MSVC compiler found")
            return True

        # Check for MinGW
        result = subprocess.run(["where", "gcc.exe"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ MinGW compiler found")
            return True

        print("✗ No C compiler found")
        print("\nInstall Visual Studio Build Tools or MinGW64")
        print("  https://visualstudio.microsoft.com/downloads/")
        return False

    # Check for GCC (Linux/Mac)
    result = subprocess.run(["which", "gcc"], capture_output=True, text=True)
    if result.returncode == 0:
        print("✓ GCC compiler found")
        return True

    print("✗ GCC not found")
    return False


def clean_build():
    """Clean previous build artifacts."""
    print("\nCleaning previous builds...")

    dirs_to_clean = [
        "build/nuitka",
        "dist/devo-nuitka.dist",
    ]

    files_to_clean = [
        "dist/devo-nuitka.exe",
        "dist/devo-nuitka",
    ]

    for dir_path in dirs_to_clean:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"  Removed {dir_path}")

    for file_path in files_to_clean:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"  Removed {file_path}")


def build_nuitka():
    """Build with Nuitka."""
    print("\n" + "=" * 60)
    print("Building with Nuitka...")
    print("=" * 60)
    print("\nThis will take 5-15 minutes on first build...")
    print()

    # Ensure dist directory exists
    os.makedirs("dist", exist_ok=True)

    # Nuitka command
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        "--output-dir=build/nuitka",
        "--include-package=cli_tool",
        "--include-package-data=cli_tool",
        "--enable-plugin=anti-bloat",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=setuptools",
        "--nofollow-import-to=distutils",
        "--nofollow-import-to=wheel",
        "--nofollow-import-to=pip",
        "--assume-yes-for-downloads",
    ]

    # Platform-specific options
    if sys.platform == "win32":
        cmd.extend(
            [
                "--windows-console-mode=attach",
                "--company-name=Devo CLI",
                "--product-name=Devo CLI Tool",
                "--file-description=AI-powered CLI for developers",
                "--output-filename=devo-nuitka.exe",
            ]
        )
    else:
        cmd.append("--output-filename=devo-nuitka")

    # Add entry point
    cmd.append("cli_tool/cli.py")

    # Run Nuitka
    print(f"Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("\n✗ Build failed")
        return False

    # Move binary to dist
    if sys.platform == "win32":
        src = "build/nuitka/devo-nuitka.exe"
        dst = "dist/devo-nuitka.exe"
    else:
        src = "build/nuitka/devo-nuitka"
        dst = "dist/devo-nuitka"

    if os.path.exists(src):
        shutil.move(src, dst)
        print(f"\n✓ Binary moved to {dst}")
        return True

    print(f"\n✗ Binary not found at {src}")
    return False


def test_binary():
    """Test the built binary."""
    print("\n" + "=" * 60)
    print("Testing binary...")
    print("=" * 60)

    if sys.platform == "win32":
        binary = "dist/devo-nuitka.exe"
    else:
        binary = "dist/devo-nuitka"

    if not os.path.exists(binary):
        print(f"✗ Binary not found: {binary}")
        return False

    # Get file size
    size_mb = os.path.getsize(binary) / (1024 * 1024)
    print(f"\nBinary size: {size_mb:.1f} MB")

    # Test version
    print("\nTest 1: --version")
    result = subprocess.run([binary, "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ PASSED: {result.stdout.strip()}")
    else:
        print(f"✗ FAILED: {result.stderr}")
        return False

    # Test help
    print("\nTest 2: --help")
    result = subprocess.run([binary, "--help"], capture_output=True, text=True)
    if result.returncode == 0:
        print("✓ PASSED")
    else:
        print(f"✗ FAILED: {result.stderr}")
        return False

    print("\n✓ All tests passed!")
    return True


def main():
    """Main build process."""
    print("=" * 60)
    print("Nuitka Build for Devo CLI")
    print("=" * 60)

    # Check prerequisites
    print("\nChecking prerequisites...")
    if not check_nuitka():
        return 1

    if not check_compiler():
        return 1

    # Clean
    clean_build()

    # Build
    if not build_nuitka():
        return 1

    # Test
    if not test_binary():
        return 1

    # Success
    print("\n" + "=" * 60)
    print("Build Complete!")
    print("=" * 60)

    if sys.platform == "win32":
        print("\nBinary: dist\\devo-nuitka.exe")
        print("\nNext steps:")
        print("  1. Test: dist\\devo-nuitka.exe --version")
        print("  2. Benchmark: python benchmark.py")
        print("  3. Test all commands thoroughly")
    else:
        print("\nBinary: dist/devo-nuitka")
        print("\nNext steps:")
        print("  1. Test: ./dist/devo-nuitka --version")
        print("  2. Benchmark: python benchmark.py")
        print("  3. Test all commands thoroughly")

    return 0


if __name__ == "__main__":
    sys.exit(main())
