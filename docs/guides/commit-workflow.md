# Commit Message Workflow

> For the full command reference, see [devo commit](../commands/commit.md).

Learn how to generate conventional commit messages using AI.

## Quick Start

```bash
# Stage your changes
git add .

# Generate commit message
devo commit
```

## Workflow

### 1. Make Your Changes

Edit your files as usual:

```bash
vim src/auth.py
vim tests/test_auth.py
```

### 2. Stage Changes

```bash
# Stage specific files
git add src/auth.py tests/test_auth.py

# Or stage all changes
git add .
```

### 3. Generate Commit Message

```bash
devo commit
```

The AI analyzes your staged changes and generates a commit message. See [devo commit](../commands/commit.md) for the full format specification and list of commit types.

### 4. Review and Commit

The tool shows the generated message. You can:

- Accept it and commit
- Edit it before committing
- Cancel and modify your changes

## Ticket Number Extraction

### Branch Naming Convention

Use this format for automatic ticket extraction:

```
<type>/<TICKET-NUMBER>-description
```

Examples:

- `feature/XYZ-123-user-authentication`
- `fix/ABC-456-login-bug`
- `chore/DEV-789-update-dependencies`

### How It Works

The tool extracts the ticket number from your branch name and includes it in the commit message:

```bash
# Branch: feature/XYZ-123-add-auth
# Generated message:
feat(auth): XYZ-123 add JWT token validation
```

## Complete Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/XYZ-123-add-authentication
```

### 2. Make Changes

```bash
vim src/auth.py
vim tests/test_auth.py
```

### 3. Review Code (Optional)

```bash
git add .
devo code-reviewer
```

### 4. Fix Issues and Stage

```bash
# Fix any issues found
vim src/auth.py

# Stage changes
git add .
```

### 5. Generate Commit Message

```bash
devo commit
```

### 6. Push Changes

```bash
git push origin feature/XYZ-123-add-authentication
```

## Tips for Better Commit Messages

1. **Stage related changes together**: Group related files for coherent messages
2. **Use descriptive branch names**: Include ticket numbers for automatic extraction
3. **Review before committing**: Run `devo code-reviewer` first
4. **Keep changes focused**: Smaller commits get better messages
5. **Edit if needed**: The generated message is a starting point

## Troubleshooting

### Generic Commit Message

For better messages:

- Use descriptive branch names with ticket numbers
- Stage related changes together
- Make focused, single-purpose commits

For errors related to missing staged changes or AWS credentials, see the [devo commit reference](../commands/commit.md).

## Next Steps

- [Code Review Workflow](code-review-workflow.md) - Review changes before committing
- [AWS Setup](aws-setup.md) - Configure AWS credentials
- [Commit Command Reference](../commands/commit.md) - Full command options
