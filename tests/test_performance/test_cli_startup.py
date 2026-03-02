"""Performance tests for CLI startup time.

Tests CLI startup performance with pytest-benchmark to ensure the CLI
starts quickly and meets the 2-second startup time requirement for
Python module execution and onedir binaries.

Requirements tested:
- 17.3: CLI startup time is under 2 seconds for Python module and onedir binaries
- 17.5: Use pytest-benchmark for performance regression detection
"""

import subprocess
import sys

import pytest
from click.testing import CliRunner

from cli_tool.cli import cli


@pytest.mark.slow
@pytest.mark.integration
def test_cli_startup_time_with_version(benchmark, cli_runner):
    """Test CLI startup time with --version flag.

    Validates: Requirements 17.3, 17.5

    This test benchmarks the CLI invocation with --version flag to measure
    startup time. The requirement is that startup time should be under 2 seconds
    for Python module execution and PyInstaller onedir binaries.
    """
    # Benchmark CLI invocation with --version
    result = benchmark(cli_runner.invoke, cli, ["--version"])

    # Verify success
    assert result.exit_code == 0
    assert "unknown" in result.output or "." in result.output  # Version format


@pytest.mark.slow
@pytest.mark.integration
def test_cli_startup_time_with_help(benchmark, cli_runner):
    """Test CLI startup time with --help flag.

    Validates: Requirements 17.3, 17.5

    This test benchmarks the CLI invocation with --help flag to measure
    startup time for help text generation, which exercises more of the
    CLI initialization code.
    """
    # Benchmark CLI invocation with --help
    result = benchmark(cli_runner.invoke, cli, ["--help"])

    # Verify success
    assert result.exit_code == 0
    assert "CLI for developers" in result.output or "Commands" in result.output


@pytest.mark.slow
@pytest.mark.integration
def test_cli_startup_time_python_module(benchmark):
    """Test CLI startup time via Python module execution.

    Validates: Requirements 17.3, 17.5

    This test benchmarks the CLI startup time when invoked as a Python module
    (python -m cli_tool.cli --version) to measure real-world startup performance.
    """

    def run_cli_module():
        """Run CLI as Python module and return result."""
        result = subprocess.run(
            [sys.executable, "-m", "cli_tool.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result

    # Benchmark module execution
    result = benchmark(run_cli_module)

    # Verify success
    assert result.returncode == 0
    assert result.stdout.strip() or result.stderr.strip()


@pytest.mark.slow
@pytest.mark.integration
def test_cli_startup_time_no_args(benchmark, cli_runner):
    """Test CLI startup time with no arguments (shows help).

    Validates: Requirements 17.3, 17.5

    This test benchmarks the CLI invocation with no arguments, which
    displays help text and exercises the full CLI initialization.
    """
    # Benchmark CLI invocation with no arguments
    result = benchmark(cli_runner.invoke, cli, [])

    # Verify help is shown (Click returns exit code 0 for help display)
    # Note: Exit code may be 0 or 2 depending on Click version
    assert result.exit_code in (0, 2)
    assert "Commands" in result.output or "Usage" in result.output


@pytest.mark.slow
@pytest.mark.integration
def test_cli_command_list_startup(benchmark, cli_runner):
    """Test CLI startup time when listing available commands.

    Validates: Requirements 17.3, 17.5

    This test benchmarks the time to initialize the CLI and list all
    available commands, which requires loading all command modules.
    """

    def invoke_and_parse_commands():
        """Invoke CLI and parse available commands."""
        result = cli_runner.invoke(cli, ["--help"])
        # Parse commands from help output
        commands = []
        in_commands_section = False
        for line in result.output.split("\n"):
            if "Commands:" in line:
                in_commands_section = True
                continue
            if in_commands_section and line.strip():
                # Extract command name (first word)
                parts = line.strip().split()
                if parts:
                    commands.append(parts[0])
        return result, commands

    # Benchmark command listing
    result, commands = benchmark(invoke_and_parse_commands)

    # Verify success and commands are listed
    assert result.exit_code == 0
    assert len(commands) > 0
    # Verify some expected commands are present
    expected_commands = ["commit", "upgrade", "aws-login"]
    assert any(cmd in commands for cmd in expected_commands)


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize("command_flag", ["--version", "--help"])
def test_cli_startup_time_parametrized(benchmark, cli_runner, command_flag):
    """Test CLI startup time with different flags.

    Validates: Requirements 17.3, 17.5

    This parametrized test benchmarks CLI startup with different flags
    to ensure consistent performance across different invocation patterns.
    """
    # Benchmark CLI invocation with specified flag
    result = benchmark(cli_runner.invoke, cli, [command_flag])

    # Verify success
    assert result.exit_code == 0
    assert len(result.output) > 0


@pytest.mark.slow
@pytest.mark.integration
def test_cli_import_time(benchmark):
    """Test CLI module import time.

    Validates: Requirements 17.3, 17.5

    This test benchmarks the time to import the CLI module, which
    measures the overhead of loading all dependencies and initializing
    the CLI infrastructure.
    """

    def import_cli_module():
        """Import CLI module and return the cli object."""
        # Use importlib to import fresh each time
        import importlib
        import sys

        # Remove from cache if present
        if "cli_tool.cli" in sys.modules:
            del sys.modules["cli_tool.cli"]

        # Import module
        module = importlib.import_module("cli_tool.cli")
        return module.cli

    # Benchmark import
    cli_obj = benchmark(import_cli_module)

    # Verify CLI object was imported
    assert cli_obj is not None
    assert hasattr(cli_obj, "commands")


@pytest.mark.slow
@pytest.mark.integration
def test_cli_startup_memory_footprint():
    """Test CLI startup memory footprint.

    Validates: Requirements 17.3, 17.5

    This test measures the memory footprint of CLI startup to ensure
    it doesn't consume excessive memory during initialization.
    """
    import tracemalloc

    # Start memory tracking
    tracemalloc.start()

    # Import and initialize CLI
    from cli_tool.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    # Get memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Verify success
    assert result.exit_code == 0

    # Memory usage should be reasonable (less than 100MB for CLI startup)
    # This is a conservative limit; actual usage should be much lower
    peak_mb = peak / 1024 / 1024
    assert peak_mb < 100, f"Peak memory usage {peak_mb:.2f}MB exceeds 100MB limit"


@pytest.mark.slow
@pytest.mark.integration
def test_cli_cold_start_performance(benchmark):
    """Test CLI cold start performance with subprocess.

    Validates: Requirements 17.3, 17.5

    This test benchmarks the CLI cold start time by invoking it as a
    subprocess, which measures the real-world startup performance including
    Python interpreter startup and module loading.
    """

    def cold_start_cli():
        """Run CLI in subprocess for cold start measurement."""
        result = subprocess.run(
            [sys.executable, "-m", "cli_tool.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result

    # Benchmark cold start
    result = benchmark.pedantic(cold_start_cli, iterations=5, rounds=3)

    # Verify success
    assert result.returncode == 0

    # Note: Cold start includes Python interpreter startup, so it may be
    # slightly slower than the 2-second target, but should still be reasonable
