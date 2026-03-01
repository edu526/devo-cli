# Code Organization Standard

## Command Structure

All commands in Devo CLI must follow this standardized structure for consistency and maintainability.

## Directory Structure

### Simple Commands (Single File)

For commands with minimal logic (< 200 lines):

```
cli_tool/commands/
└── command_name.py          # All logic in one file
```

**Examples:** `upgrade.py`, `completion.py`, `codeartifact_login.py`

### Complex Commands (Feature Module)

For commands with significant logic (> 200 lines) or multiple subcommands:

```
cli_tool/feature_name/
├── __init__.py              # Exports main classes/functions
├── README.md                # Feature documentation (optional)
├── commands/                # Click command definitions
│   ├── __init__.py
│   ├── subcommand1.py
│   └── subcommand2.py
├── core/                    # Business logic
│   ├── __init__.py
│   ├── service.py
│   └── processor.py
└── utils/                   # Feature-specific utilities
    ├── __init__.py
    └── helpers.py

cli_tool/commands/
└── feature_name.py          # Thin wrapper that imports from cli_tool/feature_name/
```

**Examples:** `dynamodb/`, `code_reviewer/`

## File Naming Conventions

- **Commands:** `snake_case.py` (e.g., `aws_login.py`, `commit_prompt.py`)
- **Modules:** `snake_case.py` (e.g., `config_manager.py`, `git_utils.py`)
- **Classes:** `PascalCase` (e.g., `SSMConfigManager`, `BaseAgent`)
- **Functions:** `snake_case` (e.g., `load_config()`, `get_template()`)

## Standard Module Organization

### Feature Module Structure

```
cli_tool/feature_name/
├── __init__.py              # Public API exports
├── README.md                # Feature overview and usage
├── commands/                # CLI command definitions
│   ├── __init__.py
│   ├── list.py             # List resources
│   ├── create.py           # Create resources
│   ├── delete.py           # Delete resources
│   └── update.py           # Update resources
├── core/                    # Business logic (no Click dependencies)
│   ├── __init__.py
│   ├── manager.py          # Main service class
│   └── processor.py        # Data processing
└── utils/                   # Feature-specific utilities
    ├── __init__.py
    └── helpers.py          # Helper functions
```

### Command File Structure

```python
"""Command description."""

import click
from rich.console import Console

from cli_tool.feature_name.core import FeatureManager

console = Console()


@click.group()
def feature_name():
    """Feature description."""
    pass


@feature_name.command("subcommand")
@click.argument("name")
@click.option("--flag", is_flag=True, help="Flag description")
def subcommand(name, flag):
    """Subcommand description."""
    manager = FeatureManager()
    result = manager.do_something(name, flag)
    console.print(f"[green]✓ Success: {result}[/green]")
```

## Configuration Management

### Centralized Config

All configuration must use the centralized config manager:

```python
from cli_tool.utils.config_manager import load_config, save_config

# Read config
config = load_config()
feature_config = config.get("feature_name", {})

# Write config
config["feature_name"] = new_config
save_config(config)
```

### Feature-Specific Config Helpers

Create helper functions in `cli_tool/utils/config_manager.py`:

```python
def get_feature_config() -> Dict:
    """Get feature configuration."""
    config = load_config()
    return config.get("feature_name", {})

def save_feature_config(feature_config: Dict):
    """Save feature configuration."""
    config = load_config()
    config["feature_name"] = feature_config
    save_config(config)
```

## Separation of Concerns

### Commands Layer (`cli_tool/commands/` or `cli_tool/feature/commands/`)
- Click decorators and CLI interface
- User input validation
- Output formatting with Rich
- Error handling and user messages
- **NO business logic**

### Core Layer (`cli_tool/feature/core/`)
- Business logic
- Data processing
- API calls
- **NO Click dependencies**
- **NO Rich console output** (return data, let commands format)

### Utils Layer (`cli_tool/feature/utils/`)
- Helper functions
- Data transformations
- Validators
- **Reusable across commands**

## Current State vs Standard

### ✅ Follows Standard
- `cli_tool/dynamodb/` - Well organized with commands/, core/, utils/
- `cli_tool/code_reviewer/` - Good separation with prompt/, tools/
- `cli_tool/commands/upgrade.py` - Simple, single file

### ⚠️ Needs Refactoring
- `cli_tool/aws_login/` - Should be `cli_tool/aws_login/commands/` structure
- `cli_tool/ssm/` - Missing commands/ subdirectory
- `cli_tool/commands/ssm.py` - Too large (600+ lines), should split into subcommands

## Migration Plan

### Phase 1: Standardize Existing Features
1. Move `cli_tool/aws_login/*.py` → `cli_tool/aws_login/commands/`
2. Split `cli_tool/commands/ssm.py` → `cli_tool/ssm/commands/`
3. Create `cli_tool/ssm/core/` for business logic

### Phase 2: New Features
All new features must follow the standard structure from day one.

## Examples

### Good: DynamoDB Structure
```
cli_tool/dynamodb/
├── __init__.py
├── commands/
│   ├── export_table.py      # Main export command
│   └── list_templates.py    # Template management
├── core/
│   ├── exporter.py          # Export logic
│   └── parallel_scanner.py  # Scanning logic
└── utils/
    ├── templates.py         # Template management
    └── filter_builder.py    # Query building
```

### Bad: Large Single File
```
cli_tool/commands/
└── ssm.py                   # 600+ lines, multiple concerns
```

### Better: Split Structure
```
cli_tool/ssm/
├── commands/
│   ├── connect.py           # Connection commands
│   ├── database.py          # Database management
│   └── instance.py          # Instance management
├── core/
│   ├── session.py           # SSM session logic
│   └── port_forwarder.py    # Port forwarding logic
└── utils/
    └── hosts_manager.py     # /etc/hosts management
```

## Testing Structure

Tests should mirror the source structure:

```
tests/
├── test_feature_name/
│   ├── test_commands.py
│   ├── test_core.py
│   └── test_utils.py
└── test_simple_command.py
```

## Documentation

Each feature module should have:

1. **README.md** - Feature overview, usage examples
2. **Docstrings** - All public functions and classes
3. **Type hints** - All function signatures

## Benefits

1. **Consistency** - Easy to find code across features
2. **Maintainability** - Clear separation of concerns
3. **Testability** - Business logic isolated from CLI
4. **Scalability** - Easy to add new subcommands
5. **Onboarding** - New developers know where to look
