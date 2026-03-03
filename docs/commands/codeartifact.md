# devo codeartifact-login

Login to AWS CodeArtifact for npm access.

## Synopsis

```bash
devo codeartifact-login [OPTIONS]
```

**Alias:** `ca-login`

## Description

Authenticates with configured AWS CodeArtifact domains and repositories. Automatically configures npm to use CodeArtifact for private package access. Supports multiple domains with different namespaces.

## Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |

## Usage

### Basic Usage

```bash
# Login to CodeArtifact
devo codeartifact-login

# Using alias
devo ca-login

# With specific AWS profile
devo --profile production codeartifact-login
```

### Interactive Flow

```
Logging in to AWS CodeArtifact...

✓ Authenticated with domain: my-domain
✓ Configured npm for repository: npm
✓ Configured scope: @myorg

CodeArtifact login successful!

Token expires in: 12 hours
```

## Configuration

CodeArtifact settings are stored in `~/.devo/config.json`:

```json
{
  "codeartifact": {
    "region": "us-east-1",
    "account_id": "123456789012",
    "sso_url": "https://my-org.awsapps.com/start",
    "required_role": "Developer",
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

### Configuration Fields

| Field | Description | Required |
|-------|-------------|----------|
| `region` | AWS region where CodeArtifact is hosted | Yes |
| `account_id` | AWS account ID | Yes |
| `sso_url` | AWS SSO start URL | No |
| `required_role` | Required IAM role for access | No |
| `domains` | List of domain configurations | Yes |
| `domains[].domain` | CodeArtifact domain name | Yes |
| `domains[].repository` | Repository name | Yes |
| `domains[].namespace` | npm scope (e.g., @myorg) | Yes |

### Initial Setup

```bash
# 1. Set region and account ID
devo config set codeartifact.region us-east-1
devo config set codeartifact.account_id 123456789012

# 2. Edit config to add domains (manual)
devo config path
# Edit ~/.devo/config.json and add domains array

# 3. Login to AWS
devo aws-login

# 4. Login to CodeArtifact
devo codeartifact-login

# 5. Install private packages
npm install @myorg/my-package
```

## npm Configuration

After login, your `~/.npmrc` will contain:

```ini
@myorg:registry=https://my-domain-123456789012.d.codeartifact.us-east-1.amazonaws.com/npm/npm/
//my-domain-123456789012.d.codeartifact.us-east-1.amazonaws.com/npm/npm/:_authToken=<token>
//my-domain-123456789012.d.codeartifact.us-east-1.amazonaws.com/npm/npm/:always-auth=true
```

## Examples

## Token Expiration

CodeArtifact tokens expire after 12 hours. When expired, re-login to get a new token:

```bash
devo codeartifact-login
```

## Troubleshooting

### Configuration not found

```
Error: CodeArtifact configuration not found
```

**Solution:** Configure CodeArtifact settings:

```bash
devo config show codeartifact
devo config set codeartifact.region us-east-1
devo config set codeartifact.account_id 123456789012
```

### Access denied

```
Error: Access denied to CodeArtifact
```

**Solution:** Ensure your AWS credentials have CodeArtifact permissions:

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

### npm install fails

```
npm ERR! 401 Unauthorized
```

**Solution:** Token may be expired, re-login:

```bash
devo codeartifact-login
```

### Wrong domain/repository

**Solution:** Verify configuration:

```bash
devo config show codeartifact
```

Update if needed:

```bash
devo config path
# Edit ~/.devo/config.json
```

## Requirements

- AWS credentials with CodeArtifact permissions
- npm installed
- CodeArtifact domain and repository created in AWS
- Proper IAM permissions

## Permissions Required

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
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "sts:AWSServiceName": "codeartifact.amazonaws.com"
        }
      }
    }
  ]
}
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (configuration not found, access denied, etc.) |

## See Also

- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [devo aws-login](aws-login.md) - AWS SSO authentication
- [devo config](config.md) - Manage configuration

## Notes

- Tokens expire after 12 hours
- Requires AWS credentials with CodeArtifact permissions
- Updates `~/.npmrc` automatically
- Supports multiple domains and namespaces
- Works with npm, yarn, and pnpm
