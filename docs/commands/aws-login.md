# AWS Login Command

Automates AWS SSO authentication and credential management.

## Overview

The `aws-login` command eliminates manual credential management by automating the AWS SSO authentication process. It opens your browser, handles authentication, and caches credentials automatically.

## Quick Start

```bash
# Configure a new profile
devo aws-login --configure --profile production

# Login
devo aws-login --profile production

# Check status
devo aws-login --status
```

## Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--profile` | `-p` | AWS profile name to login |
| `--list` | `-l` | List available AWS profiles |
| `--configure` | `-c` | Configure a new SSO profile interactively |
| `--refresh-all` | `-r` | Refresh all expired/expiring profiles |
| `--status` | `-s` | Show detailed expiration status for all profiles |
| `--set-default` | `-d` | Set a profile as the default (updates shell configuration) |

## Usage

### Configure Profile

Interactive configuration using AWS CLI's SSO wizard:

```bash
devo aws-login --configure
devo aws-login --configure --profile production
```

The wizard will:

1. Prompt for SSO start URL
2. Open browser for authentication
3. Show available accounts and roles
4. Configure default region

### Login

```bash
# Login to specific profile
devo aws-login --profile production

# Interactive profile selection
devo aws-login
```

### List Profiles

```bash
devo aws-login --list
```

Shows all configured profiles with their status (Active/Expired).

### Check Status

```bash
devo aws-login --status
```

Displays detailed expiration information for all profiles:

```
═══ AWS Profile Expiration Status ═══

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Profile              ┃ Status          ┃ Expires At (Local)        ┃ Time Remaining       ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ production           │ Valid           │ 2026-03-01 14:30:00       │ 7h 45m               │
│ dev                  │ Expiring Soon   │ 2026-03-01 07:05:00       │ 8m                   │
│ staging              │ Expired         │ 2026-02-28 23:00:00       │ Expired              │
└──────────────────────┴─────────────────┴───────────────────────────┴──────────────────────┘
```

### Refresh All

```bash
devo aws-login --refresh-all
```

Automatically refreshes all profiles that are expired or expiring within 10 minutes. Groups profiles by SSO session to minimize login prompts.

## Configuration

### SSO Session Format (Recommended)

```ini
[sso-session my-sso]
sso_start_url = https://my-company.awsapps.com/start
sso_region = us-east-1

[profile production]
sso_session = my-sso
sso_account_id = 123456789012
sso_role_name = Developer
region = us-east-1
output = json
```

### Legacy Format

```ini
[profile production]
sso_start_url = https://my-company.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = Developer
region = us-east-1
output = json
```

Both formats are supported.

## How It Works

1. **Configuration**: Uses AWS CLI's `aws configure sso`
2. **Authentication**: Opens browser for SSO authentication
3. **Caching**: Stores credentials in `~/.aws/sso/cache/`
4. **Expiration**: Account credentials typically last 1-8 hours
5. **Detection**: Monitors expiration and prompts for refresh

## Using Credentials

```bash
# Set as default
export AWS_PROFILE=production

# Use with AWS CLI
aws s3 ls --profile production

# Use with other devo commands
devo codeartifact-login --profile production
```

## Examples

### Basic Usage

```bash
# Configure and login
devo aws-login --configure --profile production
devo aws-login --profile production
```

### Multiple Profiles

```bash
# Configure multiple environments
devo aws-login --configure --profile dev
devo aws-login --configure --profile staging
devo aws-login --configure --profile production

# Check status
devo aws-login --status

# Refresh all
devo aws-login --refresh-all
```

## Troubleshooting

### No AWS profiles found

```bash
devo aws-login --configure
```

### Credentials expired

```bash
devo aws-login --profile production
# or
devo aws-login --refresh-all
```

### SSO authentication failed

Check:

- SSO start URL is correct
- Network access to SSO portal
- SSO account is active
- Role name matches assigned role

### Profile already exists

The configure command will prompt to overwrite or keep existing profile.

## Features

- **Interactive Configuration**: Browser-based account/role selection
- **Auto-Refresh**: Detects and refreshes expiring credentials
- **Session Reuse**: Groups profiles by SSO session to minimize logins
- **Status Monitoring**: Real-time expiration tracking
- **Multi-Format Support**: Works with both legacy and sso-session formats
- **Local Timezone**: Shows expiration times in your timezone

## Related Commands

- [`devo codeartifact-login`](codeartifact.md) - Login to CodeArtifact
- [`devo config`](config.md) - Configure Devo CLI settings

## Related Guides

- [AWS Login Workflow](../guides/aws-login-workflow.md) - Complete workflow guide
- [AWS Setup](../guides/aws-setup.md) - Initial AWS configuration

## Notes

- Account credentials expire after 1-8 hours (organization-dependent)
- SSO tokens can last up to 12 hours
- Requires AWS CLI v2
- Credentials cached securely by AWS CLI
- Supports multiple profiles for different accounts/roles
