# devo commit

Generate conventional commit messages from staged git changes using AI.

## Synopsis

```bash
devo commit [OPTIONS]
```

## Description

Analyzes staged git changes and generates a properly formatted conventional commit message. Uses AWS Bedrock AI to understand code changes and create semantic commit messages following the Conventional Commits format.

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--push` | `-p` | Push the commit to the remote origin |
| `--pull-request` | `-pr` | Open a pull request on GitHub |
| `--add` | `-a` | Add all changes to the staging area before committing |
| `--all` | `-A` | Perform add, commit, push, and open pull request |
| `--help` | | Show help message and exit |

## Commit Message Format

Generated messages follow the Conventional Commits specification:

```
<type>(<scope>): <summary>

[optional body]

[optional footer]
```

### Commit Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(auth): add SSO login support` |
| `fix` | Bug fix | `fix(api): handle null response from endpoint` |
| `chore` | Maintenance tasks | `chore(deps): update boto3 to 1.34.0` |
| `docs` | Documentation changes | `docs(readme): add installation instructions` |
| `refactor` | Code refactoring | `refactor(parser): simplify token extraction` |
| `test` | Test additions or modifications | `test(auth): add SSO login tests` |
| `style` | Code style changes | `style(format): apply black formatting` |
| `perf` | Performance improvements | `perf(query): optimize database query` |
| `ci` | CI/CD changes | `ci(github): add release workflow` |
| `build` | Build system changes | `build(docker): update base image` |

### Scope

The scope is optional and indicates the area of the codebase affected:

- `auth` - Authentication
- `api` - API endpoints
- `cli` - CLI interface
- `config` - Configuration
- `deps` - Dependencies
- `db` - Database
- etc.

### Ticket Extraction

The command automatically extracts ticket numbers from branch names:

**Branch name:** `feature/JIRA-123-add-login`
**Generated footer:** `Refs: JIRA-123`

Supported patterns:

- `JIRA-123`
- `PROJ-456`
- `ABC-789`
- Any `[A-Z]+-[0-9]+` pattern

## Requirements

- Git repository with staged changes
- AWS credentials configured
- AWS Bedrock access (Claude model)

## Configuration

The command uses the Bedrock model configured in your Devo CLI settings:

```bash
# View current model
devo config show bedrock.model_id

# Change model
devo config set bedrock.model_id us.anthropic.claude-3-7-sonnet-20250219-v1:0
```

## Examples

### Simple Commit

```bash
git add src/auth.py
devo commit
```

### Commit and Push

```bash
git add .
devo commit --push
```

### Full Workflow (add, commit, push, PR)

```bash
devo commit --all
```

### With AWS Profile

```bash
devo --profile production commit
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (no staged changes, AWS error, user cancelled, etc.) |

## See Also

- [Commit Workflow Guide](../guides/commit-workflow.md)
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [devo code-reviewer](code-reviewer.md) - Review code before committing
