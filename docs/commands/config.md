# devo config

Manage Devo CLI configuration settings.

## Overview

The `config` command allows you to view, modify, and manage your Devo CLI configuration. Configuration is stored in `~/.devo/config.json` and includes AWS settings, Bedrock model preferences, and other options.

## Subcommands

### show
Display all configuration settings.

```bash
devo config show
```

### get
Get a specific configuration value.

```bash
devo config get <key>
```

Examples:
```bash
devo config get aws.region
devo config get bedrock.model_id
devo config get version_check.enabled
```

### set
Set a configuration value.

```bash
devo config set <key> <value>
```

Examples:
```bash
devo config set aws.region us-west-2
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
devo config set version_check.enabled false
```

### edit
Open configuration file in your default editor.

```bash
devo config edit
```

### path
Show the path to the configuration file.

```bash
devo config path
```

### validate
Validate configuration file syntax and values.

```bash
devo config validate
```

### reset
Reset configuration to default values.

```bash
devo config reset
```

**Warning:** This will delete your current configuration.

### export
Export configuration to a file.

```bash
devo config export <filename>
```

Examples:
```bash
devo config export backup.json
devo config export ~/backups/devo-config-$(date +%Y%m%d).json
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
devo config import backup.json
devo config import team-config.json --merge
```

### registry list
List all configured CodeArtifact registries.

```bash
devo config registry list
```

### registry add
Add a new CodeArtifact registry.

```bash
devo config registry add --domain <domain> --repository <repo> --namespace <namespace>
```

Example:
```bash
devo config registry add --domain my-domain --repository npm --namespace @myorg
```

### registry remove
Remove a CodeArtifact registry by index.

```bash
devo config registry remove <index>
```

Example:
```bash
# List registries to see indices
devo config registry list

# Remove registry at index 2
devo config registry remove 2
```

## Configuration Keys

### Bedrock Settings

- `bedrock.model_id` - Primary Bedrock model ID
- `bedrock.fallback_model_id` - Fallback model ID
- `bedrock.region` - AWS region for Bedrock

### GitHub Settings

- `github.repo_owner` - Repository owner/organization
- `github.repo_name` - Repository name

### CodeArtifact Settings

- `codeartifact.region` - CodeArtifact region
- `codeartifact.account_id` - Account ID
- `codeartifact.sso_url` - SSO URL
- `codeartifact.required_role` - Required role
- `codeartifact.domains` - List of domain configurations (managed via `registry` subcommands)

### Version Check Settings

- `version_check.enabled` - Enable automatic version checks (default: true)

## Examples

### View Configuration

```bash
# Show all settings
devo config show

# Get specific value
devo config get bedrock.model_id
```

### Modify Settings

```bash
# Change Bedrock region
devo config set bedrock.region us-west-2

# Use different Bedrock model
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Disable version checks
devo config set version_check.enabled false

# Update GitHub repository
devo config set github.repo_owner myorg
devo config set github.repo_name my-cli
```

### Manage CodeArtifact Registries

```bash
# List all registries
devo config registry list

# Add a new registry
devo config registry add --domain my-domain --repository npm --namespace @myorg

# Remove a registry
devo config registry remove 2
```

### Backup and Restore

```bash
# Export current configuration
devo config export backup.json

# Make changes
devo config set aws.region us-west-2

# Restore from backup
devo config import backup.json
```

### Team Configuration

```bash
# Export team configuration template
devo config export team-template.json

# Share with team members
# They can import it:
devo config import team-template.json --merge
```

### Edit Manually

```bash
# Open in editor
devo config edit

# Or edit directly
nano ~/.devo/config.json
```

## Configuration File Format

The configuration file is JSON format:

```json
{
  "bedrock": {
    "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "fallback_model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "region": "us-east-1"
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

# Validate syntax
devo config validate

# Reset if corrupted
devo config reset
```

### Invalid Values

```bash
# Validate configuration
devo config validate

# Check specific value
devo config get aws.region
```

## See Also

- [Configuration Guide](../getting-started/configuration.md) - Detailed configuration documentation
- [Environment Variables](../reference/environment.md) - Environment variable reference
- [Troubleshooting](../reference/troubleshooting.md) - Common issues
