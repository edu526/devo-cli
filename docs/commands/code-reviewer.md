# devo code-reviewer

AI-powered code review analyzing git diffs for quality, security, and best practices.

## Synopsis

```bash
devo code-reviewer [OPTIONS]
```

## Description

Performs comprehensive analysis of code changes using AWS Bedrock AI. Analyzes the diff between your current branch and a base branch (e.g., main/master) for code quality, security vulnerabilities, performance issues, and best practices compliance.

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--base-branch TEXT` | `-b` | Base branch to compare against (default: auto-detect main/master) |
| `--repo-path TEXT` | `-r` | Path to the Git repository (default: current directory) |
| `--output [json\|table]` | `-o` | Output format (default: table) |
| `--show-metrics` | `-m` | Include detailed execution metrics in the output |
| `--full-prompt` | `-f` | Use full detailed prompt (default: optimized short prompt) |
| `--help` | | Show help message and exit |

## Review Categories

The command analyzes code across four main categories:

- **Code Quality**: Structure, naming conventions, duplication, complexity
- **Security**: Input validation, authentication, data exposure, injection vulnerabilities
- **Performance**: Algorithm efficiency, resource usage, query optimization, caching
- **Best Practices**: Language conventions, design patterns, error handling, documentation

## Output Format

Structured feedback includes:

- Severity levels: Critical, High, Medium, Low, Info
- File locations with line numbers
- Issue descriptions
- Actionable recommendations

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL_ID` | AWS Bedrock model to use | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` |
| `AWS_PROFILE` | AWS profile for credentials | Default profile |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (no changes, access denied, etc.) |

## Examples

```bash
# Review changes in current branch vs auto-detected base branch (main/master)
devo code-reviewer

# Review changes vs a specific base branch
devo code-reviewer --base-branch develop

# Get JSON output for CI/CD integration
devo code-reviewer --output json

# Show execution metrics
devo code-reviewer --show-metrics

# Use full detailed prompt (more comprehensive but slower)
devo code-reviewer --full-prompt

# Combine options
devo code-reviewer --base-branch develop --show-metrics --output json

# Use specific AWS profile
devo --profile production code-reviewer
```

## See Also

- [Code Review Workflow Guide](../guides/code-review-workflow.md) - Step-by-step usage guide
- [Commit Command](commit.md) - Generate commit messages
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
