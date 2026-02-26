# devo commit

Generate conventional commit messages from staged git changes using AI.

## Synopsis

```bash
devo commit [OPTIONS]
```

## Description

Analyzes staged git changes and generates a properly formatted conventional commit message. Uses AWS Bedrock AI to understand code changes and create semantic commit messages following the format: `<type>(<scope>): <summary>`

## Usage

::: mkdocs-click
    :module: cli_tool.commands.commit_prompt
    :command: commit
    :prog_name: devo
    :depth: 1

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

## Commit Message Format

```
<type>(<scope>): <summary>

[optional body]

[optional footer]
```

### Commit Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `chore` | Maintenance tasks |
| `docs` | Documentation changes |
| `refactor` | Code refactoring |
| `test` | Test additions or modifications |
| `style` | Code style changes |
| `perf` | Performance improvements |

### Summary Line

- Maximum 50 characters
- Imperative mood (e.g., "add" not "added")
- No period at the end
- Lowercase after type and scope

## Ticket Number Extraction

Automatically extracts ticket numbers from branch names following the pattern:

```
<type>/<TICKET-NUMBER>-description
```

Examples:
- `feature/XYZ-123-user-auth` → Includes `XYZ-123` in commit message
- `fix/ABC-456-login-bug` → Includes `ABC-456` in commit message

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
| 1 | Error (no staged changes, access denied, etc.) |

## Examples

```bash
# Generate commit message for staged changes
devo commit

# Use specific AWS profile
devo --profile production commit

# Example output:
# feat(auth): XYZ-123 add JWT token validation
```

## See Also

- [Commit Workflow Guide](../guides/commit-workflow.md) - Step-by-step usage guide
- [Code Reviewer Command](code-reviewer.md) - Review code before committing
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
