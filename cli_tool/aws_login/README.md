# AWS Login Module

Modular implementation of the AWS SSO login command.

## Module Structure

```
cli_tool/aws_login/
├── __init__.py          # Module exports
├── command.py           # Main Click command entry point
├── config.py            # AWS config file management
├── credentials.py       # Credential expiration checking
├── setup.py             # Interactive SSO profile configuration
├── status.py            # Status display for all profiles
├── refresh.py           # Refresh expired/expiring credentials
├── list.py              # List available profiles
└── login.py             # SSO login flow
```

## Module Responsibilities

### command.py
- Main Click command definition
- Command-line option parsing
- Routes to appropriate submodules based on flags

### config.py
- Read/parse AWS config file (~/.aws/config)
- Extract profile configurations
- Handle both legacy SSO format and new sso-session format
- List available profiles and SSO sessions

### credentials.py
- Check credential expiration using AWS CLI
- Verify credentials with STS GetCallerIdentity
- Determine if profiles need refresh
- Get SSO token information from cache

### setup.py
- Interactive SSO profile configuration
- Reuse existing SSO sessions
- List available accounts and roles from AWS SSO API
- Write profile configuration to AWS config file

### status.py
- Display detailed expiration status for all profiles
- Show expiration time in local timezone
- Calculate time remaining for each profile

### refresh.py
- Refresh all expired/expiring profiles
- Group profiles by SSO session to minimize logins
- Show summary of refresh operations

### list.py
- List all available AWS profiles
- Show active/expired status for each profile

### login.py
- Perform SSO login flow
- Open browser for authentication
- Cache credentials
- Display expiration information

## Usage Examples

```bash
# Login to a profile
devo aws-login --profile production

# List all profiles
devo aws-login --list

# Show detailed status
devo aws-login --status

# Refresh expired profiles
devo aws-login --refresh-all

# Configure new profile
devo aws-login --configure
```

## Key Features

- Detects both legacy SSO format and new sso-session format
- Groups profiles by SSO session to minimize login prompts
- Shows real expiration time in local timezone
- Auto-refresh for expired/expiring credentials (10-minute threshold)
- Uses AWS CLI's native credential resolution
- Reads account credential expiration (not SSO token expiration)
