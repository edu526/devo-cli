# Quick Start Guide

## For New Developers

### One Command Setup

```bash
./setup-dev.sh
```

That's it! This single command will:
1. ✅ Create virtual environment
2. ✅ Install CLI in development mode
3. ✅ Install all dependencies
4. ✅ Setup shell autocompletion
5. ✅ Refresh shell cache

### Verify Installation

```bash
# Check CLI works
devo --help

# Try tab completion
devo <TAB>

# Run tests
make test
```

## Daily Workflow

```bash
# 1. Make changes
# ... edit files ...

# 2. Refresh
make refresh

# 3. Test
devo <command>
make test
```

## Common Commands

```bash
make help          # Show all available commands
make refresh       # Refresh after code changes
make test          # Run tests
make lint          # Check code style
devo commit        # Generate commit message
```

## Need Help?

- Run `make help` for all commands
- Check `docs/contributing.md` for detailed guide
- See `README.md` for full documentation

## First Time?

```bash
# 1. Clone repo
git clone <repository-url>
cd devo-cli

# 2. Run setup
chmod +x setup-dev.sh
./setup-dev.sh

# 3. Start coding!
```

You're ready to contribute! 🚀
