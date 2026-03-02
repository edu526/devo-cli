# Regression Tests

## Purpose

This directory contains regression tests that verify previously fixed bugs remain fixed. Each regression test reproduces a specific bug that was discovered and fixed in the project's history.

## Why Regression Tests?

Regression tests serve several critical purposes:

1. **Prevent Bug Reintroduction**: Ensure that bug fixes remain effective as the codebase evolves
2. **Document Bug History**: Provide a living record of issues that have been resolved
3. **Traceability**: Link tests directly to issue tracking system (GitHub Issues, Jira, etc.)
4. **Confidence in Refactoring**: Allow safe code refactoring by catching unintended behavior changes

## Test Organization

Each regression test should:

- Be named after the issue it addresses (e.g., `test_issue_123.py`, `test_gh_456.py`)
- Include the issue number in the test docstring
- Reproduce the original bug scenario
- Verify the fix is working correctly
- Include a link to the original issue in comments

## Test Template

```python
"""
Regression test for Issue #123: Config set doesn't create nested keys

GitHub Issue: https://github.com/org/repo/issues/123
Fixed in: PR #124
"""

import pytest
from cli_tool.core.utils.config_manager import set_config_value


@pytest.mark.unit
def test_issue_123_config_set_creates_nested_keys():
  """
  Regression test for Issue #123.

  Bug: config set command failed when setting nested keys that didn't exist.
  Expected: config set should create intermediate dictionaries automatically.

  Issue: https://github.com/org/repo/issues/123
  """
  config = {}

  # This used to raise KeyError before the fix
  set_config_value(config, "aws.region", "us-east-1")

  # Verify nested structure was created
  assert config == {"aws": {"region": "us-east-1"}}
```

## Naming Conventions

### File Names

- **GitHub Issues**: `test_issue_<number>.py` (e.g., `test_issue_123.py`)
- **Jira Tickets**: `test_<project>_<number>.py` (e.g., `test_devo_456.py`)
- **Internal Bugs**: `test_bug_<description>.py` (e.g., `test_bug_config_nested_keys.py`)

### Test Function Names

Test functions should follow this pattern:
```
test_<issue_id>_<brief_description>
```

Examples:
- `test_issue_123_config_set_creates_nested_keys`
- `test_devo_456_commit_handles_binary_files`
- `test_bug_aws_login_credential_refresh`

## Test Markers

All regression tests should use appropriate pytest markers:

```python
@pytest.mark.unit  # For unit-level regression tests
@pytest.mark.integration  # For integration-level regression tests
@pytest.mark.platform  # For platform-specific regression tests
```

## Documentation Requirements

Each regression test file must include:

1. **Module Docstring**: Brief description of the bug and fix
2. **Issue Link**: URL to the original issue
3. **Fix Reference**: PR number or commit hash where the bug was fixed
4. **Test Docstring**: Detailed explanation of the bug behavior and expected fix

## Running Regression Tests

### Run All Regression Tests

```bash
pytest tests/test_regression/
```

### Run Specific Regression Test

```bash
pytest tests/test_regression/test_issue_123.py
```

### Run Regression Tests with Coverage

```bash
pytest tests/test_regression/ --cov=cli_tool --cov-report=term-missing
```

## Adding New Regression Tests

When a bug is fixed, follow these steps:

1. **Choose a Template**: Select the appropriate template from `templates/` directory or use `TEMPLATE.py`
2. **Copy and Rename**: Copy the template to a new file following naming conventions
3. **Fill in Header**: Replace placeholders with actual bug information and issue links
4. **Write the Test**: Implement the test that reproduces the bug and verifies the fix
5. **Add Edge Cases**: Include tests for related edge cases and boundary conditions
6. **Run and Verify**: Ensure the test fails without the fix and passes with it
7. **Document**: Add thorough documentation explaining the bug and fix
8. **Commit**: Commit the test with a descriptive message

### Quick Start

For a quick guide, see **[QUICK_START.md](QUICK_START.md)** (5-minute guide).

For comprehensive guidelines, see **[GUIDELINES.md](GUIDELINES.md)** (complete reference).

### Available Templates

We provide specialized templates for different bug types:

- **`TEMPLATE.py`** - General regression test template
- **`templates/cli_command_bug_template.py`** - CLI command bugs
- **`templates/aws_integration_bug_template.py`** - AWS integration bugs
- **`templates/data_corruption_bug_template.py`** - Data corruption bugs
- **`templates/platform_specific_bug_template.py`** - Platform-specific bugs
- **`templates/concurrency_bug_template.py`** - Concurrency bugs

Choose the template that best matches your bug type for pre-filled guidance and checklists.

## Common Regression Test Patterns

### Pattern 1: Input Validation Bug

```python
def test_issue_XXX_validates_empty_input():
  """Bug: Function crashed on empty input instead of returning error."""
  result = function_under_test("")
  assert result.is_error()
  assert "empty input" in result.error_message
```

### Pattern 2: Edge Case Handling

```python
def test_issue_XXX_handles_boundary_value():
  """Bug: Function failed at boundary value (e.g., zero, max int)."""
  result = function_under_test(0)
  assert result.is_success()
```

### Pattern 3: State Management Bug

```python
def test_issue_XXX_cleans_up_state():
  """Bug: Function left system in inconsistent state on error."""
  with pytest.raises(ExpectedException):
    function_under_test(invalid_input)

  # Verify state was cleaned up
  assert system_state_is_clean()
```

### Pattern 4: Concurrency Bug

```python
def test_issue_XXX_thread_safe_operation():
  """Bug: Function had race condition with concurrent access."""
  import threading

  results = []

  def worker():
    results.append(function_under_test())

  threads = [threading.Thread(target=worker) for _ in range(10)]
  for t in threads:
    t.start()
  for t in threads:
    t.join()

  # Verify all operations succeeded
  assert all(r.is_success() for r in results)
```

### Pattern 5: Configuration Migration Bug

```python
def test_issue_XXX_migrates_legacy_config():
  """Bug: Config migration failed for legacy format."""
  legacy_config = {"old_key": "value"}
  migrated = migrate_config(legacy_config)

  assert "new_key" in migrated
  assert migrated["new_key"] == "value"
```

## Integration with CI/CD

Regression tests run automatically in the CI/CD pipeline:

- **On Every Commit**: All regression tests run to catch reintroduced bugs
- **On Pull Requests**: Regression tests must pass before merging
- **Coverage Tracking**: Regression tests contribute to overall coverage metrics

## Maintenance Guidelines

### When to Update Regression Tests

- **Never Remove**: Regression tests should never be removed unless the feature itself is removed
- **Update on Refactoring**: If the underlying implementation changes, update the test to match new API
- **Expand on Related Bugs**: If a similar bug is found, add additional test cases to the existing file

### When to Archive Regression Tests

If a feature is completely removed from the codebase:

1. Move the regression test to `tests/test_regression/archived/`
2. Add a comment explaining why it was archived
3. Keep the test for historical reference

## Examples

See the following files for examples of well-written regression tests:

- `test_issue_123.py` - Example of config management bug fix
- (More examples will be added as bugs are fixed)

## Questions?

If you have questions about regression testing or need help writing a regression test, please:

1. Review this README and existing regression tests
2. Check the main testing documentation in `tests/README.md`
3. Ask in the team chat or create a discussion issue

## References

- **Quick Start Guide**: `QUICK_START.md` - 5-minute guide to writing regression tests
- **Comprehensive Guidelines**: `GUIDELINES.md` - Complete reference for regression testing
- **Templates Directory**: `templates/` - Specialized templates for different bug types
- Main Testing Documentation: `tests/README.md`
- Testing Strategy Design: `.kiro/specs/comprehensive-testing-strategy/design.md`
- Requirements: `.kiro/specs/comprehensive-testing-strategy/requirements.md`
