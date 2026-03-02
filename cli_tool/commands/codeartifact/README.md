# CodeArtifact Authentication

AWS CodeArtifact authentication for Python package management.

## Structure

```
cli_tool/commands/codeartifact/
├── __init__.py              # Public API exports
├── README.md                # This file
├── commands/                # CLI command definitions
│   ├── __init__.py          # Command registration
│   └── login.py             # Login command
└── core/                    # Business logic
    ├── __init__.py
    └── authenticator.py     # CodeArtifactAuthenticator
```

## Usage

```bash
# Authenticate with CodeArtifact
devo codeartifact-login

# Or use alias
devo ca-login

# Use specific AWS profile
devo --profile production codeartifact-login
```

## Features

- Automatic authentication with AWS CodeArtifact
- Configures pip to use CodeArtifact repository
- Token-based authentication (12-hour validity)
- Supports custom domain and repository configuration

## Configuration

Default configuration in `~/.devo/config.json`:

```json
{
  "codeartifact": {
    "domain": "devo-ride",
    "repository": "pypi",
    "region": "us-east-1"
  }
}
```

## Architecture

### Commands Layer (`commands/`)
- `login.py`: CLI command with Click decorators
- User feedback and error handling
- Output formatting with Rich

### Core Layer (`core/`)
- `authenticator.py`: CodeArtifactAuthenticator class
- AWS CodeArtifact API integration
- Pip configuration management
- No Click dependencies

## How It Works

1. Retrieves authentication token from AWS CodeArtifact
2. Configures pip to use CodeArtifact repository
3. Sets up index URL with embedded token
4. Token valid for 12 hours

## Requirements

- AWS credentials configured
- AWS CodeArtifact permissions:
  - `codeartifact:GetAuthorizationToken`
  - `codeartifact:ReadFromRepository`

## After Authentication

Install packages from CodeArtifact:

```bash
pip install your-private-package
```

Publish packages to CodeArtifact:

```bash
python -m build
twine upload --repository codeartifact dist/*
```

## Token Expiration

Tokens expire after 12 hours. Re-run the command to refresh:

```bash
devo codeartifact-login
```
