# Environment Variables Reference

Complete reference for environment variables that configure Devo CLI behavior.

## Overview

Environment variables override configuration file values and provide temporary configuration changes without modifying `~/.devo/config.json`.

## AWS Configuration

### AWS_REGION

- **Description:** AWS region for all AWS operations
- **Default:** `us-east-1`
- **Example:**
  ```bash
  export AWS_REGION=us-west-2
  devo commit
  ```

### AWS_ACCOUNT_ID

- **Description:** AWS account ID for authentication
- **Default:** `123456789012`
- **Example:**
  ```bash
  export AWS_ACCOUNT_ID=123456789012
  devo commit
  ```

### AWS_SSO_URL

- **Description:** AWS SSO start URL for authentication
- **Default:** `https://my-org.awsapps.com/start`
- **Example:**
  ```bash
  export AWS_SSO_URL=https://your-org.awsapps.com/start
  devo commit
  ```

### AWS_REQUIRED_ROLE

- **Description:** Required IAM role name for operations
- **Default:** `DeveloperTools`
- **Example:**
  ```bash
  export AWS_REQUIRED_ROLE=Developer
  devo commit
  ```

### AWS_PROFILE

- **Description:** AWS CLI profile to use
- **Default:** `default`
- **Example:**
  ```bash
  export AWS_PROFILE=production
  devo commit
  ```

## Bedrock Configuration

### BEDROCK_MODEL_ID

- **Description:** AWS Bedrock model ID for AI features
- **Default:** `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- **Valid Values:**
  - `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (Claude 3.7 Sonnet)
  - `us.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4)
- **Example:**
  ```bash
  export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
  devo commit
  ```

## GitHub Configuration

### GITHUB_REPO_OWNER

- **Description:** GitHub repository owner or organization
- **Default:** `edu526`
- **Example:**
  ```bash
  export GITHUB_REPO_OWNER=myorg
  devo upgrade
  ```

### GITHUB_REPO_NAME

- **Description:** GitHub repository name
- **Default:** `devo-cli`
- **Example:**
  ```bash
  export GITHUB_REPO_NAME=my-cli
  devo upgrade
  ```

## CodeArtifact Configuration

### CODEARTIFACT_REGION

- **Description:** AWS region for CodeArtifact operations
- **Default:** Same as `AWS_REGION`
- **Example:**
  ```bash
  export CODEARTIFACT_REGION=us-east-1
  devo codeartifact-login
  ```

## Version Check Configuration

### DEVO_SKIP_VERSION_CHECK

- **Description:** Disable automatic version checks
- **Default:** `0` (enabled)
- **Valid Values:**
  - `0` - Version checks enabled
  - `1` - Version checks disabled
- **Example:**
  ```bash
  export DEVO_SKIP_VERSION_CHECK=1
  devo commit
  ```

## Usage Patterns

### Temporary Override

Override for single command:

```bash
AWS_REGION=eu-west-1 devo commit
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0 devo code-reviewer
```

### Session Override

Override for current shell session:

```bash
export AWS_REGION=us-west-2
export AWS_PROFILE=production
devo commit
devo code-reviewer
```

### Permanent Override

Add to shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
# Add to ~/.bashrc or ~/.zshrc
export AWS_REGION=us-west-2
export AWS_PROFILE=production
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

### Using .env File

Create `.env` file in project root:

```bash
# .env
AWS_REGION=us-west-2
AWS_PROFILE=production
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
DEVO_SKIP_VERSION_CHECK=1
```

Load with:

```bash
# Load .env file
set -a
source .env
set +a

# Run commands
devo commit
```

## Configuration Priority

Values are resolved in this order (later overrides earlier):

1. Default values (hardcoded)
2. Configuration file (`~/.devo/config.json`)
3. Environment variables
4. Command-line arguments

Example:

```bash
# config.json has: aws.region = "us-east-1"
# Environment has: AWS_REGION = "us-west-2"
# Result: Uses us-west-2

devo config get aws.region  # Shows: us-west-2
```

## Examples

### Use Different AWS Profile

```bash
export AWS_PROFILE=staging
devo commit
```

### Use Different Bedrock Model

```bash
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
devo commit
```

### Disable Version Checks

```bash
export DEVO_SKIP_VERSION_CHECK=1
devo commit
```

### Multiple Overrides

```bash
export AWS_REGION=eu-west-1
export AWS_PROFILE=production
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
devo commit
```

### Per-Command Override

```bash
# Use staging profile for commit
AWS_PROFILE=staging devo commit

# Use production profile for code review
AWS_PROFILE=production devo code-reviewer
```

## Debugging

### Check Current Values

```bash
# Show all configuration
devo config show

# Check specific value
devo config get aws.region

# Verify environment variable
echo $AWS_REGION
echo $AWS_PROFILE
```

### Test Configuration

```bash
# Test with environment variable
AWS_REGION=us-west-2 devo config show

# Verify AWS credentials
aws sts get-caller-identity --profile $AWS_PROFILE
```

## Security Considerations

1. **Don't commit .env files** - Add to `.gitignore`
2. **Use restrictive permissions** - `chmod 600 .env`
3. **Avoid hardcoding credentials** - Use AWS SSO or IAM roles
4. **Rotate credentials regularly** - Update access keys periodically
5. **Use least privilege** - Grant minimum required permissions

## See Also

- [Configuration Reference](configuration.md) - Configuration file reference
- [Configuration Guide](../getting-started/configuration.md) - Configuration usage guide
- [AWS Setup](../guides/aws-setup.md) - AWS configuration guide
