# Commands Overview

Devo CLI provides several commands to enhance your development workflow.

## Core Commands

### [devo commit](commit.md)

Generate conventional commit messages from staged changes using AWS Bedrock.

```bash
devo commit [OPTIONS]
```

**Options:**

- `-p, --push` - Push the commit to the remote origin
- `-pr, --pull-request` - Open a pull request on GitHub
- `-a, --add` - Add all changes to the staging area before committing
- `-A, --all` - Perform add, commit, push, and open pull request

**Use when:** You have staged changes and want a properly formatted commit message.

(see also: [Commit Workflow](../guides/commit-workflow.md))

### [devo code-reviewer](code-reviewer.md)

Perform AI-driven code review with security and quality analysis.

```bash
devo code-reviewer [OPTIONS]
```

**Options:**

- `-b, --base-branch TEXT` - Base branch to compare against (default: auto-detect main/master)
- `-r, --repo-path TEXT` - Path to the Git repository (default: current directory)
- `-o, --output [json|table]` - Output format (table: rich tables, json: raw JSON)
- `-m, --show-metrics` - Include detailed execution metrics in the output
- `-f, --full-prompt` - Use full detailed prompt (default: optimized short prompt)

**Use when:** You want to review code changes before committing or merging.

(see also: [Code Review Workflow](../guides/code-review-workflow.md))

### [devo config](config.md)

Manage Devo CLI configuration.

```bash
devo config <subcommand> [OPTIONS]
```

**Subcommands:**

- `show` - Show current configuration
- `set` - Set a configuration value
- `export` - Export configuration (full or partial)
- `import` - Import configuration from file
- `reset` - Reset configuration to defaults
- `sections` - List all configuration sections
- `path` - Show configuration file path
- `migrate` - Migrate legacy config files to consolidated format

**Use when:** You need to view or modify configuration settings.

## AWS Integration

### [devo aws-login](aws-login.md)

Automate AWS SSO authentication and credential caching.

```bash
devo aws-login [COMMAND] [OPTIONS]
```

**Commands:**

- `login` - Login to AWS using SSO with a specific profile
- `list` - List all AWS profiles with detailed status
- `configure` - Configure a new SSO profile interactively
- `refresh` - Refresh expired or expiring credentials
- `set-default` - Set a profile as the default

**Use when:** You need to login to AWS using SSO without manually copying credentials.

### [devo codeartifact-login](codeartifact.md)

Authenticate with AWS CodeArtifact for private package management.

```bash
devo codeartifact-login [OPTIONS]
```

**Alias:** `ca-login`

**Use when:** You need to access private packages from CodeArtifact.

### [devo ssm](ssm.md)

AWS Systems Manager Session Manager commands for database and instance connections.

```bash
devo ssm <subcommand> [OPTIONS]
```

**Commands:**

- `connect` - Shortcut for 'devo ssm database connect'
- `shell` - Shortcut for 'devo ssm instance shell'
- `forward` - Manual port forwarding (without using config)
- `database` - Manage database connections
  - `connect` - Connect to a configured database (uses hostname forwarding)
  - `list` - List configured databases
  - `add` - Add a database configuration
  - `remove` - Remove a database configuration
- `instance` - Manage EC2 instance connections
  - `shell` - Connect to a configured instance via interactive shell
  - `list` - List configured instances
  - `add` - Add an instance configuration
  - `remove` - Remove an instance configuration
- `hosts` - Manage /etc/hosts entries for hostname forwarding
  - `setup` - Setup /etc/hosts entries for all configured databases
  - `list` - List all /etc/hosts entries managed by Devo CLI
  - `add` - Add a single database hostname to /etc/hosts
  - `remove` - Remove a database hostname from /etc/hosts
  - `clear` - Remove all Devo CLI managed entries from /etc/hosts

**Use when:** You need to connect to RDS, ElastiCache, or other AWS resources through a bastion instance.

(see also: [SSM Port Forwarding Guide](../guides/ssm-port-forwarding.md))

### [devo dynamodb](dynamodb.md)

DynamoDB table management and data export utilities.

```bash
devo dynamodb <subcommand> [OPTIONS]
```

**Commands:**

- `list` - List all DynamoDB tables in the region
- `describe` - Show detailed information about a table
- `export` - Export DynamoDB table to CSV, JSON, or JSONL format
- `list-templates` - List all saved export templates

**Use when:** You need to list, describe, or export DynamoDB tables.

(see also: [DynamoDB Export Guide](../guides/dynamodb-export.md))

### [devo eventbridge](eventbridge.md)

Check EventBridge scheduled rules status by environment.

```bash
devo eventbridge [OPTIONS]
```

**Options:**

- `-e, --env TEXT` - Filter by environment (e.g., dev, staging, prod)
- `-r, --region TEXT` - AWS region (default: us-east-1)
- `-s, --status [enabled|disabled|all]` - Filter by rule status
- `-o, --output [table|json]` - Output format (default: table)

**Use when:** You need to monitor EventBridge scheduled rules and their status.

## Utility Commands

### [devo upgrade](upgrade.md)

Update Devo CLI to the latest version.

```bash
devo upgrade [OPTIONS]
```

**Options:**

- `-f, --force` - Force upgrade without confirmation
- `-c, --check` - Check for updates without upgrading

**Use when:** You want to get the latest features and bug fixes.

### [devo autocomplete](completion.md)

Setup shell autocomplete for Devo CLI.

```bash
devo autocomplete [OPTIONS]
```

**Options:**

- `-i, --install` - Automatically install autocomplete to shell config
- `-y, --yes` - Skip confirmation prompt when installing

**Use when:** You want to enable tab completion for your shell.

## Command Categories

### Automation Features

- `commit` - Generate commit messages
- `code-reviewer` - Automated code review

### AWS Integration

- `aws-login` - AWS SSO authentication
- `codeartifact-login` - CodeArtifact authentication
- `ssm` - Session Manager port forwarding with hostname support
- `dynamodb` - DynamoDB table management (list, describe, export)
- `eventbridge` - EventBridge scheduled rules monitoring

### Utility Commands

- `upgrade` - Self-update
- `config` - Configuration management
- `autocomplete` - Shell completion

## Global Options

All commands support these global options:

```bash
--profile TEXT    AWS profile to use (must come before command)
-v, --version     Show the version and exit
--help           Show help message
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

### Commit with Options

```bash
# Add all changes, commit, and push
devo commit -A

# Commit and push
devo commit -p

# Commit, push, and open PR
devo commit -pr
```

### With AWS Profile

```bash
# Use specific AWS profile (must come before command)
devo --profile production aws-login
devo --profile staging dynamodb list
devo --profile dev ssm database connect mydb
```

### SSM Database Connection

```bash
# List databases
devo ssm database list

# Add a database
devo ssm database add

# Connect to database (with hostname forwarding)
devo ssm database connect mydb

# Setup /etc/hosts for all databases
devo ssm hosts setup

# Connect using shortcut
devo ssm connect mydb
```

### DynamoDB Operations

```bash
# List all tables
devo dynamodb list

# Describe a table
devo dynamodb describe my-table

# Export table to CSV
devo dynamodb export my-table --format csv --output data.csv

# Export with filter
devo dynamodb export my-table --filter "status = 'active'" --format json
```

### Configuration

```bash
# View current configuration
devo config show

# Set Bedrock model
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Export configuration
devo config export backup.json

# Import configuration
devo config import backup.json
```

## Getting Help

Get help for any command:

```bash
# General help
devo --help

# Command-specific help
devo commit --help
devo code-reviewer --help
devo ssm database --help
devo ssm database connect --help
```

## Next Steps

- Explore individual command documentation
- Check [Configuration Guide](../getting-started/configuration.md)
- See [Troubleshooting](../reference/troubleshooting.md) for common issues
