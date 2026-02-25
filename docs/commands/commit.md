# devo commit

Generate conventional commit messages from staged git changes using AI.

## Overview

The `commit` command analyzes your staged changes and generates a properly formatted conventional commit message following the format:

```
<type>(<scope>): <summary>
```

## Features

- Extracts ticket numbers from branch names (e.g., `feature/XYZ-123-description`)
- Analyzes git diff to understand changes
- Generates semantic commit types (feat, fix, chore, etc.)
- Follows 50-character limit for summary line
- Uses AWS Bedrock (Claude 3.7 Sonnet) for intelligent analysis

## Usage

::: mkdocs-click
    :module: cli_tool.commands.commit_prompt
    :command: commit
    :prog_name: devo
    :depth: 1

## Commit Types

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

## Examples

```bash
# Generate commit message for staged changes
git add .
devo commit

# Example output:
# feat(auth): XYZ-123 add JWT token validation
```

## Branch Naming Convention

For automatic ticket extraction, use this branch format:

```
feature/XYZ-<ticket_number>-description
```

Example: `feature/XYZ-456-user-authentication`
