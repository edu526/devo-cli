<div align="center">

# Devo CLI

Developer productivity CLI for Git workflows and AWS management.

[![GitHub release](https://img.shields.io/github/v/release/edu526/devo-cli)](https://github.com/edu526/devo-cli/releases/latest) [![Downloads](https://img.shields.io/github/downloads/edu526/devo-cli/total)](https://github.com/edu526/devo-cli/releases) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Documentation](https://github.com/edu526/devo-cli/actions/workflows/docs.yml/badge.svg)](https://devo.heyedu.dev) [![Release](https://github.com/edu526/devo-cli/actions/workflows/release.yml/badge.svg)](https://github.com/edu526/devo-cli/releases) [![GitHub issues](https://img.shields.io/github/issues/edu526/devo-cli)](https://github.com/edu526/devo-cli/issues)

</div>

## Features

- Automated commit message generation (via AWS Bedrock)
- Code review with security analysis (via AWS Bedrock)
- AWS SSO authentication and credential management
- DynamoDB, EventBridge and SSM Session Manager integration
- CodeArtifact authentication
- Shell autocompletion (bash, zsh, fish)
- Self-updating capability
- Standalone binaries — no Python required

## Quick Install

**Linux/macOS:**
```bash
curl -fsSL https://devo.heyedu.dev/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://devo.heyedu.dev/install.ps1 | iex
```

## Usage

```bash
# Generate commit message
devo commit

# Code review
devo code-reviewer

# AWS SSO login
devo aws-login

# DynamoDB export
devo dynamodb export my-table

# SSM port forwarding
devo ssm forward my-service 8080

# Update to latest version
devo upgrade
```

## Documentation

Full documentation at **[devo.heyedu.dev](https://devo.heyedu.dev)**

## License

MIT License - See LICENSE file for details
