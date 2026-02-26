# devo code-reviewer

AI-powered code review analyzing git diffs for quality, security, and best practices.

## Synopsis

```bash
devo code-reviewer [OPTIONS]
```

## Description

Performs comprehensive analysis of code changes using AWS Bedrock AI. Analyzes staged changes or specific commits for code quality, security vulnerabilities, performance issues, and best practices compliance.

## Usage

::: mkdocs-click
    :module: cli_tool.commands.code_reviewer
    :command: code_reviewer
    :prog_name: devo
    :depth: 1

## Options

| Option | Description |
|--------|-------------|
| `--commit TEXT` | Analyze specific commit instead of staged changes |
| `--help` | Show help message and exit |

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
# Review staged changes
devo code-reviewer

# Review specific commit
devo code-reviewer --commit abc123

# Use specific AWS profile
devo --profile production code-reviewer
```

## See Also

- [Code Review Workflow Guide](../guides/code-review-workflow.md) - Step-by-step usage guide
- [Commit Command](commit.md) - Generate commit messages
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
