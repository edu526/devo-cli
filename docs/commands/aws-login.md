# devo aws-login

AWS SSO authentication and profile management.

## Synopsis

```bash
devo aws-login [COMMAND] [OPTIONS]
```

## Description

Automates AWS SSO authentication and credential management. Eliminates manual credential management by automating the AWS SSO authentication process. Opens your browser, handles authentication, and caches credentials automatically.

## Commands

### login

Login to AWS using SSO with a specific profile.

```bash
devo aws-login login [PROFILE] [OPTIONS]
```

**Arguments:**

- `PROFILE` - AWS profile name (optional, shows interactive menu if omitted)

**Example:**

```bash
# Interactive profile selection
devo aws-login login

# Login to specific profile
devo aws-login login production
```

### list

List all AWS profiles with detailed status.

```bash
devo aws-login list [OPTIONS]
```

Shows all configured profiles with their status (Active/Expired/Expiring Soon).

**Example:**

```bash
devo aws-login list
```

**Output:**

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

### configure

Configure a new SSO profile interactively.

```bash
devo aws-login configure [PROFILE] [OPTIONS]
```

**Arguments:**

- `PROFILE` - AWS profile name (optional, prompts if omitted)

Uses AWS CLI's SSO wizard to configure a new profile. The wizard will:

1. Prompt for SSO start URL
2. Open browser for authentication
3. Show available accounts and roles
4. Configure default region

**Example:**

```bash
# Interactive configuration
devo aws-login configure

# Configure specific profile
devo aws-login configure production
```

### refresh

Refresh expired or expiring credentials.

```bash
devo aws-login refresh [OPTIONS]
```

Automatically refreshes all profiles that are expired or expiring within 10 minutes. Groups profiles by SSO session to minimize login prompts.

**Example:**

```bash
devo aws-login refresh
```

### set-default

Set a profile as the default.

```bash
devo aws-login set-default [PROFILE] [OPTIONS]
```

**Arguments:**

- `PROFILE` - AWS profile name (optional, shows interactive menu if omitted)

Sets the AWS_PROFILE environment variable as default:

- **Linux/macOS**: Updates `.bashrc`, `.zshrc`, or `config.fish`
- **Windows**: Sets user environment variable with `setx`
- **Git Bash (Windows)**: Updates `.bashrc`

After setting default, you can use AWS CLI without `--profile`:

```bash
aws s3 ls
aws sts get-caller-identity
devo codeartifact-login
```

**Example:**

```bash
# Interactive selection
devo aws-login set-default

# Set specific profile as default
devo aws-login set-default production
```

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

## Requirements

- AWS CLI v2
- Web browser for SSO authentication
- Network access to SSO portal

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (authentication failed, profile not found, etc.) |

## See Also

- [AWS Login Workflow](../guides/aws-login-workflow.md) - Complete workflow guide
- [AWS Setup](../guides/aws-setup.md) - Initial AWS configuration
- [devo codeartifact-login](codeartifact.md) - Login to CodeArtifact

## Notes

- Account credentials expire after 1-8 hours (organization-dependent)
- SSO tokens can last up to 12 hours
- Credentials cached securely by AWS CLI
- Supports multiple profiles for different accounts/roles
