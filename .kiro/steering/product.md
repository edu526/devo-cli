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

### Code Generation
- Template-based scaffolding using Jinja2 templates
- Templates stored in `cli_tool/templates/` with `.j2` extension
- Supports database migrations, indexes, and custom templates

### AWS Integration
- CodeArtifact authentication for private package repositories
- Bedrock AI model integration (configurable via BEDROCK_MODEL_ID env var)
- Default region: us-east-1

### Developer Experience
- Self-updating capability via `devo upgrade`
- Shell completion support (bash, zsh, fish)
- Rich terminal UI for formatted output

## Command Reference

### `devo commit`
Generates conventional commit messages from staged git changes.
- Format: `<type>(<scope>): NDT-<ticket> <summary>`
- Extracts ticket numbers from branch names (feature/NDT-XXX-description)
- Types: feat, fix, chore, docs, refactor, test, style, perf
- Max 50 chars for summary line

### `devo code-reviewer`
AI-powered code review analyzing git diffs.
- Reviews staged or committed changes
- Checks: code quality, security, best practices, performance
- Structured output with severity levels and actionable feedback

### `devo generate`
Scaffolds code from Jinja2 templates.
- Available templates: alter_table, create_index, ejemplo_template
- Prompts for template variables interactively

### `devo codeartifact-login`
Authenticates with AWS CodeArtifact for package management.
- Domain: devo-ride
- Repository: pypi
- Region: us-east-1

### `devo upgrade`
Self-updates the CLI tool to the latest version.

## Design Principles

### Modularity
- Each command is a separate module in `cli_tool/commands/`
- Large features (code_reviewer) have dedicated subdirectories
- Prompts for complex features organized in `prompt/` subdirectories

### AI Agent Pattern
- All AI features extend `BaseAgent` from `cli_tool/agents/base_agent.py`
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
- Template-based code generation
- AWS CodeArtifact integration
- Consistent development tooling across team members
