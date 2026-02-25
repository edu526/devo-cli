# devo code-reviewer

AI-powered code review analyzing git diffs for quality, security, and best practices.

## Overview

The `code-reviewer` command performs comprehensive analysis of your code changes using AWS Bedrock AI, checking for:

- Code quality and maintainability
- Security vulnerabilities
- Performance issues
- Best practices compliance
- Potential bugs

## Usage

::: mkdocs-click
    :module: cli_tool.commands.code_reviewer
    :command: code_reviewer
    :prog_name: devo
    :depth: 1

## Review Categories

### Code Quality
- Code structure and organization
- Naming conventions
- Code duplication
- Complexity analysis

### Security
- Input validation
- Authentication/authorization issues
- Sensitive data exposure
- Injection vulnerabilities

### Performance
- Inefficient algorithms
- Resource usage
- Database query optimization
- Caching opportunities

### Best Practices
- Language-specific conventions
- Design patterns
- Error handling
- Documentation

## Output Format

The review provides structured feedback with:

- **Severity levels**: Critical, High, Medium, Low, Info
- **File locations**: Specific files and line numbers
- **Descriptions**: Clear explanation of issues
- **Recommendations**: Actionable suggestions for fixes

## Examples

```bash
# Review staged changes
git add .
devo code-reviewer

# Review specific commit
devo code-reviewer --commit abc123

# Review changes between branches
git diff main feature/my-branch | devo code-reviewer
```

## Configuration

Set your preferred Bedrock model:

```bash
export BEDROCK_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
```
