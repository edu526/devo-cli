#!/usr/bin/env python3
"""
Benchmark script to compare Nuitka vs PyInstaller vs Python
Measures startup time and identifies bottlenecks
"""

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path


def measure_execution(command, runs=5):
    """Measure execution time of a command."""
    times = []

    for i in range(runs):
        start = time.time()
        result = subprocess.run(
            command, capture_output=True, text=True, shell=isinstance(command, str)
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            times.append(elapsed)
        else:
            print(f"  Run {i + 1} failed: {result.stderr}")

    if not times:
        return None, None, None

    return statistics.mean(times), min(times), max(times)


def format_time(seconds):
    """Format time in seconds to readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def benchmark_python():
    """Benchmark Python development mode."""
    print("=" * 60)
    print("Python Development Mode")
    print("=" * 60)

    cmd = [sys.executable, "-m", "cli_tool.cli", "--version"]
    avg, min_t, max_t = measure_execution(cmd, runs=3)

    if avg:
        print(f"Average: {format_time(avg)}")
        print(f"Min: {format_time(min_t)}, Max: {format_time(max_t)}")
    else:
        print("Failed to execute")

    return avg


def benchmark_pyinstaller():
    """Benchmark PyInstaller binary if available."""
    print("\n" + "=" * 60)
    print("PyInstaller Binary")
    print("=" * 60)

    # Check for onedir
    if sys.platform == "win32":
        binary = Path("dist/devo/devo.exe")
    else:
        binary = Path("dist/devo/devo")

    if not binary.exists():
        print("Not found (run: pyinstaller devo.spec)")
        return None

    avg, min_t, max_t = measure_execution([str(binary), "--version"], runs=3)

    if avg:
        print(f"Average: {format_time(avg)}")
        print(f"Min: {format_time(min_t)}, Max: {format_time(max_t)}")
    else:
        print("Failed to execute")

    return avg


def benchmark_nuitka():
    """Benchmark Nuitka binary if available."""
    print("\n" + "=" * 60)
    print("Nuitka Binary")
    print("=" * 60)

    if sys.platform == "win32":
        binary = Path("dist/devo-nuitka.exe")
    else:
        binary = Path("dist/devo-nuitka")

    if not binary.exists():
        print("Not found (run: python nuitka-build.py)")
        return None

    avg, min_t, max_t = measure_execution([str(binary), "--version"], runs=3)

    if avg:
        print(f"Average: {format_time(avg)}")
        print(f"Min: {format_time(min_t)}, Max: {format_time(max_t)}")
    else:
        print("Failed to execute")

    return avg


def compare_sizes():
    """Compare binary sizes."""
    print("\n" + "=" * 60)
    print("Binary Sizes")
    print("=" * 60)

    if sys.platform == "win32":
        pyinstaller_path = Path("dist/devo/devo.exe")
        nuitka_path = Path("dist/devo-nuitka.exe")
    else:
        pyinstaller_path = Path("dist/devo/devo")
        nuitka_path = Path("dist/devo-nuitka")

    if pyinstaller_path.exists():
        size_mb = os.path.getsize(pyinstaller_path) / (1024 * 1024)
        print(f"PyInstaller: {size_mb:.1f} MB")
    else:
        print("PyInstaller: Not built")

    if nuitka_path.exists():
        size_mb = os.path.getsize(nuitka_path) / (1024 * 1024)
        print(f"Nuitka:      {size_mb:.1f} MB")
    else:
        print("Nuitka:      Not built")


def main():
    """Run all benchmarks."""
    print("\n" + "=" * 60)
    print("Devo CLI Performance Benchmark")
    print("=" * 60)
    print("\nMeasuring startup time with --version command")
    print("Each test runs 3 times, showing average\n")

    # Run benchmarks
    python_time = benchmark_python()
    pyinstaller_time = benchmark_pyinstaller()
    nuitka_time = benchmark_nuitka()

    # Compare sizes
    compare_sizes()

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    if python_time:
        print(f"\nPython:      {format_time(python_time)}")

    if pyinstaller_time:
        print(f"PyInstaller: {format_time(pyinstaller_time)}", end="")
        if python_time:
            speedup = python_time / pyinstaller_time
            print(f" ({speedup:.1f}x vs Python)")
        else:
            print()

    if nuitka_time:
        print(f"Nuitka:      {format_time(nuitka_time)}", end="")
        if python_time:
            speedup = python_time / nuitka_time
            print(f" ({speedup:.1f}x vs Python)", end="")
        if pyinstaller_time:
            speedup = pyinstaller_time / nuitka_time
            print(f", {speedup:.1f}x vs PyInstaller")
        else:
            print()

    # Recommendation
    print("\n" + "=" * 60)
    print("Recommendation")
    print("=" * 60)

    if nuitka_time and pyinstaller_time:
        if nuitka_time < pyinstaller_time * 0.7:
            improvement = ((pyinstaller_time - nuitka_time) / pyinstaller_time) * 100
            print(f"\n✓ Nuitka is {improvement:.0f}% faster than PyInstaller")
            print("  Migration recommended for better Windows performance")
        elif nuitka_time < pyinstaller_time:
            print("\n✓ Nuitka is slightly faster")
            print("  Migration optional, depends on build time trade-off")
        else:
            print("\n✗ Nuitka is not faster")
            print("  Stick with PyInstaller")
    elif nuitka_time:
        print("\n✓ Nuitka build successful")
        print("  Build PyInstaller for comparison: pyinstaller devo.spec")
    else:
        print("\nBuild Nuitka binary to compare: python nuitka-build.py")


if __name__ == "__main__":
    main()
