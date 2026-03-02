# Configuration Management

Centralized configuration management for Devo CLI.

## Structure

```
cli_tool/commands/config_cmd/
├── __init__.py              # Public API exports
├── README.md                # This file
└── commands/                # CLI command definitions
    ├── __init__.py          # Command registration
    ├── show.py              # Show configuration
    ├── set.py               # Set configuration value
    ├── get.py               # Get configuration value
    ├── export.py            # Export configuration
    ├── import_cmd.py        # Import configuration
    ├── reset.py             # Reset configuration
    ├── path.py              # Show config file path
    ├── sections.py          # List configuration sections
    └── migrate.py           # Migrate old configurations
```

## Usage

```bash
# Show all configuration
devo config show

# Show specific section
devo config show bedrock
devo config show aws

# Get specific value
devo config get bedrock.model_id
devo config get aws.region

# Set configuration value
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
devo config set aws.region us-west-2

# List all sections
devo config sections

# Show config file path
devo config path

# Export configuration
devo config export backup.json
devo config export ~/backups/config-$(date +%Y%m%d).json

# Import configuration
devo config import backup.json

# Reset to defaults
devo config reset
devo config reset --yes  # Skip confirmation
```

## Configuration File

Location: `~/.devo/config.json`

Default structure:

```json
{
  "bedrock": {
    "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "region": "us-east-1"
  },
  "aws": {
    "region": "us-east-1"
  },
  "codeartifact": {
    "domain": "devo-ride",
    "repository": "pypi",
    "region": "us-east-1"
  },
  "ssm": {
    "databases": {},
    "instances": {},
    "hosts": {}
  },
  "dynamodb": {
    "templates": {}
  }
}
```

## Features

- Centralized configuration storage
- Nested key access with dot notation
- JSON export/import for backups
- Configuration validation
- Default values
- Section-based organization

## Architecture

### Commands Layer (`commands/`)
All command files contain both CLI interface and business logic:
- Click decorators for CLI
- Direct configuration file manipulation
- Rich output formatting
- User interaction and confirmation

## Configuration Sections

### bedrock
AWS Bedrock configuration for AI features:
- `model_id` - Claude model identifier
- `region` - AWS region for Bedrock

### aws
General AWS configuration:
- `region` - Default AWS region

### codeartifact
CodeArtifact repository settings:
- `domain` - CodeArtifact domain
- `repository` - Repository name
- `region` - AWS region

### ssm
SSM Session Manager configurations:
- `databases` - Database connection configs
- `instances` - EC2 instance configs
- `hosts` - /etc/hosts entries

### dynamodb
DynamoDB settings:
- `templates` - Saved export templates

## Examples

### Change Bedrock Model

```bash
# Use Claude Sonnet 4
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0

# Verify change
devo config get bedrock.model_id
```

### Backup Configuration

```bash
# Export current config
devo config export ~/backups/devo-config-backup.json

# Later, restore from backup
devo config import ~/backups/devo-config-backup.json
```

### Reset After Issues

```bash
# Reset to defaults
devo config reset

# Reconfigure as needed
devo config set aws.region us-west-2
```
