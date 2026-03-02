# Code Reviewer

AI-Powered Code Analysis for Pull Requests using AWS Bedrock.

## Structure

```
cli_tool/commands/code_reviewer/
├── __init__.py              # Public API exports
├── README.md                # This file
├── TODO.md                  # Feature roadmap
├── commands/                # CLI command definitions
│   ├── __init__.py          # Command registration
│   └── analyze.py           # Main analysis command
├── core/                    # Business logic
│   ├── __init__.py
│   ├── analyzer.py          # CodeReviewAnalyzer class
│   └── git_utils.py         # GitManager for git operations
├── prompt/                  # AI prompts and rules
│   ├── __init__.py
│   ├── analysis_rules.py    # Analysis guidelines
│   ├── code_reviewer.py     # Main prompts
│   ├── output_format.py     # Output structure
│   ├── security_standards.py # Security checks
│   └── tools_guide.py       # Tool usage guide
└── tools/                   # AI agent tools
    ├── __init__.py
    ├── code_analyzer.py     # Code analysis tools
    ├── file_reader.py       # File reading tools
    └── README.md            # Tools documentation
```

## Usage

```bash
# Analyze PR changes (current branch vs main)
devo code-reviewer

# Analyze PR changes vs specific branch
devo code-reviewer --base-branch develop

# Get JSON output for CI/CD integration
devo code-reviewer --output json

# Show detailed execution metrics
devo code-reviewer --show-metrics

# Use full detailed prompt (more comprehensive but slower)
devo code-reviewer --full-prompt
```

## Features

- AI-powered code analysis using AWS Bedrock (Claude 3.7 Sonnet)
- Analyzes git diffs between branches
- Detects security issues, code quality problems, and breaking changes
- Structured JSON output for CI/CD integration
- Rich terminal UI with tables and formatting
- Execution metrics and performance tracking

## Architecture

### Commands Layer (`commands/`)
- CLI interface using Click
- User input validation
- Output formatting with Rich
- No business logic

### Core Layer (`core/`)
- `analyzer.py`: Main analysis logic using BaseAgent
- `git_utils.py`: Git operations (diffs, branches, file changes)
- No Click dependencies

### Prompt Layer (`prompt/`)
- AI system prompts
- Analysis rules and guidelines
- Security standards
- Output format specifications

### Tools Layer (`tools/`)
- AI agent tools for code analysis
- File reading and context gathering
- Import analysis and reference search
