# AWS Login Module

Modular implementation of the AWS SSO login command with subcommands.

## Module Structure

```
cli_tool/commands/aws_login/
├── __init__.py          # Module exports
├── command.py           # Main Click group entry point
├── commands/            # Command implementations
│   ├── __init__.py      # Command exports
│   ├── list.py          # List available profiles
│   ├── login.py         # SSO login flow
│   ├── setup.py         # Interactive SSO profile configuration
│   ├── status.py        # Status display for all profiles
│   ├── refresh.py       # Refresh expired/expiring credentials
│   └── set_default.py   # Set default profile
├── core/                # Core business logic
│   ├── __init__.py      # Core exports
│   ├── config.py        # AWS config file management
│   └── credentials.py   # Credential expiration checking
└── README.md            # This file
```

## Commands

- `aws-login` - Login to AWS using SSO with interactive profile selection (default action)
- `login [PROFILE]` - Login to AWS using SSO with specific profile
- `list` - List all AWS profiles with detailed status (expiration, time remaining)
- `configure [PROFILE]` - Configure a new SSO profile interactively
- `refresh` - Refresh expired or expiring credentials
- `set-default [PROFILE]` - Set a profile as the default

## Usage Examples

```bash
# Quick interactive login (no subcommand needed)
devo aws-login

# Login to specific profile
devo aws-login login production
devo aws-login login              # also interactive

# List all profiles with detailed status
devo aws-login list

# Configure new profile
devo aws-login configure
devo aws-login configure my-profile

# Refresh expired profiles
devo aws-login refresh

# Set default profile
devo aws-login set-default production
devo aws-login set-default        # interactive selection
```

## Module Responsibilities

### command.py
- Main Click group definition
- Registers all subcommands
- Registers shortcuts
- AWS CLI availability check

### commands/login.py
- Perform SSO login flow
- Open browser for authentication
- Cache credentials
- Display expiration information

### commands/list.py
- List all available AWS profiles
- Show active/expired status for each profile

### commands/configure.py (setup.py)
- Interactive SSO profile configuration
- Reuse existing SSO sessions
- List available accounts and roles from AWS SSO API
- Write profile configuration to AWS config file

### commands/status.py
- Display detailed expiration status for all profiles
- Show expiration time in local timezone
- Calculate time remaining for each profile

### commands/refresh.py
- Refresh all expired/expiring profiles
- Group profiles by SSO session to minimize logins
- Show summary of refresh operations

### commands/set_default.py
- Set default AWS profile
- Update shell configuration files
- Handle Windows/Linux/macOS differences

### core/config.py
- Read/parse AWS config file (~/.aws/config)
- Extract profile configurations
- Handle both legacy SSO format and new sso-session format
- List available profiles and SSO sessions

### core/credentials.py
- Check credential expiration using AWS CLI
- Verify credentials with STS GetCallerIdentity
- Determine if profiles need refresh
- Get SSO token information from cache

## Key Features

- Subcommand-based interface (consistent with SSM, DynamoDB)
- Detects both legacy SSO format and new sso-session format
- Groups profiles by SSO session to minimize login prompts
- Shows real expiration time in local timezone
- Auto-refresh for expired/expiring credentials (10-minute threshold)
- Uses AWS CLI's native credential resolution
- Reads account credential expiration (not SSO token expiration)

