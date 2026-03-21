<div align="center">

<img src="docs/assets/banner.svg" alt="Devo CLI" width="800"/>

[![GitHub release](https://img.shields.io/github/v/release/edu526/devo-cli)](https://github.com/edu526/devo-cli/releases/latest) [![Downloads](https://img.shields.io/github/downloads/edu526/devo-cli/total)](https://github.com/edu526/devo-cli/releases) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/) [![Release](https://github.com/edu526/devo-cli/actions/workflows/release.yml/badge.svg)](https://github.com/edu526/devo-cli/releases) [![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=edu526_devo-cli&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=edu526_devo-cli) [![Coverage](https://sonarcloud.io/api/project_badges/measure?project=edu526_devo-cli&metric=coverage)](https://sonarcloud.io/summary/new_code?id=edu526_devo-cli)

</div>

---

## Install

**Linux / macOS**
```bash
curl -fsSL https://devo.heyedu.dev/install.sh | bash
```

**Windows (PowerShell)**
```powershell
irm https://devo.heyedu.dev/install.ps1 | iex
```

## What it does

| Command | Description |
|---------|-------------|
| `devo ssm connect` | Secure port-forwarding tunnel to private databases via AWS SSM |
| `devo aws-login` | AWS SSO authentication — refreshes all profiles at once |
| `devo dynamodb export` | Export any DynamoDB table to CSV or JSON |
| `devo commit` | AI-generated commit messages via AWS Bedrock |
| `devo code-reviewer` | AI code review with security analysis before opening a PR |
| `devo codeartifact-login` | Authenticate npm/pip against AWS CodeArtifact |
| `devo upgrade` | Self-update to the latest release |

## Quick start

```bash
# Connect to a private database through SSM
devo ssm connect mydb

# Refresh all AWS SSO profiles
devo aws-login

# Export a DynamoDB table
devo dynamodb export my-table

# Generate a commit message
devo commit
```

## Documentation

Full docs at **[devo.heyedu.dev](https://devo.heyedu.dev)**

## License

MIT — see [LICENSE](LICENSE) for details.
