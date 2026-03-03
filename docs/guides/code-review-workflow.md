# Code Review Workflow

Learn how to use AI-powered code review to analyze your changes before committing.

## Quick Start

```bash
# Run code review (compares current branch vs main/master)
devo code-reviewer
```

## Review Process

### 1. Make Your Changes

Work on your branch normally.

### 2. Run the Review

```bash
devo code-reviewer
```

The AI will compare your current branch against the auto-detected base branch (main/master) and analyze:

- Code quality and maintainability
- Security vulnerabilities
- Performance issues
- Best practices compliance
- Potential bugs

### 3. Review the Feedback

The output includes:

- Severity levels (Critical, High, Medium, Low, Info)
- Specific file locations and line numbers
- Clear descriptions of issues
- Actionable recommendations

### 4. Address Issues

Fix the identified issues and run the review again:

```bash
# Make fixes
vim src/auth.py

# Review again
devo code-reviewer
```

## Common Workflows

### Pre-Commit Review

Review branch changes before committing:

```bash
devo code-reviewer
# Fix issues
devo commit
```

### Review Against Specific Branch

Compare your branch against a specific base:

```bash
devo code-reviewer --base-branch develop
```

### JSON Output for CI/CD

Get machine-readable output:

```bash
devo code-reviewer --output json
```

## Understanding Review Categories

### Code Quality

- Code structure and organization
- Naming conventions
- Code duplication
- Complexity analysis

### Security

- Input validation
- Authentication/authorization issues
- Sensitive data exposure
- Injection vulnerabilities

### Performance

- Inefficient algorithms
- Resource usage
- Database query optimization
- Caching opportunities

### Best Practices

- Language-specific conventions
- Design patterns
- Error handling
- Documentation

## Tips for Better Reviews

1. **Review small changes**: Smaller diffs get more focused feedback
2. **Commit frequently**: Keep changes grouped and meaningful
3. **Run frequently**: Catch issues early in development
4. **Address critical issues first**: Prioritize by severity
5. **Use with commit workflow**: Combine with `devo commit` for complete workflow

## Configuration

### Set Bedrock Model

```bash
export BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
```

### AWS Profile

```bash
devo --profile production code-reviewer
```

### Troubleshooting

### No Changes Detected

Make sure your branch has commits that differ from the base branch (main/master). Code reviewer compares branch history, not staged files.

### Access Denied

Verify AWS credentials and Bedrock permissions:

```bash
aws sts get-caller-identity
aws bedrock list-foundation-models --region us-east-1
```

### Review Takes Too Long

For large diffs, consider reviewing against a more recent base branch or use the short prompt (default):

```bash
# Short prompt (default, faster)
devo code-reviewer

# Full prompt (more thorough but slower)
devo code-reviewer --full-prompt

# Compare against closer base branch
devo code-reviewer --base-branch your-feature-parent-branch
```

## Next Steps

- [Commit Workflow](commit-workflow.md) - Generate commit messages
- [AWS Setup](aws-setup.md) - Configure AWS credentials
- [Code Reviewer Command Reference](../commands/code-reviewer.md) - Full command options
