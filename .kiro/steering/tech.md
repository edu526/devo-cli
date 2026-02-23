---
inclusion: always
---

# Technology Stack & Development Guidelines

## Python Environment (CRITICAL)

- Python 3.12+ required (check before suggesting code)
- Use `venv` for virtual environments
- Install with: `pip install -r requirements.txt` then `pip install -e .`
- Entry point: `devo` command (defined in setup.py)

## Core Dependencies (Know These)

- **click 8.1.8** - CLI framework (use decorators: @click.command, @click.option, @click.argument)
- **rich 13.0.0+** - Terminal UI (use for formatted output, not plain print statements)
- **strands-agents 1.7.0+** - AI agent framework (extend BaseAgent, use Pydantic for structured outputs)
- **gitpython 3.1.0+** - Git operations (use for reading diffs, branches, staged changes)
- **pydantic** - Data validation (required for all AI agent response models)

## Code Style Rules (ENFORCE)

- Line length: 150 chars max (flake8 configured)
- Indentation: 2 spaces (not 4, check .editorconfig)
- Line endings: LF only (Unix style)
- Import sorting: black profile via isort
- No trailing whitespace
- Final newline: not required

## AWS Integration (Environment Aware)

- **Bedrock**: Claude 3.7 Sonnet (us.anthropic.claude-3-7-sonnet-20250219-v1:0)
- Model ID configurable via `BEDROCK_MODEL_ID` env var
- **CodeArtifact**: Domain configured in config, region `us-east-1`
- Login before publishing: `devo codeartifact-login` or manual aws codeartifact login

## Version Management (NEVER EDIT _version.py)

- Versions auto-generated from git tags via setuptools_scm
- `cli_tool/_version.py` is generated - DO NOT manually edit
- Tag format: `v1.2.3` (semantic versioning)
- Create releases: `./release.sh v1.2.0` or `git tag v1.2.0 && git push origin v1.2.0`
- Fallback version: 0.0.0 (when no tags exist)

## Testing Commands

```bash
pytest                    # Run all tests
pytest --cov=cli_tool    # With coverage
flake8                   # Lint check
isort .                  # Format imports
```

## Build & Publish

```bash
python -m build          # Creates dist/ with wheel and source
twine upload --repository codeartifact dist/*  # After codeartifact login
```

## When Writing Code

1. Use Rich for terminal output (not print)
2. Extend BaseAgent for AI features with Pydantic models
3. Register new commands in `cli_tool/cli.py` via `cli.add_command()`
4. Follow 2-space indentation (not Python's typical 4)
5. Keep lines under 150 chars
6. Use snake_case for modules/functions, PascalCase for classes, UPPER_SNAKE_CASE for constants

## Development Tools

- **pytest** + **pytest-mock** - Testing (tests in `tests/` directory)
- **flake8** - Linting (configured for 150 char lines)
- **setuptools 78.1.0** + **setuptools_scm** - Build and version management
- **build** - Package building (`python -m build`)
- **twine 6.1.0** - Publishing to CodeArtifact
