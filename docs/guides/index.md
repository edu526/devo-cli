# Guides

Step-by-step guides for common workflows and use cases with Devo CLI.

## Workflow Guides

### [Commit Workflow](commit-workflow.md)
Learn how to generate conventional commit messages using AI.

**Topics covered:**

- Staging changes
- Generating commit messages
- Commit message format and types
- Ticket number extraction
- Complete development workflow

**Best for:** Developers who want to standardize commit messages and automate message generation.

### [Code Review Workflow](code-review-workflow.md)
Learn how to use AI-powered code review to analyze changes before committing.

**Topics covered:**

- Running code reviews
- Understanding review categories
- Addressing feedback
- Pre-commit review workflow
- Review specific commits or branches

**Best for:** Teams implementing code quality checks and security reviews.

## AWS Integration Guides

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

## Setup Guides

### [Shell Completion](shell-completion.md)
Enable tab completion for your shell.

**Topics covered:**

- Bash completion
- Zsh completion
- Fish completion
- Installation and configuration

**Best for:** Improving command-line productivity.

## Guide Categories

### Getting Started
- [AWS Setup](aws-setup.md) - Configure AWS credentials and permissions

### Development Workflows
- [Commit Workflow](commit-workflow.md) - Generate commit messages
- [Code Review Workflow](code-review-workflow.md) - Review code changes

### AWS Services
- [DynamoDB Export](dynamodb-export.md) - Export table data
- [SSM Port Forwarding](ssm-port-forwarding.md) - Connect to private resources

### Productivity
- [Shell Completion](shell-completion.md) - Enable tab completion

## Quick Links

### For New Users
1. [AWS Setup](aws-setup.md) - Configure credentials
2. [Commit Workflow](commit-workflow.md) - Start using AI commit messages
3. [Shell Completion](shell-completion.md) - Enable tab completion

### For Teams
1. [Code Review Workflow](code-review-workflow.md) - Implement code reviews
2. [SSM Port Forwarding](ssm-port-forwarding.md) - Share database configurations
3. [DynamoDB Export](dynamodb-export.md) - Automate data exports

### For AWS Users
1. [AWS Setup](aws-setup.md) - Configure AWS access
2. [DynamoDB Export](dynamodb-export.md) - Work with DynamoDB
3. [SSM Port Forwarding](ssm-port-forwarding.md) - Access private resources

## Related Documentation

- [Commands Reference](../commands/index.md) - Technical command documentation
- [Configuration Guide](../getting-started/configuration.md) - Detailed configuration options
- [Troubleshooting](../reference/troubleshooting.md) - Common issues and solutions

