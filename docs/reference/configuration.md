# Configuration Reference

Complete reference for all Devo CLI configuration options.

## Configuration File Location

`~/.devo/config.json`

## Configuration Structure

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

## AWS Configuration

### aws.region

- **Type:** string
- **Default:** `us-east-1`
- **Description:** AWS region for all AWS operations
- **Valid Values:** Any valid AWS region (e.g., `us-east-1`, `us-west-2`, `eu-west-1`)
- **Example:**
  ```bash
  devo config set aws.region us-west-2
  ```

### aws.account_id

- **Type:** string
- **Default:** `123456789012`
- **Description:** AWS account ID for authentication
- **Format:** 12-digit number
- **Example:**
  ```bash
  devo config set aws.account_id 123456789012
  ```

### aws.sso_url

- **Type:** string
- **Default:** `https://my-org.awsapps.com/start`
- **Description:** AWS SSO start URL for authentication
- **Format:** HTTPS URL
- **Example:**
  ```bash
  devo config set aws.sso_url https://your-org.awsapps.com/start
  ```

### aws.required_role

- **Type:** string
- **Default:** `DeveloperTools`
- **Description:** Required IAM role name for operations
- **Example:**
  ```bash
  devo config set aws.required_role Developer
  ```

## Bedrock Configuration

### bedrock.model_id

- **Type:** string
- **Default:** `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- **Description:** Primary AWS Bedrock model ID for AI features
- **Valid Values:**
  - `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (Claude 3.7 Sonnet)
  - `us.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4)
- **Example:**
  ```bash
  devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
  ```

### bedrock.fallback_model_id

- **Type:** string
- **Default:** `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- **Description:** Fallback model ID if primary model fails
- **Example:**
  ```bash
  devo config set bedrock.fallback_model_id us.anthropic.claude-3-7-sonnet-20250219-v1:0
  ```

## GitHub Configuration

### github.repo_owner

- **Type:** string
- **Default:** `edu526`
- **Description:** GitHub repository owner or organization name
- **Example:**
  ```bash
  devo config set github.repo_owner myorg
  ```

### github.repo_name

- **Type:** string
- **Default:** `devo-cli`
- **Description:** GitHub repository name
- **Example:**
  ```bash
  devo config set github.repo_name my-cli
  ```

## CodeArtifact Configuration

### codeartifact.region

- **Type:** string
- **Default:** Same as `aws.region`
- **Description:** AWS region for CodeArtifact operations
- **Example:**
  ```bash
  devo config set codeartifact.region us-east-1
  ```

### codeartifact.account_id

- **Type:** string
- **Default:** Same as `aws.account_id`
- **Description:** AWS account ID for CodeArtifact
- **Example:**
  ```bash
  devo config set codeartifact.account_id 123456789012
  ```

### codeartifact.sso_url

- **Type:** string
- **Default:** Same as `aws.sso_url`
- **Description:** AWS SSO URL for CodeArtifact authentication
- **Example:**
  ```bash
  devo config set codeartifact.sso_url https://your-org.awsapps.com/start
  ```

### codeartifact.required_role

- **Type:** string
- **Default:** Same as `aws.required_role`
- **Description:** Required IAM role for CodeArtifact operations
- **Example:**
  ```bash
  devo config set codeartifact.required_role Developer
  ```

### codeartifact.domains

- **Type:** array of objects
- **Default:** `[]`
- **Description:** List of CodeArtifact domain configurations
- **Object Structure:**
  - `domain` (string): Domain name
  - `repository` (string): Repository name
  - `namespace` (string): NPM namespace
- **Example:**
  ```json
  {
    "codeartifact": {
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

## Version Check Configuration

### version_check.enabled

- **Type:** boolean
- **Default:** `true`
- **Description:** Enable automatic version checks on command execution
- **Valid Values:** `true`, `false`
- **Example:**
  ```bash
  devo config set version_check.enabled false
  ```

## Configuration Priority

Configuration values are resolved in this order (later overrides earlier):

1. Default values (hardcoded in code)
2. Configuration file (`~/.devo/config.json`)
3. Environment variables
4. Command-line arguments

## Default Configuration

```json
{
  "aws": {
    "region": "us-east-1",
    "account_id": "123456789012",
    "sso_url": "https://my-org.awsapps.com/start",
    "required_role": "DeveloperTools"
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
    "required_role": "DeveloperTools",
    "domains": []
  },
  "version_check": {
    "enabled": true
  }
}
```

## See Also

- [Configuration Guide](../getting-started/configuration.md) - Configuration usage guide
- [Environment Variables](environment.md) - Environment variable reference
- [config command](../commands/config.md) - Configuration management command
