# Regression Test Guidelines

## Overview

This document provides comprehensive guidelines for writing effective regression tests. Regression tests are critical for preventing bugs from reappearing after they've been fixed.

## Table of Contents

1. [When to Write a Regression Test](#when-to-write-a-regression-test)
2. [Choosing the Right Template](#choosing-the-right-template)
3. [Writing Effective Regression Tests](#writing-effective-regression-tests)
4. [Naming Conventions](#naming-conventions)
5. [Documentation Requirements](#documentation-requirements)
6. [Test Structure and Patterns](#test-structure-and-patterns)
7. [Common Pitfalls to Avoid](#common-pitfalls-to-avoid)
8. [Integration with Issue Tracking](#integration-with-issue-tracking)
9. [Review Checklist](#review-checklist)

## When to Write a Regression Test

Write a regression test whenever:

1. **A bug is fixed**: Every bug fix should include a regression test
2. **A feature breaks**: When a feature that previously worked stops working
3. **An edge case is discovered**: When an unexpected input causes incorrect behavior
4. **A security issue is found**: Security fixes must have regression tests
5. **Data corruption occurs**: Any data integrity issue needs a regression test
6. **Platform-specific issues**: Bugs that only occur on certain platforms
7. **Concurrency issues**: Race conditions, deadlocks, or thread safety issues

## Choosing the Right Template

We provide several templates for different types of bugs:

### 1. General Template (`TEMPLATE.py`)

Use for most bugs that don't fit other categories.

**When to use:**
- Simple logic errors
- Input validation bugs
- Output formatting issues
- General functionality bugs

### 2. CLI Command Bug Template (`templates/cli_command_bug_template.py`)

Use for bugs related to CLI commands.

**When to use:**
- Command argument parsing errors
- Command output formatting issues
- Interactive prompt bugs
- Command exit code problems
- Flag/option handling issues

### 3. AWS Integration Bug Template (`templates/aws_integration_bug_template.py`)

Use for bugs related to AWS services.

**When to use:**
- AWS API interaction errors
- Credential handling issues
- AWS service mocking problems
- Region configuration bugs
- AWS error handling issues

### 4. Data Corruption Bug Template (`templates/data_corruption_bug_template.py`)

Use for bugs that cause data loss or corruption.

**When to use:**
- Data serialization/deserialization errors
- Configuration corruption
- File corruption
- Data transformation errors
- Round-trip data integrity issues

### 5. Platform-Specific Bug Template (`templates/platform_specific_bug_template.py`)

Use for bugs that only occur on specific platforms.

**When to use:**
- Windows-only bugs
- macOS-only bugs
- Linux-only bugs
- Path handling issues
- Shell-specific problems

### 6. Concurrency Bug Template (`templates/concurrency_bug_template.py`)

Use for bugs related to concurrent execution.

**When to use:**
- Race conditions
- Deadlocks
- Thread safety issues
- Concurrent write problems
- Synchronization bugs

## Writing Effective Regression Tests

### The Golden Rule

**A regression test should fail before the fix and pass after the fix.**

If your test passes even without the fix, it's not testing the bug correctly.

### Step-by-Step Process

#### 1. Understand the Bug

Before writing the test:
- Read the bug report thoroughly
- Reproduce the bug manually
- Understand the root cause
- Understand the fix

#### 2. Choose a Template

Select the appropriate template based on the bug type (see above).

#### 3. Copy and Rename

```bash
# Copy the template
cp tests/test_regression/TEMPLATE.py tests/test_regression/test_issue_123.py

# Or copy a specific template
cp tests/test_regression/templates/cli_command_bug_template.py tests/test_regression/test_issue_456.py
```

#### 4. Fill in the Header

Replace placeholders with actual information:

```python
"""
Regression test for Issue #123: Config set doesn't create nested keys

Bug Description:
  Setting a deeply nested config key like 'aws.sso.profiles.dev.region'
  failed with KeyError when intermediate keys didn't exist.

Expected Behavior:
  Config set should automatically create intermediate dictionaries,
  similar to 'mkdir -p' for directories.

Reproduction Steps:
  1. Start with empty config: {}
  2. Run: devo config set aws.sso.profiles.dev.region us-west-2
  3. Expected: KeyError: 'aws'
  4. After fix: Config updated successfully

GitHub Issue: https://github.com/org/repo/issues/123
Fixed in: PR #124
"""
```

#### 5. Write the Test

Follow the AAA pattern:

```python
@pytest.mark.unit
def test_issue_123_config_set_creates_nested_keys():
  """
  Regression test for Issue #123.

  Bug: KeyError when setting nested keys
  Fix: Auto-create intermediate dictionaries

  Issue: https://github.com/org/repo/issues/123
  """
  # ARRANGE: Set up the scenario that triggers the bug
  config = {}  # Empty config triggers the bug

  # ACT: Execute the code that previously failed
  set_config_value(config, "aws.region", "us-east-1")

  # ASSERT: Verify the fix works
  assert config == {"aws": {"region": "us-east-1"}}
```

#### 6. Add Edge Cases

Test related scenarios:

```python
@pytest.mark.unit
def test_issue_123_preserves_existing_keys():
  """Verify fix doesn't overwrite existing keys."""
  config = {"aws": {"profile": "dev"}}
  set_config_value(config, "aws.region", "us-east-1")

  assert config["aws"]["profile"] == "dev"  # Preserved
  assert config["aws"]["region"] == "us-east-1"  # Added
```

#### 7. Run and Verify

```bash
# Run the specific test
pytest tests/test_regression/test_issue_123.py -v

# Run with coverage
pytest tests/test_regression/test_issue_123.py --cov=cli_tool.core.utils.config_manager

# Verify it tests the fix
pytest tests/test_regression/test_issue_123.py --cov-report=html
# Check htmlcov/index.html to see if the fixed code is covered
```

## Naming Conventions

### File Names

Follow these patterns:

| Issue Source | File Name Pattern | Example |
|-------------|-------------------|---------|
| GitHub Issue | `test_issue_<number>.py` | `test_issue_123.py` |
| Jira Ticket | `test_<project>_<number>.py` | `test_devo_456.py` |
| Internal Bug | `test_bug_<description>.py` | `test_bug_config_nested_keys.py` |

### Test Function Names

Pattern: `test_<issue_id>_<brief_description>`

Examples:
- `test_issue_123_config_set_creates_nested_keys`
- `test_issue_123_preserves_existing_keys`
- `test_devo_456_commit_handles_binary_files`

### Guidelines

- Use lowercase with underscores (snake_case)
- Be descriptive but concise
- Include issue number for traceability
- Describe what is being tested, not how

## Documentation Requirements

Every regression test must include:

### 1. Module Docstring

```python
"""
Regression test for Issue #123: Brief description

Detailed bug description...

Expected behavior...

GitHub Issue: https://github.com/org/repo/issues/123
Fixed in: PR #124
"""
```

### 2. Test Function Docstring

```python
def test_issue_123_description():
  """
  Regression test for Issue #123: One-line description.

  Bug: What was broken
  Fix: How it was fixed

  Issue: https://github.com/org/repo/issues/123
  """
```

### 3. Inline Comments

```python
# ARRANGE: Set up the bug scenario
config = {}  # Empty config triggers KeyError

# ACT: This would have raised KeyError before the fix
set_config_value(config, "aws.region", "us-east-1")

# ASSERT: Verify the fix works
assert config["aws"]["region"] == "us-east-1"
```

## Test Structure and Patterns

### AAA Pattern (Arrange-Act-Assert)

Always structure tests using the AAA pattern:

```python
def test_example():
  # ARRANGE: Set up test data and conditions
  input_data = create_test_data()

  # ACT: Execute the code being tested
  result = function_under_test(input_data)

  # ASSERT: Verify expected outcomes
  assert result == expected_output
```

### Multiple Test Cases

When a bug has multiple aspects, write separate test functions:

```python
# Main test - reproduces the original bug
def test_issue_123_main_bug():
  """Test the primary bug scenario."""
  pass

# Edge case 1
def test_issue_123_edge_case_empty_input():
  """Test with empty input."""
  pass

# Edge case 2
def test_issue_123_edge_case_existing_data():
  """Test with existing data."""
  pass

# Related functionality
def test_issue_123_doesnt_break_related_feature():
  """Verify fix doesn't break related features."""
  pass
```

### Parametrized Tests

For testing multiple similar scenarios:

```python
@pytest.mark.parametrize("input,expected", [
  ({}, {"aws": {"region": "us-east-1"}}),
  ({"aws": {}}, {"aws": {"region": "us-east-1"}}),
  ({"aws": {"profile": "dev"}}, {"aws": {"profile": "dev", "region": "us-east-1"}}),
])
def test_issue_123_various_scenarios(input, expected):
  """Test bug fix with various input scenarios."""
  set_config_value(input, "aws.region", "us-east-1")
  assert input == expected
```

## Common Pitfalls to Avoid

### 1. Test Doesn't Actually Test the Bug

**Problem:** Test passes even without the fix.

**Solution:** Verify the test fails on the unfixed code:
```bash
# Temporarily revert the fix
git stash
# Run the test - it should FAIL
pytest tests/test_regression/test_issue_123.py
# Restore the fix
git stash pop
# Run the test - it should PASS
pytest tests/test_regression/test_issue_123.py
```

### 2. Test is Too Broad

**Problem:** Test tests more than just the bug.

**Solution:** Focus on the specific bug:
```python
# BAD: Tests too much
def test_issue_123():
  config = load_config()
  set_config_value(config, "aws.region", "us-east-1")
  save_config(config)
  reloaded = load_config()
  assert reloaded["aws"]["region"] == "us-east-1"

# GOOD: Tests just the bug
def test_issue_123():
  config = {}
  set_config_value(config, "aws.region", "us-east-1")
  assert config["aws"]["region"] == "us-east-1"
```

### 3. Missing Edge Cases

**Problem:** Only tests the happy path.

**Solution:** Test edge cases:
```python
# Test the main bug
def test_issue_123_main():
  pass

# Test edge cases
def test_issue_123_empty_input():
  pass

def test_issue_123_existing_data():
  pass

def test_issue_123_deeply_nested():
  pass
```

### 4. Poor Documentation

**Problem:** Future developers don't understand what the test is for.

**Solution:** Document thoroughly:
```python
"""
Regression test for Issue #123: Config set doesn't create nested keys

Bug Description:
  [Detailed explanation of the bug]

Expected Behavior:
  [What should happen instead]

GitHub Issue: https://github.com/org/repo/issues/123
Fixed in: PR #124
"""
```

### 5. Test Depends on External State

**Problem:** Test fails intermittently due to external dependencies.

**Solution:** Mock all external dependencies:
```python
# BAD: Depends on real file system
def test_issue_123():
  config = load_config()  # Reads from ~/.devo/config.json
  # ...

# GOOD: Uses mocks
def test_issue_123(temp_config_dir, mocker):
  config_file = temp_config_dir / "config.json"
  mocker.patch("cli_tool.core.utils.config_manager.CONFIG_FILE", config_file)
  # ...
```

### 6. Test is Flaky

**Problem:** Test sometimes passes, sometimes fails.

**Solution:** Identify and fix the source of flakiness:
- Remove timing dependencies
- Mock random/time functions
- Ensure test isolation
- Fix race conditions

## Integration with Issue Tracking

### Linking Tests to Issues

Always include issue links in:

1. **Module docstring:**
   ```python
   """
   GitHub Issue: https://github.com/org/repo/issues/123
   Jira Ticket: DEVO-456
   """
   ```

2. **Test docstring:**
   ```python
   """
   Issue: https://github.com/org/repo/issues/123
   """
   ```

3. **Git commit message:**
   ```
   test: add regression test for issue #123

   Regression test for config set nested key creation bug.

   Fixes #123
   ```

### Issue Tracking Best Practices

1. **Reference the issue in the PR:**
   - Use "Fixes #123" in PR description
   - Link to the original issue

2. **Update the issue:**
   - Comment with link to the regression test
   - Mark as "has regression test"

3. **Cross-reference:**
   - Link from test to issue
   - Link from issue to test
   - Link from fix PR to test PR

## Review Checklist

Before submitting a regression test, verify:

### Documentation
- [ ] Module docstring includes bug description
- [ ] Module docstring includes issue link
- [ ] Module docstring includes fix reference (PR/commit)
- [ ] Test function has descriptive docstring
- [ ] Inline comments explain the bug scenario

### Test Quality
- [ ] Test fails without the fix (verified)
- [ ] Test passes with the fix
- [ ] Test is focused on the specific bug
- [ ] Edge cases are covered
- [ ] Test uses appropriate markers (@pytest.mark.unit, etc.)

### Code Quality
- [ ] Follows AAA pattern (Arrange-Act-Assert)
- [ ] Uses appropriate fixtures
- [ ] Mocks all external dependencies
- [ ] No hardcoded paths or values
- [ ] Follows project code style (2-space indent, 150 char lines)

### Naming
- [ ] File name follows convention (test_issue_123.py)
- [ ] Test function name is descriptive
- [ ] Test function name includes issue number

### Integration
- [ ] Issue link is correct and accessible
- [ ] PR reference is included
- [ ] Related issues are cross-referenced
- [ ] Test is in correct directory (tests/test_regression/)

### Execution
- [ ] Test runs successfully in isolation
- [ ] Test runs successfully with full test suite
- [ ] Test doesn't have flaky behavior
- [ ] Test completes in reasonable time (<5 seconds)

## Examples

See these files for examples of well-written regression tests:

- `test_issue_123.py` - Config management bug
- `templates/cli_command_bug_template.py` - CLI command bug template
- `templates/aws_integration_bug_template.py` - AWS integration bug template
- `templates/data_corruption_bug_template.py` - Data corruption bug template
- `templates/platform_specific_bug_template.py` - Platform-specific bug template
- `templates/concurrency_bug_template.py` - Concurrency bug template

## Quick Reference

### Creating a New Regression Test

```bash
# 1. Copy appropriate template
cp tests/test_regression/TEMPLATE.py tests/test_regression/test_issue_123.py

# 2. Edit the file
vim tests/test_regression/test_issue_123.py

# 3. Run the test
pytest tests/test_regression/test_issue_123.py -v

# 4. Verify coverage
pytest tests/test_regression/test_issue_123.py --cov=cli_tool --cov-report=html

# 5. Commit
git add tests/test_regression/test_issue_123.py
git commit -m "test: add regression test for issue #123"
```

### Running Regression Tests

```bash
# All regression tests
pytest tests/test_regression/

# Specific test file
pytest tests/test_regression/test_issue_123.py

# Specific test function
pytest tests/test_regression/test_issue_123.py::test_issue_123_main

# With coverage
pytest tests/test_regression/ --cov=cli_tool --cov-report=term-missing

# Verbose output
pytest tests/test_regression/ -v

# Show print statements
pytest tests/test_regression/ -s
```

## Questions?

If you have questions about writing regression tests:

1. Review this guide and the templates
2. Look at existing regression tests for examples
3. Check the main testing documentation in `tests/README.md`
4. Ask in the team chat or create a discussion issue

## References

- Main Testing Documentation: `tests/README.md`
- Regression Test README: `tests/test_regression/README.md`
