# Quick Start Guide

## Installation

### Binary Installation (Recommended)

**Linux/macOS:**
```bash
curl -fsSL https://devo.heyedu.dev/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://devo.heyedu.dev/install.ps1 | iex
```

### Verify Installation

```bash
devo --version
devo --help
```

## First Steps

### 1. Configure AWS Credentials

```bash
# If you don't have AWS CLI configured
aws configure

# Or use AWS SSO
devo aws-login configure
devo aws-login
```

### 2. Setup Shell Autocompletion

```bash
devo autocomplete --install
source ~/.bashrc  # or ~/.zshrc
```

### 3. Try AI Features

```bash
# Make some changes to your code
git add .

# Generate commit message
devo commit

# Review code changes
devo code-reviewer
```

## Common Workflows

### Daily Development

```bash
# 1. Make code changes
# ... edit files ...

# 2. Stage changes
git add .

# 3. Generate commit message and commit
devo commit

# 4. Push changes
devo commit -p

# 5. Create PR
devo commit -pr
```

### AWS Operations

```bash
# Login to AWS
devo aws-login

# Export DynamoDB table
devo dynamodb export my-table

# Connect to database via SSM
devo ssm database connect my-db

# Manage EventBridge rules
devo eventbridge list
devo eventbridge enable my-rule
```

### Configuration

```bash
# View current config
devo config show

# Change Bedrock model
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Change AWS region
devo config set aws.region us-west-2

# Backup configuration
devo config export ~/devo-config-backup.json
```

## For Developers

### One Command Setup

```bash
./setup-dev.sh
```

That's it! This single command will:
1. ✅ Create virtual environment
2. ✅ Install CLI in development mode
3. ✅ Install all dependencies
4. ✅ Setup shell autocompletion
5. ✅ Refresh shell cache

### Verify Installation

```bash
# Check CLI works
devo --help

# Try tab completion
devo <TAB>

# Run tests
make test
```

## Daily Development Workflow

```bash
# 1. Make changes
# ... edit files ...

# 2. Refresh
make refresh

# 3. Test
devo <command>
make test

# 4. Lint
make lint

# 5. Commit
devo commit
```

## Common Commands

```bash
make help          # Show all available commands
make refresh       # Refresh after code changes
make test          # Run tests
make lint          # Check code style
make format        # Format code
devo commit        # Generate commit message
```

## Need Help?

- Run `make help` for all commands
- Check `docs/contributing.md` for detailed guide
- See `README.md` for full documentation
- Visit [Full Documentation](https://devo.heyedu.dev)

## Quick Command Reference

| Command | Description |
|---------|-------------|
| `devo commit` | AI commit message generation |
| `devo code-reviewer` | AI code review |
| `devo aws-login` | AWS SSO authentication |
| `devo dynamodb list` | List DynamoDB tables |
| `devo ssm database connect` | Connect to database |
| `devo config show` | Show configuration |
| `devo upgrade` | Update to latest version |

See [Command Reference](./docs/commands.md) for complete list.

You're ready to go! 🚀
