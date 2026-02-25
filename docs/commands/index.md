# Commands Overview

Devo CLI provides several commands to enhance your development workflow.

## Core Commands

### [devo commit](commit.md)
Generate AI-powered conventional commit messages from staged changes.

```bash
devo commit [OPTIONS]
```

**Use when:** You have staged changes and want a properly formatted commit message.

### [devo code-reviewer](code-reviewer.md)
Perform AI-driven code review with security and quality analysis.

```bash
devo code-reviewer [OPTIONS]
```

**Use when:** You want to review code changes before committing or merging.

### [devo config](config.md)
Manage Devo CLI configuration.

```bash
devo config <subcommand> [OPTIONS]
```

**Use when:** You need to view or modify configuration settings.

## AWS Integration

### [devo codeartifact-login](codeartifact.md)
Authenticate with AWS CodeArtifact for private package management.

```bash
devo codeartifact-login
```

**Use when:** You need to access private packages from CodeArtifact.

### [devo ssm](ssm.md)
AWS Systems Manager Session Manager port forwarding with hostname support.

```bash
devo ssm <subcommand> [OPTIONS]
```

**Subcommands:**
- `connect` - Connect to a configured database
- `connect-with-hosts` - Connect using real hostname
- `connect-all-with-hosts` - Connect to all databases with hostname forwarding
- `list` - List configured databases
- `add-db` - Add database configuration
- `remove-db` - Remove database configuration
- `hosts-setup` - Setup /etc/hosts entries for all databases
- `hosts-list` - List managed hosts entries
- `export` - Export configuration
- `import` - Import configuration

**Use when:** You need to connect to RDS, ElastiCache, or other AWS resources through a bastion instance.

### [devo dynamodb](dynamodb.md)
DynamoDB table management and data export utilities.

```bash
devo dynamodb <subcommand> [OPTIONS]
```

**Subcommands:**
- `list` - List all DynamoDB tables
- `describe` - Show table details
- `export` - Export table data to CSV/JSON/JSONL
- `list-templates` - List saved export templates

**Use when:** You need to list, describe, or export DynamoDB tables.

### [devo eventbridge](eventbridge.md)
Check EventBridge scheduled rules status by environment.

```bash
devo eventbridge [OPTIONS]
```

**Use when:** You need to monitor EventBridge scheduled rules and their status.

## Utility Commands

### [devo upgrade](upgrade.md)
Update Devo CLI to the latest version.

```bash
devo upgrade [OPTIONS]
```

**Use when:** You want to get the latest features and bug fixes.

### [devo completion](completion.md)
Generate shell completion scripts.

```bash
devo completion [SHELL]
```

**Use when:** You want to enable tab completion for your shell.

## Command Categories

### AI-Powered Features
- `commit` - Generate commit messages
- `code-reviewer` - Automated code review

### AWS Integration
- `codeartifact-login` - CodeArtifact authentication
- `ssm` - Session Manager port forwarding with hostname support
- `dynamodb` - DynamoDB table management (list, describe, export)
- `eventbridge` - EventBridge scheduled rules monitoring

### Utility Commands
- `upgrade` - Self-update
- `config` - Configuration management
- `completion` - Shell completion

## Global Options

All commands support these global options:

```bash
--profile TEXT    AWS profile to use
--help           Show help message
--version        Show version
```

## Examples

### Basic Workflow

```bash
# 1. Make changes
git add .

# 2. Generate commit message
devo commit

# 3. Review code
devo code-reviewer

# 4. Push changes
git push
```

### With AWS Profile

```bash
# Use specific AWS profile
devo --profile production commit
devo --profile staging code-reviewer
```

### Configuration

```bash
# View current configuration
devo config show

# Set Bedrock model
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Export configuration
devo config export backup.json
```

## Getting Help

Get help for any command:

```bash
# General help
devo --help

# Command-specific help
devo commit --help
devo code-reviewer --help
devo config --help
```

## Next Steps

- Explore individual command documentation
- Check [Configuration Guide](../getting-started/configuration.md)
- See [Troubleshooting](../reference/troubleshooting.md) for common issues
