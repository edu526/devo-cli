# AWS Setup Guide

Devo CLI requires AWS credentials to access Bedrock AI models and CodeArtifact. This guide walks you through the setup process.

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI v2 installed

## Quick Setup

### 1. Install AWS CLI

If not already installed:

```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows
# Download and run: https://awscli.amazonaws.com/AWSCLIV2.msi
```

Verify installation:

```bash
aws --version
# Should show: aws-cli/2.x.x or higher
```

### 2. Configure AWS SSO (Recommended)

For organizations using AWS SSO, use the `devo aws-login` command:

```bash
# Configure SSO profile interactively
devo aws-login configure production

# Login
devo aws-login login production
```

The command will:

1. Prompt for SSO start URL
2. Open browser for authentication
3. Show available accounts and roles
4. Configure default region

**See the [AWS Login Workflow](aws-login-workflow.md) guide for detailed SSO setup.**

### 3. Alternative: AWS Configure (For IAM Users)

If not using SSO:

```bash
aws configure
```

Enter:

- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Default output format (e.g., `json`)

### 4. Verify Credentials

```bash
# Check identity
aws sts get-caller-identity

# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

## Required IAM Permissions

Your AWS user/role needs these permissions:

### Bedrock Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
      ]
    }
  ]
}
```

### CodeArtifact Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "codeartifact:GetAuthorizationToken",
        "codeartifact:GetRepositoryEndpoint",
        "codeartifact:ReadFromRepository"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "sts:GetServiceBearerToken",
      "Resource": "*"
    }
  ]
}
```

## Using AWS Profiles

If you have multiple AWS accounts or roles, use the `devo aws-login` command:

```bash
# Configure multiple profiles
devo aws-login configure dev
devo aws-login configure staging
devo aws-login configure production

# Check status
devo aws-login list

# Use with Devo CLI
devo --profile production commit
devo --profile staging code-reviewer

# Set default profile
export AWS_PROFILE=production
devo commit
```

**See the [AWS Login Workflow](aws-login-workflow.md) guide for managing multiple profiles.**

## AWS SSO Setup

For organizations using AWS SSO, we recommend using the `devo aws-login` command for simplified authentication:

```bash
# Configure SSO profile
devo aws-login configure my-profile

# Login
devo aws-login login my-profile

# Check status
devo aws-login list

# Refresh expired credentials
devo aws-login refresh
```

**For detailed SSO workflows, see the [AWS Login Workflow](aws-login-workflow.md) guide.**

### Manual SSO Configuration (Alternative)

If you prefer to use AWS CLI directly:

```bash
# Configure SSO
aws configure sso

# Login
aws sso login --profile my-sso-profile
```

## Bedrock Model Access

### Enable Bedrock Models

1. Go to AWS Console → Bedrock
2. Navigate to "Model access"
3. Request access to Claude models:
   - Claude 3.7 Sonnet
   - Claude Sonnet 4 (optional)

### Available Models

Configure your preferred model:

```bash
# Claude 3.7 Sonnet (default)
devo config set bedrock.model_id us.anthropic.claude-3-7-sonnet-20250219-v1:0

# Claude Sonnet 4
devo config set bedrock.model_id us.anthropic.claude-sonnet-4-20250514-v1:0
```

## Regional Considerations

Bedrock is available in specific regions. Recommended regions:

- `us-east-1` (N. Virginia) - Most models available
- `us-west-2` (Oregon)
- `eu-west-1` (Ireland)

Set your region:

```bash
devo config set aws.region us-east-1
```

## Troubleshooting

### Credentials Not Found

```bash
# Check AWS configuration
aws configure list

# Verify credentials file
cat ~/.aws/credentials
cat ~/.aws/config
```

### Access Denied to Bedrock

1. Verify model access in AWS Console
2. Check IAM permissions
3. Confirm region supports Bedrock

```bash
# List available models
aws bedrock list-foundation-models --region us-east-1
```

### SSO Session Expired

Use the `devo aws-login` command to refresh:

```bash
# Refresh specific profile
devo aws-login login my-profile

# Or refresh all profiles
devo aws-login refresh
```

### Wrong Account/Role

```bash
# Verify current identity
aws sts get-caller-identity

# Check profile
echo $AWS_PROFILE
```

## Security Best Practices

1. **Use IAM Roles**: Prefer IAM roles over access keys
2. **Enable MFA**: Require multi-factor authentication
3. **Rotate Credentials**: Regularly rotate access keys
4. **Use SSO**: Prefer AWS SSO over long-term credentials
5. **Least Privilege**: Grant minimum required permissions
6. **Audit Access**: Review CloudTrail logs regularly

## Environment Variables

Override configuration with environment variables:

```bash
# Set region
export AWS_REGION=us-west-2

# Set profile
export AWS_PROFILE=production

# Disable version check
export DEVO_SKIP_VERSION_CHECK=1
```

## Testing Your Setup

```bash
# Test AWS credentials
aws sts get-caller-identity

# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1

# Test Devo CLI
devo config show

# Generate a commit message (requires staged changes)
git add .
devo commit
```

## Next Steps

- [AWS Login Workflow](aws-login-workflow.md) - Detailed SSO authentication guide
- [Configuration Guide](../getting-started/configuration.md) - Detailed configuration options
- [Commands](../commands/index.md) - Learn available commands
- [Troubleshooting](../reference/troubleshooting.md) - Common issues

## Additional Resources

- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [AWS SSO](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html)
- [AWS Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
