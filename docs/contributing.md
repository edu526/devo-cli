# Contributing to Devo CLI

Thank you for your interest in contributing! This guide will help you get started.

## Quick Start for New Contributors

### One Command Setup

```bash
# Clone and setup everything
git clone <repository-url>
cd devo-cli
chmod +x setup-dev.sh
./setup-dev.sh
```

That's it! The script does everything:
- ✅ Creates virtual environment
- ✅ Installs CLI in development mode
- ✅ Installs dependencies
- ✅ Sets up autocompletion
- ✅ Refreshes shell cache

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
git checkout -b feature/NDT-123-description
```

Branch naming:
- `feature/NDT-<ticket>-description` - New features
- `fix/NDT-<ticket>-description` - Bug fixes
- `chore/NDT-<ticket>-description` - Maintenance

### 2. Make Changes

Edit files in:
- `cli_tool/commands/` - CLI commands
- `cli_tool/agents/` - AI logic
- `cli_tool/utils/` - Utilities
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
git commit -m "feat(cli): NDT-123 add feature"
```

Commit format: `<type>(<scope>): NDT-<ticket> <summary>`

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`

### 5. Push and Create PR

```bash
git push origin feature/NDT-123-description
devo commit --pull-request  # Opens PR in browser
```

## Code Style

- Line length: 150 characters
- Indentation: 2 spaces
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
make refresh       # Refresh shell cache
make completion    # Setup autocompletion
make test          # Run tests
make lint          # Check code style
make format        # Format code
make clean         # Clean artifacts
make build         # Build package
```

## Testing

```bash
# Run all tests
make test

# Run specific test
pytest tests/test_commit_prompt.py -v

# With coverage
pytest --cov=cli_tool tests/
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

- [Development Guide](./development.md)
- [AWS Profile Support](./aws-profile.md)
- [CI/CD Pipeline](./cicd.md)

Thank you for contributing! 🎉
