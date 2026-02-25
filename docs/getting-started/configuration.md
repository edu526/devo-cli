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

# Get specific value
devo config get aws.region
devo config get bedrock.model_id
```

### Modify Configuration

```bash
# Set a value
devo config set aws.region us-west-2
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
devo config set version_check.enabled false

# Edit in your default editor
devo config edit

# Show config file path
devo config path

# Validate configuration
devo config validate

# Reset to defaults
devo config reset
```

### Export/Import Configuration

```bash
# Export configuration to a file
devo config export my-config.json
devo config export ~/backup/devo-config-$(date +%Y%m%d).json

# Import configuration (replaces current)
devo config import my-config.json

# Import and merge with existing configuration
devo config import team-config.json --merge
```

**Use cases:**
- Backup your configuration before making changes
- Share configuration templates with your team
- Sync configuration across multiple machines
- Restore configuration after reset

## Configuration Structure

### AWS Configuration

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

- **region**: AWS region for all AWS operations
- **account_id**: Required AWS account ID for authentication
- **sso_url**: AWS SSO URL for obtaining credentials
- **required_role**: Required IAM role name for operations

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
- **account_id**: AWS account ID
- **sso_url**: AWS SSO URL for authentication
- **required_role**: Required IAM role name
- **domains**: List of CodeArtifact registry configurations
  - **domain**: Domain name
  - **repository**: Repository name
  - **namespace**: NPM namespace

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

## Examples

### Custom AWS Configuration

```bash
devo config set aws.region eu-west-1
devo config set aws.account_id 123456789012
devo config set aws.sso_url https://mycompany.awsapps.com/start
devo config set aws.required_role Developer
```

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

### Custom GitHub Repository

```bash
devo config set github.repo_owner myorg
devo config set github.repo_name my-custom-cli
```

### Add CodeArtifact Registry

```bash
# List current registries
devo config registry list

# Add a new registry
devo config registry add --domain my-domain --repository my-repo --namespace @myorg

# Remove a registry by index
devo config registry remove 2
```

Or edit the configuration file directly:

```bash
devo config edit
```

Then add a new registry to the `codeartifact.domains` array:

```json
{
  "domain": "my-domain",
  "repository": "my-repo",
  "namespace": "@myorg"
}
```

## Troubleshooting

### Configuration Not Loading

1. Check file exists: `devo config path`
2. Validate configuration: `devo config validate`
3. Reset to defaults: `devo config reset`

### Configuration File Corrupted

```bash
# Reset to defaults
devo config reset

# Or manually delete and recreate
rm ~/.devo/config.json
devo config show  # Will create new default config
```

### AWS Credentials Issues

1. Verify account ID: `devo config get aws.account_id`
2. Check SSO URL: `devo config get aws.sso_url`
3. Verify with AWS CLI: `aws sts get-caller-identity`

### Bedrock Model Issues

1. Check model ID: `devo config get bedrock.model_id`
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
- [Environment Variables](../reference/environment.md) - Environment variable reference
- [AWS Setup Guide](../guides/aws-setup.md) - AWS credentials setup
- [Development Guide](../development/setup.md) - Development environment setup
