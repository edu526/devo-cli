# devo codeartifact-login

Authenticate with AWS CodeArtifact for private package management.

## Synopsis

```bash
devo codeartifact-login [OPTIONS]
```

## Description

Configures pip to authenticate with AWS CodeArtifact repository. Obtains an authorization token and configures pip's index URL to use the private repository.

## Usage

::: mkdocs-click
    :module: cli_tool.commands.codeartifact_login
    :command: codeartifact_login
    :prog_name: devo
    :depth: 1

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

## Configuration

Default settings:
- **Domain**: devo-ride
- **Repository**: pypi
- **Region**: us-east-1

## Required IAM Permissions

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

Authorization tokens expire after 12 hours. Re-authenticate when you encounter authentication errors.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS profile for credentials | Default profile |
| `AWS_REGION` | AWS region for CodeArtifact | `us-east-1` |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (access denied, invalid configuration, etc.) |

## Examples

```bash
# Login to CodeArtifact
devo codeartifact-login

# Use specific AWS profile
devo --profile production codeartifact-login
```

## See Also

- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [Configuration Guide](../getting-started/configuration.md) - CodeArtifact settings
