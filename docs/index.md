# Devo CLI

**Developer productivity CLI · AI-powered workflows**

```
 ██████╗ ███████╗██╗   ██╗ ██████╗
 ██╔══██╗██╔════╝██║   ██║██╔═══██╗
 ██║  ██║█████╗  ██║   ██║██║   ██║
 ██║  ██║██╔══╝  ╚██╗ ██╔╝██║   ██║
 ██████╔╝███████╗ ╚████╔╝ ╚██████╔╝
 ╚═════╝ ╚══════╝  ╚═══╝   ╚═════╝
```

## What is Devo CLI?

Devo CLI is a command-line tool that streamlines daily development tasks — from committing changes and reviewing code to managing AWS resources like DynamoDB, SSM, EventBridge and CodeArtifact. It uses AWS Bedrock internally for the `commit` and `code-reviewer` commands.

## Key Features

- **Commit Automation**: Generate conventional commit messages from staged changes using AWS Bedrock
- **Code Review**: Automated code analysis with security checks and best practices validation
- **AWS SSO**: Authentication and credential management across multiple profiles
- **DynamoDB**: Table management and data export (CSV, JSON, JSONL, TSV)
- **SSM Session Manager**: Connect to private instances and databases via port forwarding
- **EventBridge**: Enable, disable and describe rules
- **CodeArtifact**: Authenticate with private package registries
- **Shell Completion**: Tab completion support for bash, zsh, and fish
- **Self-Updating**: Keep your CLI up-to-date with a single command
- **Standalone Binaries**: No Python installation required

---

## 🚀 New here? Start in 3 steps

**Step 1 — Install**

=== "Linux/macOS"

    ```bash
    curl -fsSL https://devo.heyedu.dev/install.sh | bash
    ```

=== "Windows (PowerShell)"

    ```powershell
    irm https://devo.heyedu.dev/install.ps1 | iex
    ```

**Step 2 — Set up AWS**

→ Follow the [AWS Setup Guide](guides/aws-setup.md) to configure SSO, then use `devo aws-login` to authenticate daily.

**Step 3 — Use it**

```bash
git add .
devo commit        # generate commit message
devo code-reviewer # review your branch changes
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
- [Commit Workflow](guides/commit-workflow.md) - Generate commit messages automatically
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
