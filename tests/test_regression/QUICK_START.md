# Regression Test Quick Start Guide

## 5-Minute Guide to Writing a Regression Test

### Step 1: Choose Your Template (30 seconds)

| Bug Type | Template File |
|----------|--------------|
| General bug | `TEMPLATE.py` |
| CLI command bug | `templates/cli_command_bug_template.py` |
| AWS integration bug | `templates/aws_integration_bug_template.py` |
| Data corruption | `templates/data_corruption_bug_template.py` |
| Platform-specific | `templates/platform_specific_bug_template.py` |
| Concurrency bug | `templates/concurrency_bug_template.py` |

### Step 2: Copy and Rename (10 seconds)

```bash
# For GitHub issue #123
cp tests/test_regression/TEMPLATE.py tests/test_regression/test_issue_123.py

# For Jira ticket DEVO-456
cp tests/test_regression/TEMPLATE.py tests/test_regression/test_devo_456.py
```

### Step 3: Fill in the Header (1 minute)

Replace these placeholders:
- `XXX` → Your issue number
- `[Brief description]` → One-line bug summary
- Bug Description → What went wrong
- Expected Behavior → What should happen
- GitHub Issue link → Actual issue URL
- Fixed in → PR number or commit hash

### Step 4: Write the Test (2 minutes)

```python
@pytest.mark.unit  # or @pytest.mark.integration
def test_issue_123_brief_description():
  """
  Regression test for Issue #123: One-line description.

  Bug: What was broken
  Fix: How it was fixed

  Issue: https://github.com/org/repo/issues/123
  """
  # ARRANGE: Set up the bug scenario
  input_data = {}  # The data that triggers the bug

  # ACT: Execute the code that previously failed
  result = function_under_test(input_data)

  # ASSERT: Verify the fix works
  assert result == expected_output
```

### Step 5: Run and Verify (1 minute)

```bash
# Run the test
pytest tests/test_regression/test_issue_123.py -v

# Verify it covers the fix
pytest tests/test_regression/test_issue_123.py --cov=cli_tool.module_name
```

### Step 6: Commit (30 seconds)

```bash
git add tests/test_regression/test_issue_123.py
git commit -m "test: add regression test for issue #123"
```

## Common Patterns

### Pattern 1: Simple Function Bug

```python
@pytest.mark.unit
def test_issue_123_function_bug():
  """Bug: Function crashed on empty input."""
  result = function_name("")
  assert result.is_error()
```

### Pattern 2: CLI Command Bug

```python
@pytest.mark.integration
def test_issue_456_cli_bug(cli_runner):
  """Bug: Command failed with invalid argument."""
  result = cli_runner.invoke(command, ['arg'])
  assert result.exit_code == 0
```

### Pattern 3: Data Corruption Bug

```python
@pytest.mark.unit
def test_issue_789_data_corruption():
  """Bug: Data lost during transformation."""
  original = {"key": "value"}
  result = transform(original)
  assert result == original  # Should be unchanged
```

### Pattern 4: AWS Integration Bug

```python
@pytest.mark.integration
@mock_aws
def test_issue_101_aws_bug():
  """Bug: AWS operation failed."""
  dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
  # Test AWS operation
```

## Checklist

Before submitting:

- [ ] Test fails without the fix ✓
- [ ] Test passes with the fix ✓
- [ ] Issue link is included ✓
- [ ] Bug is documented ✓
- [ ] Test uses AAA pattern ✓
- [ ] Appropriate marker is used ✓

## Need Help?

- **Full guide:** `tests/test_regression/GUIDELINES.md`
- **Templates:** `tests/test_regression/templates/`
- **Examples:** `tests/test_regression/test_issue_123.py`
- **Main docs:** `tests/README.md`

## Pro Tips

1. **Verify the test fails first:** Temporarily revert the fix and run the test. It should fail.

2. **Keep it focused:** Test only the specific bug, not the entire feature.

3. **Document thoroughly:** Future you will thank present you.

4. **Test edge cases:** Add separate tests for boundary conditions.

5. **Mock everything:** Don't depend on external services or files.

## Common Mistakes

❌ **Test passes without the fix** → Not testing the bug correctly

❌ **Test is too broad** → Focus on the specific bug

❌ **Missing documentation** → Add issue links and descriptions

❌ **No edge cases** → Test boundary conditions

❌ **Depends on external state** → Mock all dependencies

## Quick Commands

```bash
# Run all regression tests
pytest tests/test_regression/

# Run specific test
pytest tests/test_regression/test_issue_123.py

# Run with coverage
pytest tests/test_regression/ --cov=cli_tool

# Run verbose
pytest tests/test_regression/ -v

# Run and show print statements
pytest tests/test_regression/ -s
```

## Template Selection Guide

```
Is it a CLI command bug?
├─ Yes → Use cli_command_bug_template.py
└─ No
   └─ Is it AWS-related?
      ├─ Yes → Use aws_integration_bug_template.py
      └─ No
         └─ Does it corrupt data?
            ├─ Yes → Use data_corruption_bug_template.py
            └─ No
               └─ Is it platform-specific?
                  ├─ Yes → Use platform_specific_bug_template.py
                  └─ No
                     └─ Is it a concurrency issue?
                        ├─ Yes → Use concurrency_bug_template.py
                        └─ No → Use TEMPLATE.py
```

## Example: Complete Workflow

```bash
# 1. Bug #123 is reported: "Config set fails on nested keys"

# 2. Copy template
cp tests/test_regression/TEMPLATE.py tests/test_regression/test_issue_123.py

# 3. Edit file (fill in header, write test)
vim tests/test_regression/test_issue_123.py

# 4. Run test (should fail without fix)
git stash  # Temporarily remove fix
pytest tests/test_regression/test_issue_123.py  # Should FAIL
git stash pop  # Restore fix

# 5. Run test (should pass with fix)
pytest tests/test_regression/test_issue_123.py  # Should PASS

# 6. Verify coverage
pytest tests/test_regression/test_issue_123.py --cov=cli_tool.core.utils.config_manager

# 7. Commit
git add tests/test_regression/test_issue_123.py
git commit -m "test: add regression test for issue #123"

# 8. Push and create PR
git push origin feature/fix-issue-123
```

## That's It!

You now know how to write a regression test. For more details, see `GUIDELINES.md`.
