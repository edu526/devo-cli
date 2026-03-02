---
inclusion: always
---

# Product Overview

Devo CLI is a Python-based command-line tool that provides AI-powered development workflows and AWS integration for development teams.

## Core Capabilities

### AI-Powered Features
- Commit message generation using AWS Bedrock (Claude 3.7 Sonnet)
- Code review with structured analysis and security checks
- Uses strands-agents framework with Pydantic for structured outputs

### AWS Integration
- SSO authentication with automatic credential caching
- Auto-refresh for expired/expiring credentials
- CodeArtifact authentication for private package repositories
- Bedrock AI model integration (configurable via BEDROCK_MODEL_ID env var)
- Default region: us-east-1

### Developer Experience
- Self-updating capability via `devo upgrade`
- Shell completion support (bash, zsh, fish)
- Rich terminal UI for formatted output

## Available Commands

### AI-Powered Features
- **commit** - AI-powered commit message generation
  - Conventional commit format
  - Automatic ticket extraction from branch names
  - Multi-line descriptions
  - Interactive confirmation

- **code-reviewer** - AI code review with security analysis
  - Reviews staged or committed changes
  - Checks: code quality, security, best practices, performance
  - Structured output with severity levels

### AWS Authentication
- **aws-login** - AWS SSO authentication and credential management
  - Interactive SSO profile configuration
  - Browser-based authentication flow
  - Automatic credential caching (8-12 hour expiration)
  - Auto-refresh for expired/expiring credentials
  - Groups profiles by SSO session to minimize login prompts

- **codeartifact-login** - CodeArtifact authentication
  - 12-hour authentication tokens
  - Automatic pip configuration

### AWS Services
- **dynamodb** - DynamoDB table management
  - List, describe, and export tables
  - Multiple export formats (CSV, JSON, JSONL, TSV)
  - Filter expressions with auto-optimization
  - Parallel scanning and compression support

- **eventbridge** - EventBridge rule management
  - List rules with status
  - Filter by environment and state
  - Multiple output formats (table, JSON)

- **ssm** - AWS Systems Manager Session Manager
  - Secure shell access via SSM
  - Database connection tunnels
  - Port forwarding
  - /etc/hosts management

### Configuration & Tools
- **config** - Configuration management
  - Nested key access with dot notation
  - JSON export/import
  - Configuration validation

- **autocomplete** - Shell autocompletion setup
  - Auto-detects current shell
  - Supports bash, zsh, fish

- **upgrade** - Self-update system
  - Automatic version checking
  - Platform-specific binaries
  - Safe upgrade with backup

## Design Principles

### Modularity
- Each command is a separate module in `cli_tool/commands/`
- Large features (code_reviewer) have dedicated subdirectories
- Prompts for complex features organized in `prompt/` subdirectories

### AI Agent Pattern
- All AI features extend `BaseAgent` from `cli_tool/core/agents/base_agent.py`
- System prompts defined inline or in dedicated prompt modules
- Structured outputs using Pydantic models for type safety

### User Experience
- Interactive prompts for user input
- Rich terminal formatting for readable output
- Clear error messages and validation

## Workflow Integration

### Git Integration
- Reads staged changes for commit message generation
- Analyzes diffs for code review
- Extracts ticket numbers from branch names

### Package Distribution
- Published to AWS CodeArtifact private repository
- Versioned using git tags (setuptools_scm)
- Binary distribution via PyInstaller for standalone executables

## Target Audience

Development teams requiring:
- Standardized commit message formats
- AI-assisted code review workflows
- AWS CodeArtifact integration
- Consistent development tooling across team members
