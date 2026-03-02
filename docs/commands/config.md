# devo config

Manage Devo CLI configuration settings.

## Overview

The `config` command allows you to view, modify, and manage your Devo CLI configuration. Configuration is stored in `~/.devo/config.json` and includes settings for Bedrock, GitHub, CodeArtifact, SSM, DynamoDB, and version checking.

## Subcommands

### show

Display configuration settings.

```bash
# Show all configuration
devo config show

# Show specific section
devo config show --section ssm
devo config show -s dynamodb

# Show as JSON
devo config show --json
```

### sections

List all available configuration sections.

```bash
devo config sections
```

### set

Set a configuration value using dot notation.

```bash
devo config set <key> <value>
```

Examples:

```bash
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
devo config set version_check.enabled false
```

### path

Show the path to the configuration file.

```bash
devo config path
```

### reset

Reset configuration to default values.

```bash
devo config reset
```

**Warning:** This will delete your current configuration and restore defaults.

### export

Export configuration to a file or stdout.

```bash
# Export to stdout
devo config export

# Export to file
devo config export -o backup.json
devo config export --output ~/backups/config.json

# Export specific sections
devo config export -s ssm
devo config export --section ssm --section dynamodb -o partial.json
```

### import

Import configuration from a file.

```bash
devo config import <filename> [--merge]
```

Options:

- `--merge` - Merge with existing configuration instead of replacing

Examples:

```bash
# Replace current config
devo config import backup.json

# Merge with existing
devo config import team-config.json --merge
```

### migrate

Migrate legacy configuration files to consolidated format.

```bash
devo config migrate
```

This migrates:

- `~/.devo/ssm-config.json` → `ssm` section
- `~/.devo/dynamodb/export_templates.json` → `dynamodb` section

## Configuration Sections

### Bedrock Settings

- `bedrock.model_id` - Primary Bedrock model ID
- `bedrock.fallback_model_id` - Fallback model ID

### GitHub Settings

- `github.repo_owner` - Repository owner/organization
- `github.repo_name` - Repository name

### CodeArtifact Settings

- `codeartifact.region` - CodeArtifact region
- `codeartifact.account_id` - Account ID
- `codeartifact.sso_url` - SSO URL
- `codeartifact.required_role` - Required role
- `codeartifact.domains` - List of domain configurations

### SSM Settings

- `ssm.databases` - Database connection configurations
- `ssm.instances` - EC2 instance configurations

### DynamoDB Settings

- `dynamodb.export_templates` - Saved export filter templates

### Version Check Settings

- `version_check.enabled` - Enable automatic version checks (default: true)

## Examples

### View Configuration

```bash
# Show all settings
devo config show

# Show specific section
devo config show --section ssm

# List available sections
devo config sections

# Show config file location
devo config path
```

### Modify Settings

```bash
# Use different Bedrock model
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Disable version checks
devo config set version_check.enabled false

# Update GitHub repository
devo config set github.repo_owner myorg
devo config set github.repo_name my-cli
```

### Export and Import

```bash
# Export full config to file
devo config export -o backup.json

# Export specific sections
devo config export -s ssm -s dynamodb -o partial.json

# Import and replace
devo config import backup.json

# Import and merge
devo config import team-config.json --merge
```

### Backup and Restore

```bash
# Backup current configuration
devo config export -o ~/backups/devo-config-$(date +%Y%m%d).json

# Make changes
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Restore from backup
devo config import ~/backups/devo-config-20260301.json
```

### Share Team Configuration

```bash
# Export SSM configs to share with team
devo config export -s ssm -o ssm-team-config.json

# Team members can import and merge
devo config import ssm-team-config.json --merge
```

### Migrate Legacy Configs

```bash
# Migrate old config files
devo config migrate

# Verify migration
devo config show
```

## Configuration File Format

The configuration file is JSON format located at `~/.devo/config.json`:

```json
{
  "bedrock": {
    "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "fallback_model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  },
  "github": {
    "repo_owner": "edu526",
    "repo_name": "devo-cli"
  },
  "codeartifact": {
    "region": "us-east-1",
    "account_id": "123456789012",
    "sso_url": "https://my-org.awsapps.com/start",
    "required_role": "Developer",
    "domains": [
      {
        "domain": "my-domain",
        "repository": "npm",
        "namespace": "@myorg"
      }
    ]
  },
  "ssm": {
    "databases": {
      "my-db": {
        "host": "localhost",
        "port": 5432,
        "instance_id": "i-1234567890abcdef0",
        "remote_port": 5432,
        "profile": "production"
      }
    },
    "instances": {
      "my-instance": {
        "instance_id": "i-1234567890abcdef0",
        "profile": "production"
      }
    }
  },
  "dynamodb": {
    "export_templates": {
      "users-active": {
        "table_name": "users",
        "filter_expression": "attribute_exists(#status) AND #status = :active",
        "expression_attribute_names": {
          "#status": "status"
        },
        "expression_attribute_values": {
          ":active": "active"
        }
      }
    }
  },
  "version_check": {
    "enabled": true
  }
}
```

## Environment Variables

Environment variables override configuration file values:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `AWS_SSO_URL`
- `AWS_REQUIRED_ROLE`
- `BEDROCK_MODEL_ID`
- `GITHUB_REPO_OWNER`
- `GITHUB_REPO_NAME`
- `DEVO_SKIP_VERSION_CHECK`

## Troubleshooting

### Configuration Not Loading

```bash
# Check file exists
devo config path

# View current config
devo config show

# Reset if corrupted
devo config reset
```

### Migrating from Old Config Files

If you have legacy configuration files:

```bash
# Migrate automatically
devo config migrate

# Verify migration
devo config show -s ssm
devo config show -s dynamodb
```

### Invalid Values

```bash
# View specific section
devo config show --section bedrock

# Reset to defaults
devo config reset
```

## See Also

- [Configuration Guide](../getting-started/configuration.md) - Detailed configuration documentation
- [Environment Variables](../reference/environment.md) - Environment variable reference
- [Troubleshooting](../reference/troubleshooting.md) - Common issues
