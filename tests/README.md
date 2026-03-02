# Devo CLI Testing Guide

## Overview

This guide provides comprehensive documentation for testing the Devo CLI project. The testing strategy ensures reliability, maintainability, and cross-platform compatibility through a well-organized test suite with clear patterns and best practices.

**Quick Reference:**
```bash
# Run all tests (fast, excludes slow tests)
pytest

# Run with coverage report
pytest --cov=cli_tool --cov-report=html

# Run specific category
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only

# Run in parallel (faster)
pytest -n auto

# Run only failed tests from last run
pytest --lf

# Show test execution time
pytest --durations=10
```

**Test Statistics:**
- Total tests: 614 (30 slow tests skipped by default)
- Execution time: ~29 seconds
- Test categories: unit, integration, platform, slow
- Coverage target: 75% minimum

## Table of Contents

- [Test Directory Structure](#test-directory-structure)
- [Test Categories](#test-categories)
- [Running Tests](#running-tests)
- [Mocking Patterns](#mocking-patterns)
- [Fixture Usage](#fixture-usage)
- [Test Data Management](#test-data-management)
- [Writing New Tests](#writing-new-tests)
- [Troubleshooting](#troubleshooting)
- [CI/CD Integration](#cicd-integration)
- [Best Practices](#best-practices)
- [Common Test Patterns](#common-test-patterns)
- [Additional Resources](#additional-resources)

## Test Directory Structure

The test suite mirrors the source code structure for easy navigation:

```
tests/
├── conftest.py                          # Global fixtures and configuration
├── fixtures/                            # Test data files
│   ├── git_diffs/                       # Git diff samples
│   ├── aws_responses/                   # AWS API response samples
│   ├── config_files/                    # Configuration file samples
│   └── cli_outputs/                     # Expected CLI output samples
│
├── test_commands/                       # CLI command tests (integration)
│   ├── test_commit/                     # Commit command tests
│   ├── test_code_reviewer/              # Code review command tests
│   ├── test_config_cmd/                 # Config command tests
│   ├── test_dynamodb/                   # DynamoDB command tests
│   └── test_aws_login/                  # AWS login command tests
│
├── test_core/                           # Core business logic tests (unit)
│   ├── test_agents/                     # AI agent tests
│   └── test_utils/                      # Utility function tests
│
├── test_platform/                       # Platform-specific tests
│   ├── test_windows.py
│   ├── test_macos.py
│   └── test_linux.py
│
└── README.md                            # This file
```


## Test Categories

Tests are organized into categories using pytest markers:

### Unit Tests (`@pytest.mark.unit`)

Test core business logic in isolation without external dependencies.

**Characteristics:**
- Test single functions or classes
- Mock all external dependencies (AWS, Git, file system)
- No Click or Rich dependencies in tested code
- Fast execution (<1 second per test)
- Target: 80% coverage for core/ modules

**Example:**
```python
@pytest.mark.unit
def test_config_manager_load_default(temp_config_dir, mocker):
  """Test that load_config creates default config if file doesn't exist."""
  config_file = temp_config_dir / 'config.json'
  mocker.patch('cli_tool.core.utils.config_manager.CONFIG_FILE', config_file)

  config = load_config()

  assert isinstance(config, dict)
  assert config_file.exists()
```

### Integration Tests (`@pytest.mark.integration`)

Test CLI commands end-to-end with mocked external services.

**Characteristics:**
- Use Click's CliRunner to simulate command execution
- Mock external services (AWS, Git)
- Verify exit codes and output
- Test interactive prompts
- Target: 70% coverage for commands/ modules

**Example:**
```python
@pytest.mark.integration
def test_commit_command_success(cli_runner, mocker):
  """Test commit command generates and applies commit message."""
  mock_run = mocker.patch('subprocess.run')
  mock_run.return_value.returncode = 0
  mock_run.return_value.stdout = "diff --git a/file.py b/file.py\n+new line"

  result = cli_runner.invoke(commit, input='y\n')

  assert result.exit_code == 0
  assert 'feat' in result.output or 'fix' in result.output
```

### Platform Tests (`@pytest.mark.platform`)

Test platform-specific behavior for Windows, macOS, and Linux.

**Characteristics:**
- Use pytest.mark.skipif for conditional execution
- Test path separators, shell completion, binary formats
- Run on specific platforms only

**Example:**
```python
@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_path_handling():
  """Test Windows path separator handling."""
  from pathlib import Path
  config_path = Path("C:/Users/Developer/.devo/config.json")
  assert isinstance(config_path, Path)
```

### Slow Tests (`@pytest.mark.slow`)

Performance tests and benchmarks that take longer to execute.

**Characteristics:**
- Skipped by default in local development
- Run in CI pipeline
- Use pytest-benchmark for timing
- Test performance characteristics

**Example:**
```python
@pytest.mark.slow
def test_cli_startup_time(benchmark, cli_runner):
  """Test CLI startup time is under 2 seconds."""
  result = benchmark(cli_runner.invoke, cli, ['--version'])
  assert result.exit_code == 0
```


## Running Tests

### Local Development

**Run all tests (excluding slow tests):**
```bash
pytest
```

**Run specific test categories:**
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Platform-specific tests
pytest -m platform

# Include slow tests
pytest -m slow

# Run unit and integration tests (exclude platform and slow)
pytest -m "unit or integration"

# Run everything except slow tests (default)
pytest -m "not slow"
```

**Run specific test files or directories:**
```bash
# Run all tests in a directory
pytest tests/test_commands/test_commit/

# Run specific test file
pytest tests/test_commands/test_commit/test_commit_generation.py

# Run specific test function
pytest tests/test_commands/test_commit/test_commit_generation.py::test_commit_with_staged_changes

# Run all tests for a specific command
pytest tests/test_commands/test_dynamodb/
```

**Run with coverage:**
```bash
# Generate terminal report
pytest --cov=cli_tool --cov-report=term-missing

# Generate HTML report
pytest --cov=cli_tool --cov-report=html
# Open htmlcov/index.html in browser
```

**Run in parallel (faster):**
```bash
# Use all available CPU cores
pytest -n auto

# Use specific number of workers
pytest -n 4
```

**Run specific test file or function:**
```bash
# Run specific file
pytest tests/test_commands/test_commit/test_commit_generation.py

# Run specific test function
pytest tests/test_commands/test_commit/test_commit_generation.py::test_commit_with_staged_changes

# Run tests matching pattern
pytest -k "commit"
```

**Show test execution time:**
```bash
# Show 10 slowest tests
pytest --durations=10

# Show all test durations
pytest --durations=0
```

### CI/CD Pipeline

Tests run automatically on:
- Pull requests to main/develop branches
- Pushes to main/develop branches

**CI Configuration:**
- Runs on: Windows, macOS, Linux
- Python versions: 3.12, 3.13
- Coverage threshold: 75% minimum
- All test categories included (including slow tests)


## Mocking Patterns

### AWS Services with moto

Use the `moto` library to mock AWS services at the HTTP interception level.

**DynamoDB Example:**
```python
from moto import mock_aws
import boto3

@pytest.fixture
def mock_dynamodb_table():
  """Provide mocked DynamoDB table with test data."""
  with mock_aws():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
      TableName='test-table',
      KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
      AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
      BillingMode='PAY_PER_REQUEST'
    )
    # Add test data
    table.put_item(Item={'id': 'item-1', 'name': 'Test Item'})
    yield table

@pytest.mark.integration
def test_dynamodb_export(cli_runner, mock_dynamodb_table):
  """Test DynamoDB export with mocked table."""
  result = cli_runner.invoke(export_table, ['test-table', '--format', 'json'])
  assert result.exit_code == 0
```

**AWS Bedrock (AI) Example:**
```python
@pytest.fixture
def mock_bedrock_client(mocker):
  """Provide mocked Bedrock client for AI responses."""
  mock_client = mocker.MagicMock()
  mock_client.invoke_model.return_value = {
    'body': mocker.MagicMock(read=lambda: b'{"response": "mocked AI response"}')
  }
  mocker.patch('boto3.client', return_value=mock_client)
  return mock_client

@pytest.mark.unit
def test_base_agent_query(mock_bedrock_client):
  """Test BaseAgent query with mocked Bedrock."""
  agent = BaseAgent()
  response = agent.query("test prompt")
  assert response is not None
```

**When to use moto:**
- DynamoDB operations
- IAM operations
- EventBridge operations
- SSM operations
- Any AWS service with moto support

**When NOT to use moto:**
- Bedrock (limited support) → use pytest-mock instead
- Non-AWS services → use pytest-mock


### Git Operations with pytest-mock

Mock git operations to avoid modifying real repositories.

**Subprocess Approach (cli_tool/core/utils/git_utils.py):**
```python
@pytest.mark.unit
def test_git_diff_command(mocker):
  """Test git diff command execution."""
  mock_run = mocker.patch('subprocess.run')
  mock_run.return_value.returncode = 0
  mock_run.return_value.stdout = "diff --git a/file.py b/file.py\n+new line"

  from cli_tool.core.utils.git_utils import get_git_diff
  diff = get_git_diff()

  assert "new line" in diff
  mock_run.assert_called_once()
```

**GitPython Approach (cli_tool/commands/code_reviewer/core/git_utils.py):**
```python
@pytest.mark.unit
def test_git_repo_operations(mocker):
  """Test GitPython repository operations."""
  mock_repo = mocker.MagicMock()
  mock_repo.git.diff.return_value = "diff content"
  mock_repo.is_dirty.return_value = True
  mocker.patch('git.Repo', return_value=mock_repo)

  from cli_tool.commands.code_reviewer.core.git_utils import get_staged_diff
  diff = get_staged_diff()

  assert diff == "diff content"
  mock_repo.git.diff.assert_called_once()
```

**Verifying Git Commands:**
```python
@pytest.mark.integration
def test_commit_executes_git_commands(cli_runner, mocker):
  """Test that commit command executes correct git commands."""
  mock_run = mocker.patch('subprocess.run')
  mock_run.return_value.returncode = 0
  mock_run.return_value.stdout = "diff content"

  result = cli_runner.invoke(commit, input='y\n')

  # Verify git commands were called
  calls = [str(call) for call in mock_run.call_args_list]
  assert any('git diff' in str(call) for call in calls)
  assert any('git commit' in str(call) for call in calls)
```


### File System Operations

Use pytest's `tmp_path` fixture for temporary file operations.

**Configuration File Testing:**
```python
@pytest.mark.unit
def test_config_save(temp_config_dir, mocker):
  """Test configuration file saving."""
  config_file = temp_config_dir / 'config.json'
  mocker.patch('cli_tool.core.utils.config_manager.CONFIG_FILE', config_file)

  test_config = {"aws": {"region": "us-east-1"}}
  save_config(test_config)

  assert config_file.exists()
  import json
  with open(config_file) as f:
    loaded = json.load(f)
  assert loaded == test_config
```

**Mocking File Operations:**
```python
@pytest.mark.unit
def test_hosts_file_modification(mocker):
  """Test /etc/hosts file modification (mocked)."""
  mock_open = mocker.mock_open(read_data="127.0.0.1 localhost\n")
  mocker.patch('builtins.open', mock_open)

  from cli_tool.commands.ssm.utils.hosts_manager import add_host_entry
  add_host_entry("10.0.0.1", "database.local")

  # Verify file was opened for writing
  mock_open.assert_called()
```

### unittest.mock vs pytest-mock

**Use pytest-mock (recommended):**
- Cleaner syntax with `mocker` fixture
- Automatic cleanup after test
- Better integration with pytest

**Use unittest.mock:**
- When pytest-mock is not available
- For compatibility with existing code

**Example comparison:**
```python
# pytest-mock (recommended)
def test_with_pytest_mock(mocker):
  mock_func = mocker.patch('module.function')
  mock_func.return_value = "mocked"

# unittest.mock
from unittest.mock import patch

def test_with_unittest_mock():
  with patch('module.function') as mock_func:
    mock_func.return_value = "mocked"
```


## Fixture Usage

### Global Fixtures (tests/conftest.py)

Common fixtures available to all tests:

**cli_runner** - Click CLI testing:
```python
def test_command(cli_runner):
  """Test CLI command execution."""
  result = cli_runner.invoke(my_command, ['--flag', 'value'])
  assert result.exit_code == 0
```

**fixtures_dir** - Access test data:
```python
def test_with_fixture_data(fixtures_dir):
  """Test using fixture data files."""
  import json
  with open(fixtures_dir / 'git_diffs' / 'simple_change.json') as f:
    data = json.load(f)
  assert 'diff' in data
```

**temp_config_dir** - Temporary config directory:
```python
def test_config_operations(temp_config_dir, mocker):
  """Test config operations with temporary directory."""
  config_file = temp_config_dir / 'config.json'
  mocker.patch('cli_tool.core.utils.config_manager.CONFIG_FILE', config_file)
  # Test config operations
```

**mock_dynamodb_client** - Mocked DynamoDB:
```python
def test_dynamodb_operation(mock_dynamodb_client):
  """Test DynamoDB operation with mocked client."""
  # Client is already mocked and ready to use
  response = mock_dynamodb_client.list_tables()
  assert 'TableNames' in response
```

**mock_bedrock_client** - Mocked Bedrock AI:
```python
def test_ai_operation(mock_bedrock_client):
  """Test AI operation with mocked Bedrock."""
  # Client is already mocked with sample response
  agent = BaseAgent()
  response = agent.query("test prompt")
  assert response is not None
```

### Fixture Scoping

Control fixture lifecycle with scope parameter:

**Function scope (default)** - Created/destroyed for each test:
```python
@pytest.fixture
def function_scoped_fixture():
  """Created fresh for each test."""
  return {"data": "value"}
```

**Module scope** - Shared across tests in same file:
```python
@pytest.fixture(scope="module")
def module_scoped_fixture():
  """Created once per test module."""
  # Expensive setup
  return expensive_resource
```

**Session scope** - Shared across entire test session:
```python
@pytest.fixture(scope="session")
def session_scoped_fixture():
  """Created once for entire test run."""
  # Very expensive setup
  return very_expensive_resource
```


### Parametrized Fixtures

Test multiple scenarios with one test function:

```python
@pytest.fixture(params=["json", "csv", "jsonl"])
def export_format(request):
  """Provide different export formats."""
  return request.param

def test_export_formats(export_format):
  """Test export with different formats."""
  # Test runs 3 times, once for each format
  assert export_format in ["json", "csv", "jsonl"]
```

### Fixture Composition

Combine fixtures to build complex test scenarios:

```python
@pytest.fixture
def mock_aws_environment(mock_dynamodb_client, mock_bedrock_client):
  """Provide complete mocked AWS environment."""
  return {
    'dynamodb': mock_dynamodb_client,
    'bedrock': mock_bedrock_client
  }

def test_with_full_aws_mock(mock_aws_environment):
  """Test with all AWS services mocked."""
  # Both DynamoDB and Bedrock are available
  assert 'dynamodb' in mock_aws_environment
  assert 'bedrock' in mock_aws_environment
```

### Fixture Cleanup

Fixtures automatically clean up using yield:

```python
@pytest.fixture
def resource_with_cleanup():
  """Fixture with setup and teardown."""
  # Setup
  resource = create_resource()

  yield resource  # Provide to test

  # Teardown (runs after test)
  resource.cleanup()
```


## Test Data Management

### Fixture Directory Structure

Test data is organized in `tests/fixtures/`:

```
tests/fixtures/
├── git_diffs/           # Git diff samples
│   ├── simple_change.json
│   ├── multi_file_change.json
│   ├── large_diff.json
│   └── security_issue.json
├── aws_responses/       # AWS API response samples
│   ├── dynamodb_scan_response.json
│   ├── bedrock_commit_message.json
│   └── bedrock_code_review.json
├── config_files/        # Configuration samples
│   ├── minimal_config.json
│   ├── full_config.json
│   └── legacy_config_v1.json
└── cli_outputs/         # Expected CLI outputs
    ├── commit_message_examples.json
    └── code_review_examples.json
```

### Loading Fixture Data

**Using fixtures_dir fixture:**
```python
def test_with_fixture_data(fixtures_dir):
  """Test using fixture data from JSON file."""
  import json
  fixture_path = fixtures_dir / 'git_diffs' / 'simple_change.json'

  with open(fixture_path) as f:
    data = json.load(f)

  assert 'diff' in data
  assert 'file' in data
```

**Creating helper functions:**
```python
def load_fixture_json(fixtures_dir, relative_path):
  """Helper to load JSON fixture files."""
  import json
  fixture_path = fixtures_dir / relative_path
  with open(fixture_path) as f:
    return json.load(f)

def test_with_helper(fixtures_dir):
  """Test using fixture helper function."""
  data = load_fixture_json(fixtures_dir, 'git_diffs/simple_change.json')
  assert data is not None
```

### Creating New Fixture Files

**Git Diff Fixture Format:**
```json
{
  "file": "cli_tool/commands/commit/core/generator.py",
  "diff": "diff --git a/file.py b/file.py\nindex 1234567..abcdefg 100644\n--- a/file.py\n+++ b/file.py\n@@ -10,6 +10,7 @@\n+    # New line\n",
  "staged": true,
  "binary": false
}
```

**AWS Response Fixture Format:**
```json
{
  "Items": [
    {
      "id": {"S": "item-1"},
      "name": {"S": "Test Item"},
      "created_at": {"N": "1234567890"}
    }
  ],
  "Count": 1,
  "ScannedCount": 1
}
```

**Config File Fixture Format:**
```json
{
  "aws": {
    "region": "us-east-1",
    "sso_profiles": [
      {
        "name": "dev",
        "start_url": "https://dev.awsapps.com/start",
        "account_id": "123456789012"
      }
    ]
  }
}
```


### Fixture File Naming Conventions

- Use descriptive names: `simple_change.json`, not `test1.json`
- Group related fixtures in subdirectories
- Use `.json` extension for structured data
- Use `.txt` for plain text samples
- Include version in filename for legacy data: `legacy_config_v1.json`

### Best Practices

1. **Keep fixtures realistic** - Use data that reflects actual usage
2. **Keep fixtures minimal** - Only include necessary data
3. **Document complex fixtures** - Add comments in JSON where needed
4. **Version control fixtures** - Commit all fixture files
5. **Avoid hardcoding** - Load from fixtures instead of inline data


## Writing New Tests

### Test Naming Conventions

**Test files:** `test_<module_name>.py`
```
test_config_manager.py
test_commit_generation.py
test_dynamodb_export.py
```

**Test functions:** `test_<what_is_being_tested>`
```python
def test_config_load_creates_default():
def test_commit_with_staged_changes():
def test_dynamodb_export_json_format():
```

**Test classes (optional):** `Test<FeatureName>`
```python
class TestConfigManager:
  def test_load_config(self):
  def test_save_config(self):
```

### Test Structure (Arrange-Act-Assert)

```python
def test_example(cli_runner, mocker):
  """Test description explaining what is being tested."""
  # Arrange - Set up test data and mocks
  mock_func = mocker.patch('module.function')
  mock_func.return_value = "expected"

  # Act - Execute the code being tested
  result = cli_runner.invoke(command, ['--flag'])

  # Assert - Verify the results
  assert result.exit_code == 0
  assert "expected" in result.output
```

### Unit Test Template

```python
import pytest
from cli_tool.core.utils.module import function_to_test

@pytest.mark.unit
def test_function_success_case(mocker):
  """Test function with valid input."""
  # Arrange
  mock_dependency = mocker.patch('module.dependency')
  mock_dependency.return_value = "mocked"

  # Act
  result = function_to_test("input")

  # Assert
  assert result == "expected"
  mock_dependency.assert_called_once_with("input")

@pytest.mark.unit
def test_function_error_case(mocker):
  """Test function handles errors gracefully."""
  # Arrange
  mock_dependency = mocker.patch('module.dependency')
  mock_dependency.side_effect = Exception("error")

  # Act & Assert
  with pytest.raises(Exception, match="error"):
    function_to_test("input")
```

### Integration Test Template

```python
import pytest
from click.testing import CliRunner
from cli_tool.commands.feature import command

@pytest.mark.integration
def test_command_success(cli_runner, mocker):
  """Test command executes successfully."""
  # Arrange
  mock_service = mocker.patch('cli_tool.commands.feature.core.service.call')
  mock_service.return_value = {"status": "success"}

  # Act
  result = cli_runner.invoke(command, ['--option', 'value'])

  # Assert
  assert result.exit_code == 0
  assert "success" in result.output.lower()

@pytest.mark.integration
def test_command_with_interactive_prompt(cli_runner, mocker):
  """Test command with user input."""
  # Arrange
  mock_service = mocker.patch('cli_tool.commands.feature.core.service.call')
  mock_service.return_value = {"status": "success"}

  # Act - Provide input to prompt
  result = cli_runner.invoke(command, input='y\n')

  # Assert
  assert result.exit_code == 0
```


### Platform-Specific Test Template

```python
import sys
import pytest

@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_specific_feature():
  """Test Windows-specific behavior."""
  from pathlib import Path
  # Test Windows-specific code
  assert sys.platform == "win32"

@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_macos_specific_feature():
  """Test macOS-specific behavior."""
  assert sys.platform == "darwin"

@pytest.mark.platform
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
def test_linux_specific_feature():
  """Test Linux-specific behavior."""
  assert sys.platform == "linux"
```

### Parametrized Test Template

```python
import pytest

@pytest.mark.unit
@pytest.mark.parametrize("input,expected", [
  ("value1", "result1"),
  ("value2", "result2"),
  ("value3", "result3"),
])
def test_with_multiple_inputs(input, expected):
  """Test function with various inputs."""
  result = function_to_test(input)
  assert result == expected

@pytest.mark.integration
@pytest.mark.parametrize("format", ["json", "csv", "jsonl", "tsv"])
def test_export_formats(cli_runner, format):
  """Test export command with different formats."""
  result = cli_runner.invoke(export_command, ['--format', format])
  assert result.exit_code == 0
```

### Testing Error Conditions

```python
@pytest.mark.unit
def test_function_raises_error():
  """Test function raises appropriate error."""
  with pytest.raises(ValueError, match="invalid input"):
    function_to_test("invalid")

@pytest.mark.integration
def test_command_handles_missing_argument(cli_runner):
  """Test command with missing required argument."""
  result = cli_runner.invoke(command)
  assert result.exit_code != 0
  assert "required" in result.output.lower() or "missing" in result.output.lower()
```


## Troubleshooting

### Common Issues and Solutions

#### ImportError: No module named 'pytest'

**Problem:** Test dependencies not installed.

**Solution:**
```bash
pip install -r requirements.txt
pip install -e .
```

#### ImportError: No module named 'cli_tool'

**Problem:** Package not installed in editable mode.

**Solution:**
```bash
pip install -e .
```

#### Tests fail with AWS credential errors

**Problem:** Moto decorators not applied or mocks not activated.

**Solution:**
- Verify `@mock_aws` decorator is applied
- Check that mocks are created inside `with mock_aws():` context
- Ensure boto3 client is created after mock activation

```python
# Correct
with mock_aws():
  client = boto3.client('dynamodb', region_name='us-east-1')
  # Use client

# Incorrect
client = boto3.client('dynamodb', region_name='us-east-1')
with mock_aws():
  # Client was created before mock activation
```

#### DynamoDB mock table not found

**Problem:** Table created in fixture but not accessible in test.

**Solution:**
- Ensure the mock_aws context is active when creating the table
- Create tables within the test function or use a fixture with proper scope
- Verify the table name matches exactly

```python
@pytest.mark.integration
def test_with_dynamodb_table(cli_runner):
  """Test with properly scoped DynamoDB table."""
  with mock_aws():
    # Create table in same context as test
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
      TableName='test-table',
      KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
      AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
      BillingMode='PAY_PER_REQUEST'
    )

    # Run test
    result = cli_runner.invoke(command, ['test-table'])
    assert result.exit_code == 0
```

#### Tests modify real git repository

**Problem:** Git operations not mocked.

**Solution:**
- Mock `subprocess.run` for subprocess-based git operations
- Mock `git.Repo` for GitPython-based operations

```python
# Mock subprocess git commands
mock_run = mocker.patch('subprocess.run')
mock_run.return_value.returncode = 0

# Mock GitPython
mock_repo = mocker.MagicMock()
mocker.patch('git.Repo', return_value=mock_repo)
```

#### Tests create permanent files

**Problem:** File operations not using temporary directories.

**Solution:**
- Use `temp_config_dir` fixture
- Use pytest's `tmp_path` fixture
- Mock file operations with `mocker.mock_open()`

```python
def test_with_temp_dir(temp_config_dir, mocker):
  config_file = temp_config_dir / 'config.json'
  mocker.patch('cli_tool.core.utils.config_manager.CONFIG_FILE', config_file)
  # File operations now use temporary directory
```


#### Coverage below threshold

**Problem:** Not enough code is covered by tests.

**Solution:**
1. Generate HTML coverage report to identify uncovered code:
```bash
pytest --cov=cli_tool --cov-report=html
# Open htmlcov/index.html
```

2. Add tests for uncovered code paths
3. Verify tests actually execute the code (check mocks aren't preventing execution)

#### Tests run slowly

**Problem:** Tests taking too long to execute.

**Solution:**
1. Profile slow tests:
```bash
pytest --durations=10
```

2. Verify all external calls are mocked
3. Use parallel execution:
```bash
pytest -n auto
```

4. Mark slow tests with `@pytest.mark.slow` to skip by default

#### Test execution tips for faster development

**Run only changed tests:**
```bash
# Run tests for specific module
pytest tests/test_commands/test_commit/

# Run tests matching a pattern
pytest -k "commit"

# Run only failed tests from last run
pytest --lf

# Run failed tests first, then others
pytest --ff
```

**Skip slow tests during development:**
```bash
# Default behavior (slow tests already skipped)
pytest

# Explicitly skip slow tests
pytest -m "not slow"

# Run only slow tests
pytest -m slow
```

**Use verbose output for debugging:**
```bash
# Show test names as they run
pytest -v

# Show full output (no capture)
pytest -s

# Show local variables on failure
pytest -l
```

#### Intermittent test failures

**Problem:** Tests pass sometimes, fail other times.

**Solution:**
- Check for test isolation issues (tests affecting each other)
- Verify fixtures are function-scoped
- Look for shared state between tests
- Check for race conditions in parallel execution

```python
# Bad - shared state
shared_data = []

def test_one():
  shared_data.append(1)  # Affects other tests

# Good - isolated state
def test_one():
  local_data = []
  local_data.append(1)  # Only affects this test
```

#### PytestUnknownMarkWarning

**Problem:** Custom markers not registered.

**Solution:**
- Verify markers are registered in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "platform: Platform-specific tests",
    "slow: Slow tests",
]
```

#### FileNotFoundError when loading fixtures

**Problem:** Fixture file path incorrect or file doesn't exist.

**Solution:**
- Use `fixtures_dir` fixture for correct path resolution
- Verify fixture file exists in `tests/fixtures/`
- Check file path is relative to fixtures directory

```python
# Correct
def test_with_fixture(fixtures_dir):
  path = fixtures_dir / 'git_diffs' / 'simple_change.json'

# Incorrect
def test_with_fixture():
  path = 'fixtures/git_diffs/simple_change.json'  # Wrong base path
```


## CI/CD Integration

### GitHub Actions Workflow

Tests run automatically in CI with the following configuration:

**Platforms:**
- Ubuntu (Linux)
- Windows
- macOS

**Python Versions:**
- 3.12 (minimum required)
- 3.13 (latest stable)

**Test Execution:**
- All test categories (including slow tests)
- Coverage measurement with 75% minimum threshold
- Parallel execution for faster results

### Coverage Reporting

Coverage reports are:
- Generated for each platform/Python combination
- Uploaded to Codecov for visualization
- Posted as comments on pull requests
- Used to enforce coverage thresholds

### Pre-commit Hooks

Pre-commit hooks automatically run tests and linters before commits to catch issues early.

**Setup:**
```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Install commit-msg hook for commitizen
pre-commit install --hook-type commit-msg
```

**What runs on commit:**
1. **Code Quality Checks:**
   - Check for large files
   - Check TOML syntax
   - Remove trailing whitespace
   - Check for case conflicts
   - Check for illegal Windows filenames
   - Check for merge conflicts
   - Detect destroyed symlinks
   - Detect private keys
   - Detect AWS credentials
   - Enforce branch naming conventions

2. **Code Formatting:**
   - Black (Python code formatter)
   - isort (import sorting)

3. **Linting:**
   - flake8 (style guide enforcement)

4. **Testing:**
   - Unit tests (`pytest -m unit`)
   - Runs with short traceback (`--tb=short`)
   - Stops on first failure (`-x`)

5. **Commit Message:**
   - Commitizen (conventional commit format validation)

**Skipping hooks (when necessary):**
```bash
# Skip all hooks
git commit --no-verify -m "message"

# Skip specific hook
SKIP=pytest-unit git commit -m "message"

# Skip multiple hooks
SKIP=pytest-unit,flake8 git commit -m "message"
```

**Running hooks manually:**
```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run pytest-unit

# Run on staged files only
pre-commit run
```

**Updating hooks:**
```bash
# Update to latest versions
pre-commit autoupdate
```

**Configuration (.pre-commit-config.yaml):**

The project includes the following pre-commit hooks:

```yaml
repos:
  # Standard pre-commit hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-added-large-files
      - id: check-toml
      - id: trailing-whitespace
      - id: check-case-conflict
      - id: check-illegal-windows-names
      - id: check-merge-conflict
      - id: destroyed-symlinks
      - id: detect-private-key
      - id: forbid-submodules
      - id: detect-aws-credentials
        args: [ --allow-missing-credentials ]
      - id: no-commit-to-branch
        args: ['--branch','', '--pattern', '^(?!(feature/|main|production|release/|release-candidate/|hotfix/|poc/|backup/)).*']

  # Code formatting
  - repo: https://github.com/psf/black
    rev: 25.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 6.0.1
    hooks:
      - id: isort

  # Linting
  - repo: https://github.com/pycqa/flake8
    rev: 7.3.0
    hooks:
      - id: flake8

  # Commit message validation
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.8.2
    hooks:
      - id: commitizen
        stages: [commit-msg]

  # Unit tests
  - repo: local
    hooks:
      - id: pytest-unit
        name: Run unit tests
        entry: pytest -m unit --tb=short -x
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

**Best Practices:**

1. **Run hooks before pushing** - Catch issues locally before CI
2. **Don't skip hooks without reason** - They're there to help
3. **Fix issues, don't skip** - Address the root cause
4. **Keep hooks fast** - Only unit tests run (not integration/slow tests)
5. **Update regularly** - Run `pre-commit autoupdate` periodically

**Troubleshooting:**

**Hook fails with "command not found":**
- Ensure dependencies are installed: `pip install -r requirements.txt`
- Ensure package is installed: `pip install -e .`

**Unit tests fail:**
- Run tests manually to see full output: `pytest -m unit -v`
- Fix failing tests before committing
- If tests are broken in main branch, skip temporarily: `SKIP=pytest-unit git commit -m "message"`

**Hooks take too long:**
- Only unit tests run (fast, <10 seconds typically)
- Integration and slow tests only run in CI
- Consider running `pre-commit run` before staging to catch issues early

**Black/isort conflicts:**
- Both tools are configured to work together
- If conflicts occur, run both manually: `black . && isort .`
- Commit the formatted code

### Local CI Simulation

Test locally with same configuration as CI:

```bash
# Run tests for all platforms (if on that platform)
pytest --cov=cli_tool --cov-report=term-missing --cov-fail-under=75

# Run with multiple Python versions (using tox)
tox
```


## Best Practices

### General Guidelines

1. **Write tests first** - Consider TDD for new features
2. **Test behavior, not implementation** - Focus on what code does, not how
3. **Keep tests simple** - One concept per test
4. **Use descriptive names** - Test name should explain what is tested
5. **Mock external dependencies** - Tests should be fast and isolated
6. **Avoid test interdependencies** - Each test should run independently
7. **Use fixtures for setup** - Don't repeat setup code
8. **Test edge cases** - Empty inputs, boundary values, error conditions
9. **Maintain test code quality** - Same standards as production code
10. **Update tests with code changes** - Keep tests in sync with implementation

### Lessons Learned

**Mock Scope Management:**
- Always create AWS resources (tables, clients) within the same `mock_aws()` context as the test
- Use context managers (`with mock_aws():`) rather than decorators for better control
- Verify mocks are active before creating boto3 clients

**Fixture Organization:**
- Keep fixtures close to where they're used (command-specific fixtures in command test directories)
- Use function scope by default to ensure test isolation
- Only use module/session scope for expensive, read-only resources

**Test Data Management:**
- Store complex test data in JSON files in `tests/fixtures/`
- Use the `fixtures_dir` fixture for consistent path resolution
- Keep fixture data realistic but minimal

**CLI Testing:**
- Use `CliRunner` for all CLI command tests
- Provide input to interactive prompts using `input='y\n'` parameter
- Test both success and error exit codes
- Verify error messages are user-friendly

**Performance:**
- Mock all external calls (AWS, Git, file system, network)
- Use parallel execution (`pytest -n auto`) for faster test runs
- Mark slow tests with `@pytest.mark.slow` to skip during development
- Profile tests regularly (`pytest --durations=10`) to identify bottlenecks

### Code Coverage Goals

- **Core business logic (cli_tool/core/):** 80% minimum
- **CLI commands (cli_tool/commands/):** 70% minimum
- **Overall project:** 75% minimum

**Current Status (as of 2025-01-30):**
- Total tests: 614 tests (30 slow tests skipped by default)
- Test execution time: ~29 seconds
- Overall coverage: 42% (work in progress)
- Core modules: Varies by module (config_manager: 69%, git_utils: 100%, base_agent: 74%)
- Command modules: Varies by command (commit: 98%, codeartifact: 99%, upgrade: 95%)

**Note:** The test infrastructure is complete and functional. Coverage will improve as more tests are added for remaining modules.

### Test Performance

- **Individual tests:** <5 seconds
- **Full test suite:** <60 seconds
- **Use parallel execution:** `pytest -n auto`
- **Mark slow tests:** `@pytest.mark.slow`

### Documentation

- **Docstrings:** Every test should have a clear docstring
- **Comments:** Explain complex test logic
- **Examples:** Provide examples in this README
- **Updates:** Keep documentation current with changes

## Common Test Patterns

### Testing CLI Commands with Multiple Options

When testing commands with various option combinations:

```python
@pytest.mark.integration
@pytest.mark.parametrize("options,expected", [
  (["--format", "json"], "json"),
  (["--format", "csv"], "csv"),
  (["-f", "jsonl"], "jsonl"),
])
def test_export_with_format_options(cli_runner, mock_dynamodb_table, options, expected):
  """Test export command with different format options."""
  result = cli_runner.invoke(export_table, ["test-table"] + options)
  assert result.exit_code == 0
  assert expected in result.output.lower()
```

### Testing AWS Service Interactions

When testing commands that interact with AWS services:

```python
@pytest.mark.integration
def test_dynamodb_list_tables(cli_runner):
  """Test listing DynamoDB tables."""
  with mock_aws():
    # Create mock DynamoDB resource
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    dynamodb.create_table(
      TableName='test-table',
      KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
      AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}],
      BillingMode='PAY_PER_REQUEST'
    )

    # Test the command
    result = cli_runner.invoke(list_tables)
    assert result.exit_code == 0
    assert 'test-table' in result.output
```

### Testing Configuration Management

When testing configuration operations:

```python
@pytest.mark.integration
def test_config_set_nested_key(cli_runner, temp_config_dir, mocker):
  """Test setting nested configuration keys."""
  config_file = temp_config_dir / 'config.json'
  mocker.patch('cli_tool.core.utils.config_manager.CONFIG_FILE', config_file)

  # Set nested key
  result = cli_runner.invoke(config_set, ['aws.region', 'us-west-2'])
  assert result.exit_code == 0

  # Verify the value was set
  import json
  with open(config_file) as f:
    config = json.load(f)
  assert config['aws']['region'] == 'us-west-2'
```

### Testing Error Messages

When verifying error handling and user-friendly messages:

```python
@pytest.mark.integration
def test_command_missing_required_argument(cli_runner):
  """Test command with missing required argument shows helpful error."""
  result = cli_runner.invoke(export_table)
  assert result.exit_code != 0
  # Check for helpful error message
  assert 'table' in result.output.lower() or 'required' in result.output.lower()
```

### Testing with Temporary Files

When testing file operations:

```python
@pytest.mark.unit
def test_export_to_file(tmp_path):
  """Test exporting data to a file."""
  output_file = tmp_path / "export.json"

  # Perform export
  export_data(data, str(output_file))

  # Verify file was created and contains expected data
  assert output_file.exists()
  import json
  with open(output_file) as f:
    exported = json.load(f)
  assert len(exported) > 0
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-mock documentation](https://pytest-mock.readthedocs.io/)
- [moto documentation](https://docs.getmoto.org/)
- [Click testing documentation](https://click.palletsprojects.com/en/8.1.x/testing/)
- [Rich testing guide](https://rich.readthedocs.io/en/stable/console.html#testing)

## Questions or Issues?

If you encounter issues not covered in this guide:

1. Check existing tests for similar patterns
2. Review the troubleshooting section
3. Ask the team for guidance
4. Update this documentation with solutions

---

**Last Updated:** 2025-01-30
**Maintained By:** Devo CLI Team
