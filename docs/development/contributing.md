# Contributing to Devo CLI

Thank you for your interest in contributing! This guide will help you get started.

## Quick Start

```bash
git clone <repository-url>
cd devo-cli
make venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
make install
```

### Verify Setup

```bash
devo --help          # Should show CLI commands
devo <TAB>           # Tab completion should work
make test            # Run tests
```

## Daily Development Workflow

```bash
# 1. Activate venv (if not active)
source venv/bin/activate

# 2. Make your changes
# ... edit files ...

# 3. Refresh and test
make refresh
devo <command>

# 4. Run tests
make test
make lint
```

## Making Changes

### 1. Create Feature Branch

```bash
git checkout -b feature/TICKET-123-description
```

Branch naming:

- `feature/<ticket>-description` - New features
- `fix/<ticket>-description` - Bug fixes
- `chore/<ticket>-description` - Maintenance

### 2. Make Changes

Edit files in:

- `cli_tool/commands/` - CLI commands
- `cli_tool/core/agents/` - AI logic
- `cli_tool/core/utils/` - Utilities
- `cli_tool/core/ui/` - UI components
- `tests/` - Tests

### 3. Test Changes

```bash
make refresh         # Refresh shell cache
devo <command>       # Test manually
make test            # Run automated tests
make lint            # Check code style
```

### 4. Commit Changes

```bash
# Use CLI to generate commit message
devo commit

# Or manually:
git commit -m "feat(cli): TICKET-123 add feature"
```

Commit format: `<type>(<scope>): <ticket> <summary>`

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`

See [Semantic Release](../cicd/semantic-release.md) for how commit types map to version bumps.

### 5. Push and Create PR

```bash
git push origin feature/TICKET-123-description
devo commit --pull-request  # Opens PR in browser
```

## Code Style

- Line length: 150 characters
- Indentation: 4 spaces
- All code in English
- Follow PEP 8

### Example

```python
class MyCommand:
    """Command description."""

    DEFAULT_VALUE = "value"

    def execute(self, param: str) -> str:
        """Execute the command."""
        return self._process(param)
```

## Available Commands

```bash
make help          # Show all commands
make install       # Install in editable mode
make test          # Run tests
make lint          # Check code style
make format        # Format code (isort + black)
make clean         # Clean build artifacts
make build-binary  # Build standalone binary
```

## Troubleshooting

### Command not found

```bash
make refresh
```

### Changes not reflected

```bash
make refresh
# or restart terminal
```

### AWS credentials

Get from your organization's AWS SSO portal (configured in `~/.devo/config.json`)

```bash
devo --profile my-profile <command>
```

## Getting Help

- `make help` - Available commands
- `docs/` - Documentation
- Team chat - Ask questions

## Resources

- [Development Setup](setup.md) — environment setup
- [CI/CD Overview](../cicd/overview.md) — how tests and releases work
- [Semantic Release](../cicd/semantic-release.md) — commit types and versioning
- [AWS Profile Support](../guides/aws-setup.md)

Thank you for contributing! 🎉
