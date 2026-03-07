# Guides

Step-by-step guides for common workflows and use cases with Devo CLI.

## Getting Started

### [AWS Setup](aws-setup.md)

Configure AWS credentials and permissions for Devo CLI.

**Topics covered:**

- Installing AWS CLI
- Configuring credentials
- AWS SSO setup
- Required IAM permissions
- Bedrock model access
- Using AWS profiles

**Best for:** First-time setup and AWS configuration.

### [AWS Login Workflow](aws-login-workflow.md)

Complete workflow guide for managing AWS SSO authentication.

**Topics covered:**

- First-time SSO setup
- Daily credential management
- Multi-environment configuration
- Troubleshooting common issues

**Best for:** Teams using AWS SSO who want to streamline authentication and credential management.

### [Shell Completion](shell-completion.md)

Enable tab completion for your shell.

**Topics covered:**

- Bash completion
- Zsh completion
- Fish completion
- Installation and configuration

**Best for:** Improving command-line productivity.

## Development Workflows

### [Commit Workflow](commit-workflow.md)

Learn how to generate conventional commit messages using AWS Bedrock.

**Topics covered:**

- Staging changes
- Generating commit messages
- Commit message format and types
- Ticket number extraction
- Complete development workflow

**Best for:** Developers who want to standardize commit messages and automate message generation.

### [Code Review Workflow](code-review-workflow.md)

Learn how to use automated code review to analyze changes before committing.

**Topics covered:**

- Running code reviews
- Understanding review categories
- Addressing feedback
- Pre-commit review workflow
- Review specific commits or branches

**Best for:** Teams implementing code quality checks and security reviews.

## AWS Services

### [CodeArtifact Login](codeartifact-login.md)

Authenticate with AWS CodeArtifact to access private npm packages.

**Topics covered:**

- First-time setup and configuration
- Daily token refresh workflow
- Multiple domains
- Team configuration sharing
- Troubleshooting

**Best for:** Developers who need to install private npm packages from AWS CodeArtifact.

### [DynamoDB Export](dynamodb-export.md)

Export DynamoDB table data for backup, analysis, and migration.

**Topics covered:**

- Export formats (CSV, JSON, JSONL, TSV)
- Handling nested data
- Filtering and querying
- Performance optimization
- Using templates
- Team workflows

**Best for:** Data engineers and developers working with DynamoDB data.

### [SSM Port Forwarding](ssm-port-forwarding.md)

Securely connect to private databases and services using AWS Systems Manager.

**Topics covered:**

- Setting up hostname forwarding
- Connecting to databases
- Multi-environment setup
- Team configuration sharing
- Platform-specific setup (Linux, macOS, Windows)
- Troubleshooting connections

**Best for:** Developers accessing private RDS, ElastiCache, or other AWS resources.

## Quick Links

### For New Users

1. [AWS Setup](aws-setup.md) - Configure credentials
2. [AWS Login Workflow](aws-login-workflow.md) - Setup SSO authentication
3. [Commit Workflow](commit-workflow.md) - Start using AI commit messages
4. [Shell Completion](shell-completion.md) - Enable tab completion

### For Teams

1. [AWS Login Workflow](aws-login-workflow.md) - Standardize AWS authentication
2. [Code Review Workflow](code-review-workflow.md) - Implement code reviews
3. [CodeArtifact Login](codeartifact-login.md) - Share private npm package access
4. [SSM Port Forwarding](ssm-port-forwarding.md) - Share database configurations
5. [DynamoDB Export](dynamodb-export.md) - Automate data exports

### For AWS Users

1. [AWS Setup](aws-setup.md) - Configure AWS access
2. [AWS Login Workflow](aws-login-workflow.md) - Manage SSO credentials
3. [CodeArtifact Login](codeartifact-login.md) - Access private npm packages
4. [DynamoDB Export](dynamodb-export.md) - Work with DynamoDB
5. [SSM Port Forwarding](ssm-port-forwarding.md) - Access private resources

## Related Documentation

- [Commands Reference](../commands/index.md) - Technical command documentation
- [Configuration Guide](../getting-started/configuration.md) - Detailed configuration options
- [Troubleshooting](../reference/troubleshooting.md) - Common issues and solutions
