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

## Usage

### Basic Usage

```bash
# Stage your changes
git add .

# Generate commit message
devo commit
```

The command will:

1. Analyze staged changes
2. Generate a commit message using AI
3. Show the message for review
4. Prompt for confirmation
5. Create the commit

### With Options

```bash
# Add all changes and commit
devo commit --add

# Commit and push
devo commit --push

# Commit, push, and open PR
devo commit --pull-request

# Do everything (add, commit, push, PR)
devo commit --all
```

### Interactive Flow

```bash
$ devo commit

Analyzing staged changes...

Generated commit message:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
feat(auth): add AWS SSO authentication support

- Implement SSO login flow with browser authentication
- Add credential caching for 8-hour sessions
- Support multiple AWS profiles
- Auto-refresh expiring credentials

Refs: JIRA-123
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use this commit message? [Y/n]: y

✓ Commit created successfully
```

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
# Stage changes
git add src/auth.py

# Generate and commit
devo commit
```

### Commit and Push

```bash
git add .
devo commit --push
```

### Full Workflow

```bash
# Add all changes, commit, push, and open PR
devo commit --all
```

### With AWS Profile

```bash
# Use specific AWS profile for Bedrock
devo --profile production commit
```

## Best Practices

1. **Stage related changes**: Only stage changes related to a single logical change
2. **Review the message**: Always review the generated message before confirming
3. **Edit if needed**: You can edit the message before confirming
4. **Use meaningful branches**: Include ticket numbers in branch names for automatic refs

## Troubleshooting

### No staged changes

```
Error: No staged changes found
```

**Solution:** Stage your changes first:

```bash
git add <files>
# or
devo commit --add
```

### AWS credentials not configured

```
Error: AWS credentials not found
```

**Solution:** Configure AWS credentials:

```bash
devo aws-login
```

### Bedrock access denied

```
Error: Access denied to Bedrock model
```

**Solution:** Ensure your AWS account has Bedrock access and the model is enabled in your region.

## Features

- **AI-Powered**: Uses Claude to understand code changes
- **Conventional Commits**: Follows industry standard format
- **Ticket Extraction**: Automatically extracts ticket numbers from branch names
- **Multi-line Support**: Generates detailed commit bodies when needed
- **Interactive**: Review and edit before committing
- **Workflow Integration**: Options for push and PR creation

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (no staged changes, AWS error, user cancelled, etc.) |

## See Also

- [Commit Workflow Guide](../guides/commit-workflow.md) - Complete workflow guide
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [devo code-reviewer](code-reviewer.md) - Review code before committing

## Notes

- Requires staged changes in git
- Uses AWS Bedrock (Claude model)
- Follows Conventional Commits specification
- Supports ticket number extraction from branch names
- Interactive confirmation before committing
