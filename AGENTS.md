# Devo CLI — Agent Instructions

This file provides guidance to AI coding assistants (Claude Code, Cursor, Copilot, etc.) when working with code in this repository.

## Commands

```bash
# Setup
make venv              # Create virtual environment
make install           # Install with all dependencies
make completion        # Setup shell autocompletion

# Development
make test              # Run all tests
make lint              # Run flake8
make format            # Run black & isort
make refresh           # Refresh shell cache after code changes

# Testing
pytest -m unit         # Unit tests only (also run on pre-push hook)
pytest -m integration  # Integration tests
pytest --cov=cli_tool  # With coverage report

# Build
make binary            # Build binary for current platform
make binary-all        # Build for all platforms
```

## Architecture

`devo-cli` is a Python 3.12+ CLI tool for developer workflows and AWS management, built with Click and Rich.

```
cli_tool/
├── cli.py                   # Entry point — registers all commands
├── config.py                # Global config (Bedrock model IDs, CodeArtifact, release URL)
├── commands/                # One directory per command (Click + Rich only, no business logic)
│   ├── aws_login/           # AWS SSO authentication & credential caching
│   ├── code_reviewer/       # AI code review via Bedrock
│   ├── commit/              # AI commit message generation via Bedrock
│   ├── dynamodb/            # DynamoDB list/export/filter
│   ├── eventbridge/         # EventBridge rule management
│   ├── ssm/                 # SSM Session Manager, port forwarding, /etc/hosts
│   ├── codeartifact/        # CodeArtifact token management
│   ├── config_cmd/          # ~/.devo/config.json dot-notation management
│   ├── autocomplete/        # Shell completion setup
│   └── upgrade/             # Self-update system
└── core/
    ├── agents/base_agent.py # BaseAgent — Strands + Bedrock integration
    ├── ui/console_ui.py     # Rich terminal UI components
    └── utils/               # config_manager, aws, git_utils, version_check
```

**Layer rules (strictly enforced):**
- `commands/` — Click decorators, input validation, Rich output. No business logic.
- `core/` — Business logic, API calls. No Click or Rich dependencies.
- `utils/` — Helpers and reusable functions.

## AI Integration

- **Framework:** Strands agents (`BaseAgent` in `core/agents/base_agent.py`)
- **Primary model:** `us.anthropic.claude-sonnet-4-20250514-v1:0`
- **Fallback model:** `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- **Region:** `us-east-1` (default)
- **User config:** `~/.devo/config.json` — use `load_config()` / `save_config()` from `cli_tool.core.utils.config_manager`

## Adding a New Command

1. Create `cli_tool/commands/your_command/` following the structure below
2. Register in `cli_tool/cli.py` via `cli.add_command()`
3. Use `BaseAgent` for Bedrock integration, `Rich` for all terminal output

### Simple command (e.g. `autocomplete`, `upgrade`)
```
command_name/
├── __init__.py
├── commands/main.py       # Click command
└── core/processor.py      # Business logic
```

### Command group (e.g. `config`, `eventbridge`)
```
command_name/
├── __init__.py
├── commands/
│   ├── __init__.py        # Registers subcommands
│   ├── list.py
│   └── add.py
└── core/manager.py
```

### Complex feature (e.g. `ssm`, `dynamodb`)
```
command_name/
├── __init__.py
├── commands/
│   ├── __init__.py
│   ├── resource1/
│   └── resource2/
├── core/
│   ├── manager.py
│   └── processor.py
└── utils/helpers.py
```

### Bedrock-powered feature (e.g. `commit`, `code-reviewer`)
```
command_name/
├── __init__.py
├── commands/analyze.py
├── core/analyzer.py       # Extends BaseAgent
├── prompt/
│   ├── system_prompt.py
│   └── rules.py
└── tools/analysis_tools.py
```

## Code Style

- **Indentation:** 4 spaces
- **Line length:** 150 chars max
- **Line endings:** LF only
- **Naming:** `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants, `_` prefix for private members
- **Imports:** sorted with isort (black profile)
- **Language:** English only — code, comments, docs, commit messages

## Version Management

Handled automatically by **python-semantic-release** — never create tags manually.

| Commit type | Version bump |
|-------------|-------------|
| `feat:` | minor (1.0.0 → 1.1.0) |
| `fix:`, `perf:` | patch (1.0.0 → 1.0.1) |
| `feat!:` / `BREAKING CHANGE` | major (1.0.0 → 2.0.0) |

Releases trigger automatically on push to `main`. Tag format: `v1.2.3`.

## Pre-commit Hooks

Install with: `pre-commit install && pre-commit install --hook-type pre-push`

**On every commit:** `black`, `isort`, `flake8`, `commitizen` (validates conventional format), large files, merge conflicts, AWS credentials, private keys.

**On push:** `pytest -m unit` — unit tests must pass.

## Key Constraints

- **Never edit `cli_tool/_version.py`** — auto-generated by `setuptools_scm`
- **Never use `--no-verify`** — fix the pre-commit hook issue instead
- **Never commit automatically** — only when the user explicitly asks
- **Never use plain `print`** — use Rich console instead
- Conventional commit format required: `feat:`, `fix:`, `docs:`, `chore:`, etc.
- Branch naming enforced: `feature/`, `fix/`, `hotfix/`, `release/`, `poc/`, `backup/`
- Direct commits to `main`, `production`, or `staging` are blocked
