#!/usr/bin/env python3
"""
Quick compatibility check before attempting Nuitka build
"""

import sys


def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")

    modules = [
        ("click", "CLI framework"),
        ("jinja2", "Templates"),
        ("rich", "Terminal UI"),
        ("requests", "HTTP client"),
        ("git", "GitPython"),
        ("pydantic", "Validation"),
        ("boto3", "AWS SDK"),
        ("strands_agents", "AI agents"),
        ("cli_tool", "CLI package"),
    ]

    failed = []

    for module, desc in modules:
        try:
            __import__(module)
            print(f"  ✓ {desc:20} ({module})")
        except ImportError as e:
            print(f"  ✗ {desc:20} ({module}) - {e}")
            failed.append(module)

    return len(failed) == 0


def check_dynamic_code():
    """Check for dynamic code that Nuitka might struggle with."""
    print("\nChecking for dynamic code patterns...")

    try:
        import inspect

        import cli_tool.cli

        source = inspect.getsource(cli_tool.cli)

        issues = []

        if "eval(" in source:
            issues.append("eval() found")
        if "exec(" in source:
            issues.append("exec() found")
        if "__import__(" in source:
            issues.append("__import__() found")

        if issues:
            print(f"  ⚠ Potential issues: {', '.join(issues)}")
            return False
        else:
            print("  ✓ No obvious dynamic code patterns")
            return True
    except Exception as e:
        print(f"  ⚠ Could not analyze: {e}")
        return True


def main():
    print("=" * 60)
    print("Nuitka Compatibility Check")
    print("=" * 60)
    print()

    imports_ok = test_imports()
    dynamic_ok = check_dynamic_code()

    print("\n" + "=" * 60)

    if imports_ok and dynamic_ok:
        print("✓ All checks passed!")
        print("\nReady to build with Nuitka:")
        print("  python nuitka-build.py")
        return 0
    elif imports_ok:
        print("⚠ Imports OK, but potential issues detected")
        print("\nYou can try building, but may need adjustments:")
        print("  python nuitka-build.py")
        return 0
    else:
        print("✗ Import failures detected")
        print("\nFix import issues before building")
        return 1


if __name__ == "__main__":
    sys.exit(main())
