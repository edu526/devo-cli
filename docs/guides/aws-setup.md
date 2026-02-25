# AWS Setup Guide

Devo CLI requires AWS credentials to access Bedrock AI models and CodeArtifact. This guide walks you through the setup process.

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI installed

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

### 2. Configure AWS Credentials

#### Option A: AWS Configure (Simple)

```bash
aws configure
```

Enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Default output format (e.g., `json`)

#### Option B: AWS SSO (Recommended)

```bash
aws configure sso
```

Follow prompts to:
1. Enter SSO start URL
2. Enter SSO region
3. Select account and role
4. Set profile name

### 3. Verify Credentials

```bash
# Check identity
aws sts get-caller-identity

# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

### 4. Configure Devo CLI

```bash
# Set AWS region
devo config set aws.region us-east-1

# Set account ID (from get-caller-identity)
devo config set aws.account_id 123456789012

# For SSO users
devo config set aws.sso_url https://your-org.awsapps.com/start
devo config set aws.required_role Developer
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

If you have multiple AWS accounts or roles:

### Create Named Profiles

```bash
# Configure additional profile
aws configure --profile production
aws configure --profile staging
```

### Use with Devo CLI

```bash
# Use specific profile
devo --profile production commit
devo --profile staging code-reviewer

# Set default profile
export AWS_PROFILE=production
devo commit
```

## AWS SSO Setup

For organizations using AWS SSO:

### 1. Configure SSO Profile

```bash
aws configure sso
```

Provide:
- SSO start URL: `https://your-org.awsapps.com/start`
- SSO region: `us-east-1`
- Account ID
- Role name
- Profile name: `my-sso-profile`

### 2. Login to SSO

```bash
aws sso login --profile my-sso-profile
```

### 3. Use with Devo CLI

```bash
# Use SSO profile
devo --profile my-sso-profile commit

# Or set as default
export AWS_PROFILE=my-sso-profile
devo commit
```

### 4. Configure Devo CLI for SSO

```bash
devo config set aws.sso_url https://your-org.awsapps.com/start
devo config set aws.required_role Developer
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

```bash
# Re-login to SSO
aws sso login --profile my-sso-profile
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

- [Configuration Guide](../getting-started/configuration.md) - Detailed configuration options
- [Commands](../commands/index.md) - Learn available commands
- [Troubleshooting](../reference/troubleshooting.md) - Common issues

## Additional Resources

- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [AWS SSO](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html)
- [AWS Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
