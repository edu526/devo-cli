# Devo CLI — Agent Instructions

Devo CLI is a Python-based CLI tool for streamlining daily development workflows and AWS management. Built with Python 3.12+, Click, and Rich.

## Project Structure

```
devo-cli/
├── cli_tool/
│   ├── cli.py                   # CLI entry point
│   ├── config.py                # Global configuration
│   ├── _version.py              # Auto-generated version (DO NOT EDIT)
│   ├── commands/                # Feature commands (one directory per command)
│   │   ├── autocomplete/        # Shell completion setup
│   │   ├── aws_login/           # AWS SSO authentication
│   │   ├── code_reviewer/       # AI code review
│   │   ├── codeartifact/        # CodeArtifact authentication
│   │   ├── commit/              # AI commit message generation
│   │   ├── config_cmd/          # Configuration management
│   │   ├── dynamodb/            # DynamoDB utilities
│   │   ├── eventbridge/         # EventBridge management
│   │   ├── ssm/                 # SSM Session Manager
│   │   └── upgrade/             # Self-update system
│   └── core/
│       ├── agents/              # BaseAgent (AWS Bedrock integration)
│       ├── ui/                  # Rich UI components
│       └── utils/               # config_manager, aws, git_utils
├── tests/
├── docs/                        # MkDocs documentation
```

Each command follows this structure:
- `commands/` — Click decorators, input validation, Rich output. No business logic.
- `core/` — Business logic, API calls. No Click or Rich dependencies.
- `utils/` — Helpers and reusable functions.

## Tech Stack

| Dependency | Version | Usage |
|------------|---------|-------|
| click | 8.1.8 | CLI framework |
| rich | 13.0.0+ | Terminal UI (never use plain `print`) |
| strands-agents | 1.7.0+ | AI agent framework |
| gitpython | 3.1.0+ | Git operations |
| pydantic | latest | Structured outputs for AI agents |
| pytest | latest | Testing |
| flake8 | latest | Linting |
| setuptools_scm | latest | Version from git tags |
| build | latest | Package building |

## Code Style

- **Indentation:** 4 spaces
- **Line length:** 150 chars max
- **Line endings:** LF only
- **Naming:** `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants, `_` prefix for private members
- **Imports:** sorted with isort (black profile)
- **Language:** English only — code, comments, docs, commit messages

## AWS Integration

- **Bedrock model:** `us.anthropic.claude-3-7-sonnet-20250219-v1:0` (configurable via `BEDROCK_MODEL_ID`)
- **Default region:** `us-east-1`
- **Config file:** `~/.devo/config.json`
- Use `load_config()` / `save_config()` from `cli_tool.core.utils.config_manager`

## Version Management

- **NEVER edit `cli_tool/_version.py`** — auto-generated from git tags via `setuptools_scm`
- Versioning is handled automatically by **python-semantic-release** (configured in `pyproject.toml`)
- Tag format: `v1.2.3`
- Releases are triggered automatically on push to `main` based on conventional commits:
  - `feat:` → minor bump (1.0.0 → 1.1.0)
  - `fix:` / `perf:` → patch bump (1.0.0 → 1.0.1)
  - `feat!:` / `BREAKING CHANGE` → major bump (1.0.0 → 2.0.0)
- **Never create tags manually** — let semantic-release handle it

## Adding a New Command

1. Create `cli_tool/commands/your_command/` following the module structure above
2. Register in `cli_tool/cli.py` via `cli.add_command()`
3. Use `BaseAgent` for any AWS Bedrock integration
4. Use `Rich` for all terminal output

## Command Structure Patterns

### Simple Command
Single command with minimal logic (e.g. `autocomplete`, `upgrade`):

```
command_name/
├── __init__.py          # Exports the CLI command
├── commands/
│   └── main.py          # Click command definition
└── core/
    └── processor.py     # Business logic
```

### Command Group
Multiple related subcommands (e.g. `config`, `eventbridge`):

```
command_name/
├── __init__.py
├── commands/
│   ├── __init__.py      # Registers all subcommands
│   ├── list.py
│   ├── add.py
│   └── remove.py
└── core/
    └── manager.py       # Main service class
```

### Complex Feature
Multiple command groups with subcommands (e.g. `ssm`, `dynamodb`):

```
command_name/
├── __init__.py
├── commands/
│   ├── __init__.py      # Registers all command groups
│   ├── resource1/
│   │   ├── __init__.py
│   │   ├── list.py
│   │   ├── add.py
│   │   └── remove.py
│   ├── resource2/
│   │   ├── __init__.py
│   │   └── *.py
│   ├── standalone.py    # Standalone command (no group)
│   └── shortcuts.py     # Optional shortcuts
├── core/
│   ├── manager.py
│   └── processor.py
└── utils/
    └── helpers.py
```

### Bedrock-powered Feature
Commands with AWS Bedrock integration (e.g. `commit`, `code-reviewer`):

```
command_name/
├── __init__.py
├── commands/
│   └── analyze.py
├── core/
│   └── analyzer.py      # Extends BaseAgent
├── prompt/
│   ├── system_prompt.py
│   └── rules.py
└── tools/
    └── analysis_tools.py
```

### Layer Rules

| Layer | Responsibilities | Forbidden |
|-------|-----------------|-----------|
| `commands/` | Click decorators, validation, Rich output | Business logic |
| `core/` | Business logic, API calls | Click, Rich console output |
| `utils/` | Helpers, transformations, validators | — |

## Common Commands

```bash
# Setup
make venv              # Create virtual environment
make install           # Install with all dependencies
make completion        # Setup shell autocompletion

# Development
make test              # Run all tests
make lint              # Run flake8
make format            # Run isort
make refresh           # Refresh shell cache after code changes

# Build
make binary            # Build binary for current platform
make binary-all        # Build for all platforms
```

## Testing

Tests live in `tests/` mirroring the source structure. Use markers to categorize:

```bash
pytest -m unit         # Unit tests (run on pre-push hook)
pytest -m integration  # Integration tests
pytest --cov=cli_tool  # With coverage report
```

## Pre-commit Hooks

Installed via `pre-commit install` + `pre-commit install --hook-type pre-push`.

**On every commit:**
- `black` — code formatting
- `isort` — import sorting
- `flake8` — linting
- `commitizen` — validates conventional commit message format
- Checks: large files, merge conflicts, AWS credentials, private keys

**On push:**
- `pytest -m unit` — unit tests must pass

Never use `--no-verify` to bypass hooks. Fix the issue instead.

## Branch Naming

Enforced by pre-commit. Valid prefixes:

```
feature/   fix/   hotfix/   release/   release-candidate/   poc/   backup/
```

Direct commits to `main`, `production`, or `staging` are blocked.

## Git Rules

- **Never commit automatically** — only when the user explicitly asks
- **Never use `--no-verify`** — fix the hook issue instead
- Commit message format: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, etc.)

After creating or modifying files, always tell the user what changed and let them run git commands. Example:

```
I've updated cli_tool/commands/upgrade.py.

Changes made:
- Added zipfile import
- Modified get_binary_name() to return .zip for Windows

You can review and commit when ready:
  git add cli_tool/commands/upgrade.py
  git commit -m "fix(upgrade): handle ZIP files on Windows"
```

The assistant may run git commands **only** when the user explicitly asks ("commit this", "push the changes", "run git status").

## Available Commands

| Command | Description |
|---------|-------------|
| `commit` | AI-powered commit message generation (conventional format, ticket extraction from branch) |
| `code-reviewer` | AI code review with security analysis, severity levels, staged or committed changes |
| `aws-login` | AWS SSO authentication, credential caching, auto-refresh for expiring credentials |
| `codeartifact-login` | CodeArtifact authentication (12-hour tokens, automatic pip config) |
| `dynamodb` | List, describe, export tables (CSV/JSON/JSONL/TSV), filter expressions, parallel scanning |
| `eventbridge` | List/filter EventBridge rules by environment and state, multiple output formats |
| `ssm` | Secure shell, database tunnels, port forwarding, /etc/hosts management |
| `config` | Manage `~/.devo/config.json` with dot-notation key access, JSON export/import |
| `autocomplete` | Setup shell completion (auto-detects bash, zsh, fish) |
| `upgrade` | Self-update with version checking, platform-specific binaries, backup before upgrade |

## Documentation Requirements

Every feature module must include:

1. **README.md** — Feature overview and usage examples
2. **Docstrings** — All public functions and classes
3. **Type hints** — All function signatures

## Binary Distribution

| Platform | Format | Notes |
|----------|--------|-------|
| Linux | Single executable (onefile) | |
| macOS | Tarball with onedir structure | Faster startup |
| Windows | ZIP with onedir structure | Faster startup |

Built with PyInstaller (`devo.spec`). Binaries are uploaded as GitHub release assets by semantic-release.

## Security

- Never store credentials in code — use the AWS credential chain
- Support AWS profiles and respect environment variables
- Store config in `~/.devo/config.json` (user home directory)
- Validate all inputs, sanitize outputs
- Never commit secrets — pre-commit hooks check for AWS credentials and private keys
