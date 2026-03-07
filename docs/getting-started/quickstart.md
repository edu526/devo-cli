# Quick Start Guide

Get up and running with Devo CLI in 5 minutes.

## Step 1 — Install

=== "Linux/macOS"

    ```bash
    curl -fsSL https://devo.heyedu.dev/install.sh | bash
    ```

=== "Windows (PowerShell)"

    ```powershell
    irm https://devo.heyedu.dev/install.ps1 | iex
    ```

## Step 2 — Configure AWS

Devo CLI uses AWS Bedrock for AI features. You need valid AWS credentials:

```bash
# Option A: AWS SSO (recommended) — configure once, then use devo aws-login daily
aws configure sso              # first-time profile setup
devo aws-login login           # login (opens browser)
devo aws-login refresh         # refresh expired credentials without browser

# Option B: Access keys
aws configure
```

→ See the [AWS Setup Guide](../guides/aws-setup.md) for detailed setup including Bedrock model access.

## Step 3 — Verify

```bash
devo --version
devo --help
```

## Step 4 — First Commands

### Generate a Commit Message

```bash
# Stage your changes
git add .

# Generate AI-powered commit message
devo commit
```

### Review Your Branch

```bash
# Review current branch vs main/master
devo code-reviewer
```

### Check Configuration

```bash
devo config show
```

## Enable Shell Completion (Optional)

Add to your shell configuration file:

=== "Zsh (~/.zshrc)"

    ```bash
    eval "$(_DEVO_COMPLETE=zsh_source devo)"
    ```

=== "Bash (~/.bashrc)"

    ```bash
    eval "$(_DEVO_COMPLETE=bash_source devo)"
    ```

=== "Fish (~/.config/fish/config.fish)"

    ```bash
    _DEVO_COMPLETE=fish_source devo | source
    ```

Then restart your terminal or run `source ~/.zshrc` (or equivalent).

## Daily Workflow

```bash
# 1. Work on your feature branch
git checkout -b feature/my-feature

# 2. Refresh AWS credentials if expired
devo aws-login refresh

# 3. Make changes, then stage
git add .

# 4. Review branch before committing (optional)
devo code-reviewer

# 5. Generate commit message
devo commit

# 6. Push
git push
```

## Working with AWS Profiles

```bash
# Use specific AWS profile
devo --profile production commit

# Or set default for the session
export AWS_PROFILE=production
devo commit
```

## Update Devo CLI

```bash
devo upgrade
```

## Next Steps

- [AWS Setup](../guides/aws-setup.md) - Enable Bedrock model access and IAM permissions
- [Commit Workflow](../guides/commit-workflow.md) - Learn how commit message generation works
- [Code Review Workflow](../guides/code-review-workflow.md) - AI-powered code review
- [Commands Reference](../commands/index.md) - All available commands
- [Configuration](configuration.md) - Bedrock model, GitHub, CodeArtifact settings

## Troubleshooting

### Command Not Found

Restart your terminal or add to PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### AWS Credentials Error

See [AWS Setup Guide](../guides/aws-setup.md) or run:

```bash
aws sts get-caller-identity  # verify credentials
```

### Need Help?

```bash
devo --help
devo commit --help
```

See [Troubleshooting Guide](../reference/troubleshooting.md) for more help.
