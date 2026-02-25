# Development Setup

## Quick Setup

Use the automated setup script:

```bash
# Clone the repository
git clone <repository-url>
cd devo-cli

# Run setup script
chmod +x setup-dev.sh
./setup-dev.sh
```

The setup script will:
- Create and activate virtual environment
- Install the CLI in development mode
- Install all dependencies
- Setup shell autocompletion
- Refresh shell cache

## Manual Setup

If you prefer manual setup:

```bash
# Create and activate virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate              # Linux/macOS
venv\Scripts\activate                 # Windows CMD/PowerShell
. venv/Scripts/activate               # Windows Git Bash

# Install development dependencies
pip install -r requirements.txt
pip install -e .

# Setup shell completion
devo completion
```

## Building Binaries

```bash
# Build binary for current platform
make build-binary

# Build with platform-specific naming
make build-all

# Test the binary
./dist/devo --version
```

See [Binary Distribution Guide](building.md) for detailed instructions.

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cli_tool

# Run specific test file
pytest tests/test_commit_prompt.py
```

## Code Quality

```bash
# Run linting
flake8 cli_tool/ tests/

# Format imports
isort .
```

## Release Process

This project uses Semantic Release for automated versioning. See [Semantic Release Guide](../cicd/semantic-release.md) for details.

```bash
# Commit with conventional format
git commit -m "feat: add new feature"

# Push to main
git push origin main

# GitHub Actions will automatically:
# - Analyze commits
# - Determine version
# - Create tag
# - Build binaries
# - Create GitHub Release
```
