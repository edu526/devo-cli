# Configuration Guide

This document describes all configuration options available in Devo CLI.

## Configuration File

Devo CLI uses a JSON configuration file located at `~/.devo/config.json`.

The configuration file is automatically created with default values on first run. You can manage it using the `devo config` command.

## Configuration Commands

### View Configuration

```bash
# Show all configuration
devo config show

# Show specific section
devo config show --section ssm
devo config show -s dynamodb

# Show as JSON
devo config show --json

# List available sections
devo config sections

# Show config file path
devo config path
```

### Modify Configuration

```bash
# Set a value (dot notation)
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
devo config set version_check.enabled false

# Reset to defaults
devo config reset

# Migrate legacy config files
devo config migrate
```

### Export/Import Configuration

```bash
# Export full configuration to stdout
devo config export --stdout

# Export to file
devo config export -o backup.json

# Export specific sections
devo config export -s ssm -s dynamodb
devo config export --section ssm --output ssm-config.json

# Import configuration (merges with existing by default)
devo config import backup.json

# Import and replace sections completely (instead of merging)
devo config import team-config.json -s ssm --replace
```

**Use cases:**

- Backup your configuration before making changes
- Share configuration templates with your team
- Sync configuration across multiple machines
- Restore configuration after reset
- Export specific sections for sharing (e.g., SSM configs)

## Configuration Structure

The configuration file is located at `~/.devo/config.json` and contains the following sections:

### CodeArtifact Configuration

```json
{
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
  }
}
```

- **region**: AWS region for CodeArtifact operations
- **account_id**: Required AWS account ID for authentication
- **sso_url**: AWS SSO URL for obtaining credentials
- **required_role**: Required IAM role name for operations
- **domains**: List of CodeArtifact registry configurations

### Bedrock Configuration

```json
{
  "bedrock": {
    "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "fallback_model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  }
}
```

- **model_id**: AWS Bedrock model ID for AI features
- **fallback_model_id**: Fallback model if primary fails

Available models:

- `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (Claude 3.7 Sonnet - default)
- `us.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4)

### GitHub Configuration

```json
{
  "github": {
    "repo_owner": "edu526",
    "repo_name": "devo-cli"
  }
}
```

- **repo_owner**: GitHub repository owner/organization
- **repo_name**: GitHub repository name

### SSM Configuration

```json
{
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
  }
}
```

- **databases**: Database connection configurations for port forwarding
- **instances**: EC2 instance configurations for SSM connections

### DynamoDB Configuration

```json
{
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
  }
}
```

- **export_templates**: Saved filter templates for DynamoDB exports

### Version Check Configuration

```json
{
  "version_check": {
    "enabled": true
  }
}
```

- **enabled**: Enable/disable automatic version checks

## Environment Variables

Environment variables override configuration file values:

- `AWS_REGION` - Override AWS region
- `AWS_ACCOUNT_ID` - Override AWS account ID
- `AWS_SSO_URL` - Override AWS SSO URL
- `AWS_REQUIRED_ROLE` - Override required role
- `BEDROCK_MODEL_ID` - Override Bedrock model ID
- `GITHUB_REPO_OWNER` - Override GitHub repo owner
- `GITHUB_REPO_NAME` - Override GitHub repo name
- `CODEARTIFACT_REGION` - Override CodeArtifact region
- `DEVO_SKIP_VERSION_CHECK` - Set to `1` to disable version checks

## Configuration Priority

Configuration is loaded in the following order (later sources override earlier ones):

1. Default values (hardcoded in `cli_tool/config.py`)
2. Configuration file (`~/.devo/config.json`)
3. Environment variables
4. Command-line arguments (where applicable)

## Migration from Legacy Configs

If you have existing configuration files in the old format, use the migrate command:

```bash
# Migrate from legacy files
devo config migrate

# This will migrate:
# - ~/.devo/ssm-config.json → ~/.devo/config.json (ssm section)
# - ~/.devo/dynamodb/export_templates.json → ~/.devo/config.json (dynamodb section)
```

The migrate command:

- Preserves existing data in the consolidated config
- Backs up legacy files before migration
- Only migrates if legacy files exist

## Examples

### Using Different Bedrock Model

```bash
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
```

### Disable Version Checks

```bash
devo config set version_check.enabled false
```

Or temporarily:

```bash
DEVO_SKIP_VERSION_CHECK=1 devo commit
```

### View Specific Configuration Section

```bash
# View SSM configuration
devo config show --section ssm

# View DynamoDB templates
devo config show -s dynamodb

# Export SSM config to share with team
devo config export -s ssm -o ssm-config.json
```

### Backup and Restore Configuration

```bash
# Backup current configuration
devo config export -o ~/backups/devo-config-$(date +%Y%m%d).json

# Restore from backup (merges with existing by default)
devo config import ~/backups/devo-config-20260301.json

# Import team configuration (merges with existing)
devo config import team-config.json
```

## Troubleshooting

### Configuration Not Loading

1. Check file exists: `devo config path`
2. View current config: `devo config show`
3. Reset to defaults: `devo config reset`

### Configuration File Corrupted

```bash
# Backup current config (if possible)
devo config export -o backup.json

# Reset to defaults
devo config reset

# Or manually delete and recreate
rm ~/.devo/config.json
devo config show  # Will create new default config
```

### Migrating from Old Config Files

If you have legacy config files (`~/.devo/ssm-config.json` or `~/.devo/dynamodb/export_templates.json`):

```bash
# Migrate automatically
devo config migrate

# Verify migration
devo config show
```

### AWS Profile Issues

For AWS profile selection and credentials:

1. List available profiles: `devo aws-login list`
2. Check profile status: `devo aws-login list`
3. Login to profile: `devo aws-login login production`
4. Verify credentials: `aws sts get-caller-identity --profile production`

### Bedrock Model Issues

1. Check model ID: `devo config show -s bedrock`
2. Verify model is available in your region
3. Try fallback model: `devo config set bedrock.model_id us.anthropic.claude-3-7-sonnet-20250219-v1:0`

## Security Best Practices

1. **Protect config file** - `chmod 600 ~/.devo/config.json`
2. **Don't share config** - Contains account-specific information
3. **Use AWS SSO** - Preferred over long-term credentials
4. **Rotate credentials** - Update AWS credentials periodically
5. **Limit IAM permissions** - Follow principle of least privilege

## See Also

- [Configuration Reference](../reference/configuration.md) - Complete configuration options
- [Configuration Reference](../reference/configuration.md#environment-variables) - Environment variable reference
- [AWS Setup Guide](../guides/aws-setup.md) - AWS credentials setup
- [Development Guide](../development/setup.md) - Development environment setup
