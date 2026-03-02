"""Performance regression tests for core operations.

Tests performance characteristics of critical operations to detect regressions
over time. Uses pytest-benchmark to measure and track performance metrics.

Requirements tested:
- 17.5: Use pytest-benchmark for performance regression detection
- 21.1: Regression tests to prevent performance degradation
"""

import json
from pathlib import Path

import pytest

from cli_tool.core.utils.config_manager import load_config, save_config
from cli_tool.core.utils.git_utils import get_staged_diff


@pytest.mark.slow
@pytest.mark.unit
def test_config_file_loading_performance(benchmark, temp_config_dir, mocker):
    """Test config file loading performance.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of loading configuration files
    to detect regressions in config file I/O and parsing operations.
    """
    # Setup: Create a realistic config file
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create a realistic config with nested structure
    test_config = {
        "aws": {
            "region": "us-east-1",
            "sso_profiles": [
                {
                    "name": "dev",
                    "start_url": "https://dev.awsapps.com/start",
                    "region": "us-east-1",
                    "account_id": "123456789012",
                    "role_name": "Developer",
                },
                {
                    "name": "prod",
                    "start_url": "https://prod.awsapps.com/start",
                    "region": "us-east-1",
                    "account_id": "987654321098",
                    "role_name": "Admin",
                },
            ],
        },
        "bedrock": {"model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"},
        "codeartifact": {"domain": "my-domain", "repository": "my-repo"},
        "ssm": {
            "databases": [
                {
                    "name": "db1",
                    "instance_id": "i-1234567890abcdef0",
                    "local_port": 5432,
                    "remote_port": 5432,
                },
                {
                    "name": "db2",
                    "instance_id": "i-0987654321fedcba0",
                    "local_port": 3306,
                    "remote_port": 3306,
                },
            ],
            "instances": [
                {"name": "web-server", "instance_id": "i-abcdef1234567890"},
                {"name": "app-server", "instance_id": "i-fedcba0987654321"},
            ],
        },
    }

    # Save config to file
    save_config(test_config)

    # Benchmark loading the config
    result = benchmark(load_config)

    # Verify config was loaded correctly (load_config merges with defaults)
    assert "aws" in result
    assert "bedrock" in result
    assert result["aws"]["region"] == "us-east-1"
    assert len(result["aws"]["sso_profiles"]) == 2


@pytest.mark.slow
@pytest.mark.unit
def test_config_file_saving_performance(benchmark, temp_config_dir, mocker):
    """Test config file saving performance.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of saving configuration files
    to detect regressions in config file serialization and I/O operations.
    """
    # Setup
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create a realistic config
    test_config = {
        "aws": {
            "region": "us-east-1",
            "sso_profiles": [
                {
                    "name": f"profile-{i}",
                    "start_url": f"https://profile{i}.awsapps.com/start",
                    "region": "us-east-1",
                    "account_id": f"{i:012d}",
                    "role_name": "Developer",
                }
                for i in range(10)
            ],
        },
        "bedrock": {"model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"},
        "codeartifact": {"domain": "my-domain", "repository": "my-repo"},
    }

    # Benchmark saving the config
    benchmark(save_config, test_config)

    # Verify config was saved correctly
    assert config_file.exists()
    with open(config_file) as f:
        loaded = json.load(f)
    assert loaded == test_config


@pytest.mark.slow
@pytest.mark.unit
def test_config_nested_key_access_performance(benchmark, temp_config_dir, mocker):
    """Test nested config key access performance.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of accessing deeply nested
    configuration keys to detect regressions in config traversal logic.
    """
    # Setup
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create a deeply nested config
    test_config = {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {
                        "level5": {"target_value": "found"},
                    }
                }
            }
        }
    }
    save_config(test_config)

    # Benchmark accessing nested key
    from cli_tool.core.utils.config_manager import get_config_value

    result = benchmark(get_config_value, "level1.level2.level3.level4.level5.target_value")

    # Verify correct value was retrieved
    assert result == "found"


@pytest.mark.slow
@pytest.mark.unit
def test_git_diff_parsing_performance_small(benchmark, mocker):
    """Test git diff parsing performance with small diffs.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of parsing small git diffs
    to establish baseline performance for typical use cases.
    """
    # Mock subprocess.run to return a small diff
    small_diff = """diff --git a/file.py b/file.py
index 1234567..abcdefg 100644
--- a/file.py
+++ b/file.py
@@ -10,6 +10,7 @@ def function():
     existing_line_1
     existing_line_2
+    new_line
     existing_line_3
     existing_line_4
"""

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = small_diff

    # Benchmark getting staged diff
    result = benchmark(get_staged_diff)

    # Verify diff was retrieved
    assert result == small_diff.strip()
    assert "diff --git" in result


@pytest.mark.slow
@pytest.mark.unit
def test_git_diff_parsing_performance_medium(benchmark, mocker):
    """Test git diff parsing performance with medium diffs.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of parsing medium-sized git diffs
    (50-100 lines) to measure performance with typical code changes.
    """
    # Generate a medium-sized diff (50 lines)
    diff_lines = ["diff --git a/file.py b/file.py", "index 1234567..abcdefg 100644", "--- a/file.py", "+++ b/file.py"]

    # Add 50 lines of changes
    for i in range(50):
        diff_lines.append(f"+    new_line_{i}")

    medium_diff = "\n".join(diff_lines)

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = medium_diff

    # Benchmark getting staged diff
    result = benchmark(get_staged_diff)

    # Verify diff was retrieved
    assert result == medium_diff.strip()
    assert len(result.split("\n")) >= 50


@pytest.mark.slow
@pytest.mark.unit
def test_git_diff_parsing_performance_large(benchmark, mocker):
    """Test git diff parsing performance with large diffs.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of parsing large git diffs
    (200+ lines) to detect performance issues with substantial changes.
    """
    # Generate a large diff (200 lines)
    diff_lines = [
        "diff --git a/large_file.py b/large_file.py",
        "index 1234567..abcdefg 100644",
        "--- a/large_file.py",
        "+++ b/large_file.py",
    ]

    # Add 200 lines of changes
    for i in range(200):
        if i % 3 == 0:
            diff_lines.append(f"+    new_line_{i}")
        elif i % 3 == 1:
            diff_lines.append(f"-    old_line_{i}")
        else:
            diff_lines.append(f"     unchanged_line_{i}")

    large_diff = "\n".join(diff_lines)

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = large_diff

    # Benchmark getting staged diff
    result = benchmark(get_staged_diff)

    # Verify diff was retrieved
    assert result == large_diff.strip()
    assert len(result.split("\n")) >= 200


@pytest.mark.slow
@pytest.mark.unit
def test_git_diff_parsing_performance_multifile(benchmark, mocker):
    """Test git diff parsing performance with multiple files.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of parsing diffs with multiple
    files to measure performance with complex changesets.
    """
    # Generate a diff with 10 files
    diff_parts = []
    for file_num in range(10):
        diff_parts.append(f"diff --git a/file{file_num}.py b/file{file_num}.py")
        diff_parts.append(f"index {file_num:07d}..abcdefg 100644")
        diff_parts.append(f"--- a/file{file_num}.py")
        diff_parts.append(f"+++ b/file{file_num}.py")
        diff_parts.append(f"@@ -10,6 +10,7 @@ def function_{file_num}():")
        for line_num in range(10):
            diff_parts.append(f"+    new_line_{file_num}_{line_num}")

    multifile_diff = "\n".join(diff_parts)

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = multifile_diff

    # Benchmark getting staged diff
    result = benchmark(get_staged_diff)

    # Verify diff was retrieved
    assert result == multifile_diff.strip()
    assert result.count("diff --git") == 10


@pytest.mark.slow
@pytest.mark.integration
def test_large_file_export_performance_json(benchmark, temp_config_dir):
    """Test large file export performance in JSON format.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of exporting large datasets
    to JSON format to detect regressions in serialization performance.
    """
    # Create a large dataset (1000 items)
    large_dataset = [
        {
            "id": f"item-{i:04d}",
            "name": f"Item {i}",
            "description": f"This is a description for item {i}" * 5,
            "value": i * 100,
            "category": f"category-{i % 10}",
            "metadata": {
                "created_at": f"2024-01-{(i % 28) + 1:02d}",
                "updated_at": f"2024-02-{(i % 28) + 1:02d}",
                "tags": [f"tag-{j}" for j in range(5)],
            },
        }
        for i in range(1000)
    ]

    output_file = temp_config_dir / "export.json"

    def export_to_json():
        """Export dataset to JSON file."""
        with open(output_file, "w") as f:
            json.dump(large_dataset, f, indent=2)
        return output_file

    # Benchmark export
    result_file = benchmark(export_to_json)

    # Verify export was successful
    assert result_file.exists()
    with open(result_file) as f:
        loaded = json.load(f)
    assert len(loaded) == 1000


@pytest.mark.slow
@pytest.mark.integration
def test_large_file_export_performance_csv(benchmark, temp_config_dir):
    """Test large file export performance in CSV format.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of exporting large datasets
    to CSV format to detect regressions in CSV serialization.
    """
    import csv

    # Create a large dataset (1000 items)
    large_dataset = [
        {
            "id": f"item-{i:04d}",
            "name": f"Item {i}",
            "description": f"Description for item {i}",
            "value": i * 100,
            "category": f"category-{i % 10}",
        }
        for i in range(1000)
    ]

    output_file = temp_config_dir / "export.csv"

    def export_to_csv():
        """Export dataset to CSV file."""
        with open(output_file, "w", newline="") as f:
            if large_dataset:
                writer = csv.DictWriter(f, fieldnames=large_dataset[0].keys())
                writer.writeheader()
                writer.writerows(large_dataset)
        return output_file

    # Benchmark export
    result_file = benchmark(export_to_csv)

    # Verify export was successful
    assert result_file.exists()
    with open(result_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1000


@pytest.mark.slow
@pytest.mark.integration
def test_large_file_import_performance_json(benchmark, temp_config_dir):
    """Test large file import performance from JSON format.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of importing large JSON files
    to detect regressions in deserialization performance.
    """
    # Create a large JSON file (1000 items)
    large_dataset = [
        {
            "id": f"item-{i:04d}",
            "name": f"Item {i}",
            "description": f"This is a description for item {i}" * 5,
            "value": i * 100,
            "category": f"category-{i % 10}",
        }
        for i in range(1000)
    ]

    input_file = temp_config_dir / "import.json"
    with open(input_file, "w") as f:
        json.dump(large_dataset, f, indent=2)

    def import_from_json():
        """Import dataset from JSON file."""
        with open(input_file) as f:
            return json.load(f)

    # Benchmark import
    result = benchmark(import_from_json)

    # Verify import was successful
    assert len(result) == 1000
    assert result[0]["id"] == "item-0000"


@pytest.mark.slow
@pytest.mark.integration
def test_config_roundtrip_performance(benchmark, temp_config_dir, mocker):
    """Test config export/import round-trip performance.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of a complete config export
    and import cycle to detect regressions in round-trip operations.
    """
    # Setup
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create a realistic config
    test_config = {
        "aws": {
            "region": "us-east-1",
            "sso_profiles": [
                {
                    "name": f"profile-{i}",
                    "start_url": f"https://profile{i}.awsapps.com/start",
                    "region": "us-east-1",
                    "account_id": f"{i:012d}",
                    "role_name": "Developer",
                }
                for i in range(5)
            ],
        },
        "bedrock": {"model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"},
        "codeartifact": {"domain": "my-domain", "repository": "my-repo"},
    }

    def config_roundtrip():
        """Perform config save and load cycle."""
        save_config(test_config)
        return load_config()

    # Benchmark round-trip
    result = benchmark(config_roundtrip)

    # Verify round-trip preserved core data (load_config merges with defaults)
    assert "aws" in result
    assert "bedrock" in result
    assert result["aws"]["region"] == "us-east-1"
    assert len(result["aws"]["sso_profiles"]) == 5


@pytest.mark.slow
@pytest.mark.unit
def test_config_file_loading_with_large_config(benchmark, temp_config_dir, mocker):
    """Test config file loading performance with large configuration.

    Validates: Requirements 17.5, 21.1

    This test benchmarks the performance of loading large configuration
    files with many nested structures and arrays.
    """
    # Setup
    config_file = temp_config_dir / "config.json"
    mocker.patch("cli_tool.core.utils.config_manager.get_config_file", return_value=config_file)

    # Create a large config with many profiles and settings
    test_config = {
        "aws": {
            "region": "us-east-1",
            "sso_profiles": [
                {
                    "name": f"profile-{i}",
                    "start_url": f"https://profile{i}.awsapps.com/start",
                    "region": "us-east-1",
                    "account_id": f"{i:012d}",
                    "role_name": "Developer",
                    "permissions": [f"permission-{j}" for j in range(10)],
                }
                for i in range(50)
            ],
        },
        "bedrock": {"model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"},
        "codeartifact": {"domain": "my-domain", "repository": "my-repo"},
        "ssm": {
            "databases": [
                {
                    "name": f"db-{i}",
                    "instance_id": f"i-{i:016x}",
                    "local_port": 5432 + i,
                    "remote_port": 5432,
                }
                for i in range(20)
            ],
            "instances": [{"name": f"instance-{i}", "instance_id": f"i-{i:016x}"} for i in range(30)],
        },
    }

    # Save config to file
    save_config(test_config)

    # Benchmark loading the large config
    result = benchmark(load_config)

    # Verify config was loaded correctly
    assert len(result["aws"]["sso_profiles"]) == 50
    assert len(result["ssm"]["databases"]) == 20
    assert len(result["ssm"]["instances"]) == 30
