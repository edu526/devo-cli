# CodeArtifact Login Workflow

Learn how to authenticate with AWS CodeArtifact to access private npm packages.

## Quick Start

```bash
# Login to AWS first
devo aws-login

# Then login to CodeArtifact
devo codeartifact-login
```

## What It Does

`devo codeartifact-login` authenticates with your configured AWS CodeArtifact domains and automatically updates your `~/.npmrc` so that npm can install private packages. Tokens are valid for **12 hours**.

## First-Time Setup

### 1. Configure CodeArtifact Settings

Add your CodeArtifact configuration to `~/.devo/config.json`:

```bash
devo config set codeartifact.region us-east-1
devo config set codeartifact.account_id 123456789012
```

Then edit the config file to add your domains:

```bash
devo config path   # Shows path to config file
```

Add the `domains` array:

```json
{
  "codeartifact": {
    "region": "us-east-1",
    "account_id": "123456789012",
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

### 2. Verify IAM Permissions

Your AWS role needs the following permissions:

```json
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
```

### 3. Login

```bash
# 1. Login to AWS (if using SSO)
devo aws-login

# 2. Login to CodeArtifact
devo codeartifact-login

# 3. Install private packages
npm install @myorg/my-package
```

## Daily Workflow

CodeArtifact tokens expire every **12 hours**. Typical daily routine:

```bash
# Morning: refresh AWS credentials and CodeArtifact token
devo aws-login
devo codeartifact-login

# Work normally — npm install works with private packages
npm install
```

## Multiple Domains

If your team uses multiple CodeArtifact domains, add each to the `domains` array. `devo codeartifact-login` authenticates all of them in one command:

```json
{
  "codeartifact": {
    "region": "us-east-1",
    "account_id": "123456789012",
    "domains": [
      {
        "domain": "my-domain",
        "repository": "npm",
        "namespace": "@myorg"
      },
      {
        "domain": "shared-domain",
        "repository": "npm-shared",
        "namespace": "@shared"
      }
    ]
  }
}
```

```bash
devo codeartifact-login
# ✓ Authenticated with domain: my-domain
# ✓ Authenticated with domain: shared-domain
```

## Multiple AWS Profiles

If you manage multiple environments, use the global `--profile` flag:

```bash
devo --profile production codeartifact-login
devo --profile staging codeartifact-login
```

## Team Configuration Sharing

Share CodeArtifact configuration with your team so everyone uses the same domains and settings:

```bash
# Export CodeArtifact configuration
devo config export -s codeartifact

# Share the generated file with your team (via git, Slack, etc.)

# Team members import it
devo config import <file>
```

## Troubleshooting

### Configuration Not Found

```
Error: CodeArtifact configuration not found
```

Check your configuration:

```bash
devo config show codeartifact
```

Set missing fields:

```bash
devo config set codeartifact.region us-east-1
devo config set codeartifact.account_id 123456789012
```

### Access Denied

```
Error: Access denied to CodeArtifact
```

Verify your AWS credentials are valid and have the required permissions:

```bash
aws sts get-caller-identity
```

Refresh credentials if using SSO:

```bash
devo aws-login
```

### npm install Fails (401 Unauthorized)

Token is likely expired. Re-login:

```bash
devo codeartifact-login
```

### Wrong Registry Configured

Verify your `~/.npmrc` after login:

```bash
cat ~/.npmrc
```

Check that the domain and namespace match your `~/.devo/config.json`.

## Next Steps

- [AWS Login Workflow](aws-login-workflow.md) - Manage AWS SSO credentials
- [AWS Setup](aws-setup.md) - Configure IAM permissions
- [codeartifact-login Command Reference](../commands/codeartifact.md) - Full command options
