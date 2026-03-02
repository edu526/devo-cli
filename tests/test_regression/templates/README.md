# Regression Test Templates

This directory contains specialized templates for different types of regression tests. Each template provides pre-filled structure, documentation, and checklists specific to that bug type.

## Available Templates

### 1. CLI Command Bug Template

**File:** `cli_command_bug_template.py`

**Use for:**
- Command argument parsing errors
- Command output formatting issues
- Interactive prompt bugs
- Command exit code problems
- Flag/option handling issues

**Key Features:**
- CliRunner setup
- Mock configuration examples
- Output verification patterns
- CLI command testing checklist

### 2. AWS Integration Bug Template

**File:** `aws_integration_bug_template.py`

**Use for:**
- AWS API interaction errors
- Credential handling issues
- AWS service mocking problems
- Region configuration bugs
- AWS error handling issues

**Key Features:**
- @mock_aws decorator usage
- AWS resource creation examples
- Credential handling patterns
- AWS integration testing checklist

### 3. Data Corruption Bug Template

**File:** `data_corruption_bug_template.py`

**Use for:**
- Data serialization/deserialization errors
- Configuration corruption
- File corruption
- Data transformation errors
- Round-trip data integrity issues

**Key Features:**
- Round-trip testing patterns
- Data integrity verification
- Edge case data values
- Data corruption testing checklist

### 4. Platform-Specific Bug Template

**File:** `platform_specific_bug_template.py`

**Use for:**
- Windows-only bugs
- macOS-only bugs
- Linux-only bugs
- Path handling issues
- Shell-specific problems

**Key Features:**
- Platform-specific test markers
- Cross-platform parametrized tests
- Platform detection mocking
- Platform-specific testing checklist

### 5. Concurrency Bug Template

**File:** `concurrency_bug_template.py`

**Use for:**
- Race conditions
- Deadlocks
- Thread safety issues
- Concurrent write problems
- Synchronization bugs

**Key Features:**
- Threading examples
- ThreadPoolExecutor patterns
- Race condition testing
- Concurrency testing checklist

## How to Use Templates

### Step 1: Choose the Right Template

Select the template that best matches your bug type. If unsure, use the general `TEMPLATE.py` in the parent directory.

### Step 2: Copy the Template

```bash
# Copy to the regression test directory
cp tests/test_regression/templates/cli_command_bug_template.py tests/test_regression/test_issue_123.py
```

### Step 3: Customize

1. Replace `XXX` with your issue number
2. Fill in the bug description
3. Add issue links
4. Implement the test logic
5. Remove the template instructions section

### Step 4: Run and Verify

```bash
pytest tests/test_regression/test_issue_123.py -v
```

## Template Structure

Each template includes:

1. **Header Documentation**
   - Bug description placeholder
   - Expected behavior placeholder
   - Issue link placeholders
   - Example before/after scenarios

2. **Test Functions**
   - Main test function with AAA pattern
   - Edge case test functions
   - Error handling test functions

3. **Testing Checklist**
   - Bug-type-specific verification points
   - Common pitfalls to avoid
   - Best practices

4. **Usage Instructions**
   - Step-by-step guide
   - Common patterns
   - Examples

## When to Use Which Template

```
Question: What type of bug is it?

├─ CLI command behavior → cli_command_bug_template.py
├─ AWS service integration → aws_integration_bug_template.py
├─ Data loss/corruption → data_corruption_bug_template.py
├─ Platform-specific → platform_specific_bug_template.py
├─ Concurrency/threading → concurrency_bug_template.py
└─ General/other → ../TEMPLATE.py
```

## Template Maintenance

### Adding New Templates

If you identify a new bug pattern that occurs frequently:

1. Create a new template file in this directory
2. Follow the existing template structure
3. Include comprehensive documentation
4. Add a testing checklist
5. Update this README
6. Update the main GUIDELINES.md

### Updating Existing Templates

When updating templates:

1. Ensure backward compatibility
2. Update all related documentation
3. Add examples for new patterns
4. Update the testing checklist

## Examples

See the parent directory for examples of completed regression tests:

- `../test_issue_123.py` - Example using general template
- More examples will be added as bugs are fixed

## Questions?

For more information:

- **Quick Start**: `../QUICK_START.md` - 5-minute guide
- **Guidelines**: `../GUIDELINES.md` - Comprehensive guide
- **Main README**: `../README.md` - Regression testing overview
- **Testing Docs**: `../../README.md` - Main testing documentation

## Contributing

To contribute a new template:

1. Identify a recurring bug pattern
2. Create a template following the existing structure
3. Include comprehensive documentation and checklists
4. Add examples and usage instructions
5. Update this README
6. Submit a pull request

## Template Checklist

When creating a new template, ensure it includes:

- [ ] Comprehensive header documentation
- [ ] Bug description placeholder
- [ ] Expected behavior placeholder
- [ ] Issue link placeholders
- [ ] Example before/after scenarios
- [ ] Main test function with AAA pattern
- [ ] Edge case test functions
- [ ] Error handling test functions
- [ ] Bug-type-specific testing checklist
- [ ] Usage instructions
- [ ] Common patterns and examples
- [ ] Appropriate pytest markers
- [ ] Mock setup examples (if applicable)
- [ ] Fixture usage examples (if applicable)

## License

These templates are part of the Devo CLI project and follow the same license.
