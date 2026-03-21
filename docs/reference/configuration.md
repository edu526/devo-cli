# Configuration Reference

Complete reference for all Devo CLI configuration options and environment variables.

## Configuration File

Location: `~/.devo/config.json`

```json
{
  "aws": {
    "region": "string",
    "account_id": "string",
    "sso_url": "string",
    "required_role": "string"
  },
  "bedrock": {
    "model_id": "string",
    "fallback_model_id": "string"
  },
  "github": {
    "repo_owner": "string",
    "repo_name": "string"
  },
  "codeartifact": {
    "region": "string",
    "account_id": "string",
    "sso_url": "string",
    "required_role": "string",
    "domains": [
      {
        "domain": "string",
        "repository": "string",
        "namespace": "string"
      }
    ]
  },
  "version_check": {
    "enabled": boolean
  }
}
```

### AWS

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `aws.region` | string | `us-east-1` | AWS region for all operations |
| `aws.account_id` | string | `123456789012` | 12-digit AWS account ID |
| `aws.sso_url` | string | `https://my-org.awsapps.com/start` | AWS SSO start URL |
| `aws.required_role` | string | `Developer` | Required IAM role name |

### Bedrock

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `bedrock.model_id` | string | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | Primary model for AI features |
| `bedrock.fallback_model_id` | string | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | Fallback model if primary fails |

Valid model IDs: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`, `us.anthropic.claude-sonnet-4-20250514-v1:0`

### GitHub

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `github.repo_owner` | string | `edu526` | Repository owner or organization |
| `github.repo_name` | string | `devo-cli` | Repository name |

### CodeArtifact

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `codeartifact.region` | string | Same as `aws.region` | AWS region for CodeArtifact |
| `codeartifact.account_id` | string | Same as `aws.account_id` | AWS account ID |
| `codeartifact.sso_url` | string | Same as `aws.sso_url` | SSO URL |
| `codeartifact.required_role` | string | `Developer` | Required IAM role |
| `codeartifact.domains` | array | `[]` | List of domain configs (`domain`, `repository`, `namespace`) |

### Version Check

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `version_check.enabled` | boolean | `true` | Enable automatic version checks on startup |

### Default Configuration

```json
{
  "aws": {
    "region": "us-east-1",
    "account_id": "123456789012",
    "sso_url": "https://my-org.awsapps.com/start",
    "required_role": "Developer"
  },
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
    "domains": []
  },
  "version_check": {
    "enabled": true
  }
}
```

## Environment Variables

Environment variables override configuration file values without modifying `~/.devo/config.json`.

### AWS

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_PROFILE` | `default` | AWS CLI profile (standard AWS SDK variable) |
| `AWS_REGION` | `us-east-1` | AWS region for all SDK operations |

### Bedrock

| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | Bedrock model for AI features |
| `BEDROCK_REGION` | `us-east-1` | Region for Bedrock API calls (overrides `AWS_REGION` for Bedrock only) |

### CodeArtifact

| Variable | Default | Description |
|----------|---------|-------------|
| `CODEARTIFACT_REGION` | Same as `AWS_REGION` | Region for CodeArtifact operations |
| `CODEARTIFACT_ACCOUNT_ID` | From config | AWS account ID for CodeArtifact |
| `CODEARTIFACT_SSO_URL` | From config | SSO URL for CodeArtifact |
| `CODEARTIFACT_REQUIRED_ROLE` | `Developer` | Required IAM role |

### GitHub

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_REPO_OWNER` | `edu526` | Repository owner or organization |
| `GITHUB_REPO_NAME` | `devo-cli` | Repository name |

### Other

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVO_SKIP_VERSION_CHECK` | `0` | Set to `1` to disable automatic version checks |

### Usage Patterns

**Single command override:**

```bash
AWS_REGION=eu-west-1 devo commit
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0 devo code-reviewer
```

**Session override:**

```bash
export AWS_PROFILE=production
export AWS_REGION=us-west-2
devo commit
```

**Using a `.env` file:**

```bash
# .env
AWS_REGION=us-west-2
AWS_PROFILE=production
DEVO_SKIP_VERSION_CHECK=1
```

```bash
set -a && source .env && set +a
```

!!! warning
    Never commit `.env` files. Add to `.gitignore` and use `chmod 600 .env`.

## Configuration Priority

Values are resolved in this order (later overrides earlier):

1. Default values (hardcoded)
2. Configuration file (`~/.devo/config.json`)
3. Environment variables
4. Command-line arguments

## See Also

- [Configuration Guide](../getting-started/configuration.md) — commands, migration, troubleshooting
- [config command](../commands/config.md) — manage configuration via CLI
- [AWS Setup](../guides/aws-setup.md) — configure AWS credentials
