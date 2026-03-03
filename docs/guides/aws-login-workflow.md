# AWS Login Workflow Guide

Complete workflow guide for managing AWS SSO authentication with Devo CLI.

## Overview

The `devo aws-login` command simplifies AWS SSO authentication by automating the entire process - from configuration to credential management.

## First-Time Setup Workflow

### Step 1: Install Prerequisites

Ensure AWS CLI v2 is installed:

```bash
# Check version
aws --version

# Should show: aws-cli/2.x.x or higher
```

If not installed, see [AWS Setup Guide](aws-setup.md).

### Step 2: Configure Your First Profile

```bash
devo aws-login configure production
```

The wizard will:

1. Ask for SSO start URL (e.g., `https://my-company.awsapps.com/start`)
2. Open your browser for authentication
3. Show available AWS accounts
4. Show available roles for selected account
5. Ask for default region (e.g., `us-east-1`)

**Example interaction:**

```
SSO start URL: https://my-company.awsapps.com/start
SSO Region: us-east-1

[Browser opens for authentication]

Available accounts:
  1. Production (123456789012)
  2. Development (987654321098)
  3. Staging (555666777888)

Select account: 1

Available roles:
  1. AdministratorAccess
  2. Developer
  3. ReadOnly

Select role: 2

Default region: us-east-1
Default output format: json

✓ Profile 'production' configured successfully
```

### Step 3: Login

```bash
devo aws-login login production
```

Your browser opens, you authenticate, and credentials are cached automatically.

### Step 4: Verify

```bash
# Check status
devo aws-login list

# Use credentials
aws s3 ls --profile production
```

## Daily Workflow

### Morning Routine

Start your day by checking credential status:

```bash
# Check all profiles
devo aws-login list
```

Output shows which profiles need refresh:

```
═══ AWS Profile Expiration Status ═══

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Profile              ┃ Status          ┃ Expires At (Local)        ┃ Time Remaining       ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ production           │ Expired         │ 2026-02-28 23:00:00       │ Expired              │
│ dev                  │ Valid           │ 2026-03-01 14:30:00       │ 7h 45m               │
│ staging              │ Expiring Soon   │ 2026-03-01 07:05:00       │ 8m                   │
└──────────────────────┴─────────────────┴───────────────────────────┴──────────────────────┘
```

Refresh expired/expiring profiles:

```bash
devo aws-login refresh
```

### Working with Multiple Environments

Switch between environments easily:

```bash
# Work on development
devo aws-login login dev
export AWS_PROFILE=dev
aws s3 ls

# Switch to production
devo aws-login login production
export AWS_PROFILE=production
aws dynamodb list-tables

# Switch to staging
devo aws-login login staging
export AWS_PROFILE=staging
```

### Mid-Day Credential Refresh

If credentials expire during work:

```bash
# Quick refresh for current profile
devo aws-login login production

# Or refresh all at once
devo aws-login refresh
```

## Multi-Environment Setup Workflow

### Scenario: Dev, Staging, Production

Configure all environments:

```bash
# Development
devo aws-login configure dev

# Staging
devo aws-login configure staging

# Production
devo aws-login configure production
```

**Pro tip:** If all environments use the same SSO session, the command will detect it and let you reuse it:

```
Found existing SSO sessions:
  1. my-company-sso - https://my-company.awsapps.com/start
  2. Create new SSO session

Select SSO session: 1
```

This minimizes the number of browser logins needed!

### Login to All Environments

```bash
# Login to each profile
devo aws-login login dev
devo aws-login login staging
devo aws-login login production
```

Or use `refresh` to refresh all at once:

```bash
devo aws-login refresh
```

### Check Status Across Environments

```bash
devo aws-login list
```

See all profiles at a glance.

## Troubleshooting Workflows

### Expired Credentials During Work

**Symptom:** AWS commands fail with "ExpiredToken" error

**Solution:**

```bash
# Quick fix
devo aws-login login production

# Or refresh all
devo aws-login refresh
```

### Multiple SSO Sessions

**Scenario:** You have access to multiple organizations

**Workflow:**

```bash
# Configure first org
devo aws-login configure org1-prod

# Configure second org (different SSO URL)
devo aws-login configure org2-prod

# List all profiles
devo aws-login list

# Check status
devo aws-login list
```

### Profile Conflicts

**Symptom:** Profile already exists

**Solution:**

```bash
# Option 1: Overwrite
devo aws-login configure production
# Choose "Yes" when asked to overwrite

# Option 2: Use different name
devo aws-login configure production-new
```

### Browser Not Opening

**Symptom:** SSO login doesn't open browser

**Solution:**

```bash
# Check if AWS CLI is working
aws sso login --profile production

# If that works, try devo again
devo aws-login login production

# If browser still doesn't open, manually copy URL from terminal
```

## Advanced Workflows

### Role Switching

Switch between roles in the same account:

```bash
# Configure different roles
devo aws-login configure prod-admin
# Select AdministratorAccess role

devo aws-login configure prod-readonly
# Select ReadOnly role

# Use appropriate role for task
devo aws-login login prod-admin  # For admin tasks
devo aws-login login prod-readonly  # For read-only tasks
```

### Cross-Account Access

Access resources across multiple accounts:

```bash
# Configure each account
devo aws-login configure account-a
devo aws-login configure account-b

# Copy data between accounts
aws s3 cp s3://bucket-a/file.txt /tmp/ --profile account-a
aws s3 cp /tmp/file.txt s3://bucket-b/ --profile account-b
```

### Temporary Profile for Testing

Create a temporary profile for testing:

```bash
# Configure test profile
devo aws-login configure test-temp

# Use it
devo aws-login login test-temp
export AWS_PROFILE=test-temp

# When done, remove from ~/.aws/config
vim ~/.aws/config
# Delete [profile test-temp] section
```

## Best Practices

### 1. Check Status Regularly

```bash
# Add to your shell profile (.bashrc, .zshrc)
alias aws-status='devo aws-login list'
```

### 2. Use Descriptive Profile Names

Good:

- `company-prod-admin`
- `company-dev-readonly`
- `client-staging`

Bad:

- `profile1`
- `test`
- `temp`

### 3. Refresh Proactively

Don't wait for credentials to expire:

```bash
# Before starting work
devo aws-login refresh

# Before long-running tasks
devo aws-login login production
./long-running-script.sh
```

### 4. Document Your Profiles

Keep a README in your project:

```markdown
## AWS Profiles

- `company-dev`: Development environment (Account: 123456789012)
- `company-staging`: Staging environment (Account: 987654321098)
- `company-prod`: Production environment (Account: 555666777888)

To setup:
```bash
devo aws-login configure company-dev
```
```

### 5. Use Environment Variables

```bash
# Set default profile for session
export AWS_PROFILE=production

# All AWS commands use this profile
aws s3 ls
devo codeartifact-login
```

## Integration with Other Devo Commands

### CodeArtifact Login

```bash
# Login to AWS first
devo aws-login login production

# Then login to CodeArtifact
devo --profile production codeartifact-login
```

### Commit with Bedrock

```bash
# Ensure AWS credentials are valid
devo aws-login login dev

# Generate commit message (uses Bedrock)
git add .
devo --profile dev commit
```

### Code Review with Bedrock

```bash
# Login to AWS
devo aws-login login dev

# Review code (uses Bedrock)
devo --profile dev code-reviewer
```

## Summary

Key workflows to remember:

1. **First time:** `devo aws-login configure <name>`
2. **Daily start:** `devo aws-login list` → `devo aws-login refresh`
3. **Switch profiles:** `devo aws-login login <name>` + `export AWS_PROFILE=<name>`
4. **Check status:** `devo aws-login list`
5. **Refresh all:** `devo aws-login refresh`

## Related Guides

- [AWS Setup Guide](aws-setup.md) - Initial AWS configuration
- [Commands Reference](../commands/aws-login.md) - Detailed command documentation
- [Configuration Guide](../getting-started/configuration.md) - Devo CLI configuration
