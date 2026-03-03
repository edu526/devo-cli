# Devo CLI

AI-powered command-line tool for development workflows with AWS Bedrock integration.

## What is Devo CLI?

Devo CLI is a Python-based command-line tool that enhances developer productivity through AI-powered features and AWS integration. It helps teams maintain consistent commit messages, perform automated code reviews, and streamline development workflows.

## Key Features

- **AI-Powered Commit Messages**: Generate conventional commit messages from staged changes using AWS Bedrock (Claude 3.7 Sonnet)
- **Automated Code Review**: AI-driven code analysis with security checks and best practices validation
- **Self-Updating**: Keep your CLI up-to-date with a single command
- **AWS Integration**: Seamless CodeArtifact authentication and Bedrock AI model access
- **Shell Completion**: Tab completion support for bash, zsh, and fish
- **Standalone Binaries**: No Python installation required for end users

---

## 🚀 New here? Start in 3 steps

**Step 1 — Install**

=== "Linux/macOS"

    ```bash
    curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash
    ```

=== "Windows (PowerShell)"

    ```powershell
    irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
    ```

**Step 2 — Set up AWS** (required for AI features)

→ Follow the [AWS Setup Guide](guides/aws-setup.md) to configure SSO and enable Bedrock access, then use `devo aws-login` to authenticate daily.

**Step 3 — Use it**

```bash
git add .
devo commit        # AI-generated commit message
devo code-reviewer # AI code review of your branch
```

→ See the [Quick Start Guide](getting-started/quickstart.md) for more detail.

---

## Documentation

### Getting Started

- [Quick Start Guide](getting-started/quickstart.md) - Get started in 5 minutes
- [Installation](getting-started/installation.md) - Detailed installation instructions
- [Configuration](getting-started/configuration.md) - Configure CLI settings

### Guides

- [Workflow Guides](guides/index.md) - Step-by-step guides for common workflows
- [AWS Setup](guides/aws-setup.md) - Configure AWS credentials and permissions
- [Commit Workflow](guides/commit-workflow.md) - Generate AI commit messages
- [Code Review Workflow](guides/code-review-workflow.md) - Automated code review
- [CodeArtifact Login](guides/codeartifact-login.md) - Access private npm packages
- [DynamoDB Export](guides/dynamodb-export.md) - Export table data
- [SSM Port Forwarding](guides/ssm-port-forwarding.md) - Connect to private resources

### Reference

- [Commands](commands/index.md) - Complete command reference
- [Troubleshooting](reference/troubleshooting.md) - Common issues and solutions

### For Contributors

- [Development Setup](development/setup.md) - Set up development environment
- [Contributing Guide](development/contributing.md) - Learn how to contribute
- [Building Binaries](development/building.md) - Build standalone binaries

## Requirements

- AWS credentials configured (see [AWS Setup](guides/aws-setup.md))
- Python 3.12+ (for development only, not required for binary installation)
- Git repository

## Support

- [GitHub Issues](https://github.com/edu526/devo-cli/issues) - Report bugs or request features
- [Troubleshooting](reference/troubleshooting.md) - Common issues and solutions

## License

MIT License - See [LICENSE](https://github.com/edu526/devo-cli/blob/main/LICENSE) for details.
