# Commit Message Generator

AI-powered conventional commit message generation using AWS Bedrock.

## Structure

```
cli_tool/commands/commit/
├── __init__.py              # Public API exports
├── README.md                # This file
├── commands/                # CLI command definitions
│   ├── __init__.py          # Command registration
│   └── generate.py          # Main commit command
└── core/                    # Business logic
    ├── __init__.py
    └── generator.py         # CommitMessageGenerator
```

## Usage

```bash
# Generate commit message from staged changes
devo commit

# Add all changes and commit
devo commit -a

# Commit and push
devo commit -p

# Commit, push, and open PR
devo commit -pr

# Do everything in sequence
devo commit -A

# Use specific AWS profile
devo --profile production commit
```

## Options

- `-a, --add` - Add all changes before committing
- `-p, --push` - Push to current branch after committing
- `-pr, --pull-request` - Open browser to create GitHub PR
- `-A, --all` - Execute add, commit, push, and PR in sequence
- `--profile TEXT` - AWS profile to use for Bedrock

## Features

- AI-powered commit message generation using Claude 3.7 Sonnet
- Conventional commit format (`<type>(<scope>): <summary>`)
- Automatic ticket number extraction from branch names
- Multi-line descriptions for complex changes
- Interactive confirmation before committing
- Git workflow automation (add, commit, push, PR)

## Commit Format

Generated commits follow the Conventional Commits specification:

```
<type>(<scope>): <summary>

<body>

<footer>
```

### Types
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes (formatting, etc.)
- `refactor` - Code refactoring
- `perf` - Performance improvements
- `test` - Test changes
- `chore` - Build process or auxiliary tool changes

### Examples

```
feat(auth): add OAuth2 authentication

Implement OAuth2 flow with Google and GitHub providers.
Add token refresh mechanism and session management.

Closes #123
```

```
fix(api): resolve race condition in user creation

Add mutex lock to prevent duplicate user records when
concurrent requests are made to the registration endpoint.
```

## Architecture

### Commands Layer (`commands/`)
- `generate.py`: CLI command with Click decorators
- User interaction and confirmation
- Git workflow orchestration
- Output formatting with Rich

### Core Layer (`core/`)
- `generator.py`: CommitMessageGenerator class
- AI integration with AWS Bedrock
- Git diff analysis
- Commit message generation logic
- No Click dependencies

## Configuration

Uses configuration from `~/.devo/config.json`:

```json
{
  "bedrock": {
    "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "region": "us-east-1"
  },
  "aws": {
    "region": "us-east-1"
  }
}
```

## Requirements

- Git repository with staged changes
- AWS credentials configured
- AWS Bedrock access with Claude model permissions

## Workflow

1. Reads staged git changes (`git diff --cached`)
2. Extracts ticket number from branch name (e.g., `feature/ABC-123-description`)
3. Sends diff to AWS Bedrock for analysis
4. Generates conventional commit message
5. Shows preview and asks for confirmation
6. Commits changes with generated message
7. Optionally pushes and opens PR

## Error Handling

- No staged changes: Prompts to stage changes first
- No AWS credentials: Shows configuration instructions
- Bedrock API errors: Displays error message and exits
- Git errors: Shows git error output
