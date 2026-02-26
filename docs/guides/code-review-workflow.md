# Code Review Workflow

Learn how to use AI-powered code review to analyze your changes before committing.

## Quick Start

```bash
# Stage your changes
git add .

# Run code review
devo code-reviewer
```

## Review Process

### 1. Prepare Your Changes

Stage the files you want to review:

```bash
# Stage specific files
git add src/auth.py src/utils.py

# Stage all changes
git add .
```

### 2. Run the Review

```bash
devo code-reviewer
```

The AI will analyze:

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

# Stage changes
git add src/auth.py

# Review again
devo code-reviewer
```

## Common Workflows

### Pre-Commit Review

Review changes before committing:

```bash
git add .
devo code-reviewer
# Fix issues
devo commit
```

### Review Specific Commit

Analyze a specific commit:

```bash
devo code-reviewer --commit abc123
```

### Review Branch Changes

Compare your branch against main:

```bash
git diff main feature/my-branch | devo code-reviewer
```

### Review Pull Request

Before creating a PR:

```bash
# Review all changes in your branch
git diff main...HEAD | devo code-reviewer
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
2. **Stage related changes**: Group related files together
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

## Troubleshooting

### No Changes Detected

Make sure you have staged changes:

```bash
git status
git add <files>
```

### Access Denied

Verify AWS credentials and Bedrock permissions:

```bash
aws sts get-caller-identity
aws bedrock list-foundation-models --region us-east-1
```

### Review Takes Too Long

For large diffs, consider reviewing in smaller chunks:

```bash
# Review specific files
git add src/auth.py
devo code-reviewer
```

## Next Steps

- [Commit Workflow](commit-workflow.md) - Generate commit messages
- [AWS Setup](aws-setup.md) - Configure AWS credentials
- [Code Reviewer Command Reference](../commands/code-reviewer.md) - Full command options

