# devo codeartifact-login

Authenticate with AWS CodeArtifact for private package management.

## Overview

The `codeartifact-login` command configures pip to authenticate with your AWS CodeArtifact repository, allowing you to install and publish private Python packages.

## Usage

::: mkdocs-click
    :module: cli_tool.commands.codeartifact_login
    :command: codeartifact_login
    :prog_name: devo
    :depth: 1

## Configuration

Default settings:
- **Domain**: devo-ride
- **Repository**: pypi
- **Region**: us-east-1

## Prerequisites

- AWS CLI configured with valid credentials
- Access to the CodeArtifact domain and repository
- Appropriate IAM permissions

## Examples

```bash
# Login to CodeArtifact
devo codeartifact-login

# After login, install private packages
pip install your-private-package

# Publish packages
python -m build
twine upload --repository codeartifact dist/*
```

## Required IAM Permissions

Your AWS user/role needs these permissions:

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

## Token Expiration

CodeArtifact tokens expire after 12 hours. Re-run the command when you see authentication errors.
