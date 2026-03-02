# Code Organization Standard

## Project Structure Overview

The Devo CLI project follows a clean, scalable architecture that separates commands from core infrastructure:

```
cli_tool/
├── __init__.py
├── _version.py              # Auto-generated from git tags
├── cli.py                   # CLI entry point
├── config.py                # Global configuration
│
├── commands/                # All feature commands
│   ├── __init__.py
│   ├── aws_login/
│   ├── autocomplete/
│   ├── code_reviewer/
│   ├── codeartifact/
│   ├── commit/
│   ├── config_cmd/
│   ├── dynamodb/
│   ├── eventbridge/
│   ├── ssm/
│   └── upgrade/
│
└── core/                    # Core infrastructure (shared)
    ├── __init__.py
    ├── agents/              # AI agent framework
    ├── ui/                  # Rich UI components
    └── utils/               # Shared utilities
```

## Key Benefits

1. **Clear Separation**: Commands vs Core infrastructure
2. **Scalability**: Easy to add new commands without cluttering root
3. **Navigation**: All features in one place (`commands/`)
4. **Import Clarity**:
   - Commands: `from cli_tool.commands.ssm import ssm`
   - Core: `from cli_tool.core.agents import BaseAgent`

## Command Structure

All commands in Devo CLI must follow this standardized structure for consistency and maintainability.

## Directory Structure

### Universal Feature Module Structure

**ALL commands MUST follow this structure, regardless of size or complexity:**

```
cli_tool/commands/feature_name/
├── __init__.py              # Public API exports (includes CLI command)
├── README.md                # Feature documentation (optional)
├── commands/                # CLI command definitions
│   ├── __init__.py          # Registers all command groups
│   ├── resource1/           # Command group for resource1
│   │   ├── __init__.py      # Registers resource1 commands
│   │   ├── list.py          # List resources (~30-50 lines)
│   │   ├── add.py           # Create resource (~30-50 lines)
│   │   ├── remove.py        # Delete resource (~20-30 lines)
│   │   └── update.py        # Update resource (~30-50 lines)
│   ├── resource2/           # Command group for resource2
│   │   ├── __init__.py
│   │   ├── command1.py
│   │   └── command2.py
│   ├── standalone.py        # Standalone command (no group)
│   └── shortcuts.py         # Shortcuts for common commands (optional)
├── core/                    # Business logic (no Click dependencies)
│   ├── __init__.py
│   ├── manager.py           # Main service class
│   └── processor.py         # Data processing
└── utils/                   # Feature-specific utilities (optional)
    ├── __init__.py
    └── helpers.py           # Helper functions
```

**Key Principles:**
- One file per command (~50-100 lines each)
- Commands grouped in subdirectories by domain
- Shortcuts/aliases in separate file
- All feature code contained within feature directory
- CLI command exported from `__init__.py` for direct import in `cli.py`

**Examples:** `commands/ssm/`, `commands/dynamodb/`, `commands/code_reviewer/`

**No exceptions:** Even single-command features use this structure for consistency.

## File Naming Conventions

- **Commands:** `snake_case.py` (e.g., `aws_login.py`, `commit_prompt.py`)
- **Modules:** `snake_case.py` (e.g., `config_manager.py`, `git_utils.py`)
- **Classes:** `PascalCase` (e.g., `SSMConfigManager`, `BaseAgent`)
- **Functions:** `snake_case` (e.g., `load_config()`, `get_template()`)

## Code Examples

### Command File Structure (Individual Command)

```python
"""Command description."""

import click
from rich.console import Console

from cli_tool.feature_name.core import FeatureManager

console = Console()


@click.command()
@click.argument("name")
@click.option("--flag", is_flag=True, help="Flag description")
def command_name(name, flag):
  """Command description."""
  manager = FeatureManager()
  result = manager.do_something(name, flag)
  console.print(f"[green]✓ Success: {result}[/green]")
```

### Command Group Registration (__init__.py)

```python
"""Resource commands."""

import click

from cli_tool.feature_name.commands.resource.add import add_resource
from cli_tool.feature_name.commands.resource.list import list_resources
from cli_tool.feature_name.commands.resource.remove import remove_resource


def register_resource_commands(parent_group):
  """Register resource-related commands."""

  @parent_group.group("resource")
  def resource():
    """Manage resources"""
    pass

  # Register all resource commands
  resource.add_command(list_resources, "list")
  resource.add_command(add_resource, "add")
  resource.add_command(remove_resource, "remove")
```

## Configuration Management

### Centralized Config

All configuration must use the centralized config manager:

```python
from cli_tool.core.utils.config_manager import load_config, save_config

# Read config
config = load_config()
feature_config = config.get("feature_name", {})

# Write config
config["feature_name"] = new_config
save_config(config)
```

### Feature-Specific Config Helpers

Create helper functions in `cli_tool/core/utils/config_manager.py`:

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

### Commands Layer (`cli_tool/commands/feature/commands/`)
- Click decorators and CLI interface
- User input validation
- Output formatting with Rich
- Error handling and user messages
- **NO business logic**

### Core Layer (`cli_tool/commands/feature/core/`)
- Business logic
- Data processing
- API calls
- **NO Click dependencies**
- **NO Rich console output** (return data, let commands format)

### Utils Layer (`cli_tool/commands/feature/utils/`)
- Helper functions
- Data transformations
- Validators
- **Reusable across commands**

### Shared Core (`cli_tool/core/`)
- `agents/` - AI agent framework (BaseAgent)
- `ui/` - Rich UI components (console_ui)
- `utils/` - Shared utilities (config_manager, aws, git_utils)

## Current State

### ✅ All Features Migrated
- `cli_tool/commands/ssm/` - Reference implementation with commands/, core/, utils/
- `cli_tool/commands/dynamodb/` - Well organized with commands/, core/, utils/
- `cli_tool/commands/code_reviewer/` - Good separation with commands/, core/, prompt/, tools/
- `cli_tool/commands/eventbridge/` - Organized with commands/, core/, utils/
- `cli_tool/commands/config_cmd/` - Organized with commands/, core/
- `cli_tool/commands/aws_login/` - Reorganized with commands/, core/
- `cli_tool/commands/upgrade/` - Reorganized with commands/, core/
- `cli_tool/commands/autocomplete/` - Reorganized with commands/, core/
- `cli_tool/commands/codeartifact/` - Reorganized with commands/, core/
- `cli_tool/commands/commit/` - Reorganized with commands/, core/

### ✅ Core Infrastructure
- `cli_tool/core/agents/` - AI agent framework
- `cli_tool/core/ui/` - Rich UI components
- `cli_tool/core/utils/` - Shared utilities

## Migration Completed

### Phase 1: Standardize Features ✅ COMPLETED
All features migrated to standardized structure within their directories.

### Phase 2: Top-Level Reorganization ✅ COMPLETED
- Created `cli_tool/commands/` - All feature commands
- Created `cli_tool/core/` - Shared infrastructure
- Moved all features to `commands/`
- Moved agents, ui, utils to `core/`
- Updated all imports across the codebase

### Phase 3: New Features
All new features must follow the standard structure from day one.

## Examples

### ✅ Good: SSM Structure (Reference Implementation)
```
cli_tool/commands/ssm/
├── __init__.py
├── commands/
│   ├── __init__.py
│   ├── database/            # Database command group
│   │   ├── __init__.py
│   │   ├── connect.py       # ~230 lines (complex logic)
│   │   ├── list.py          # ~30 lines
│   │   ├── add.py           # ~25 lines
│   │   └── remove.py        # ~20 lines
│   ├── instance/            # Instance command group
│   │   ├── __init__.py
│   │   ├── shell.py         # ~30 lines
│   │   ├── list.py          # ~30 lines
│   │   ├── add.py           # ~25 lines
│   │   └── remove.py        # ~20 lines
│   ├── hosts/               # Hosts command group
│   │   ├── __init__.py
│   │   ├── setup.py         # ~80 lines
│   │   ├── list.py          # ~25 lines
│   │   ├── clear.py         # ~20 lines
│   │   ├── add.py           # ~35 lines
│   │   └── remove.py        # ~25 lines
│   ├── forward.py           # Standalone command (~40 lines)
│   └── shortcuts.py         # Shortcuts (~40 lines)
├── core/
│   ├── __init__.py
│   ├── config.py            # SSMConfigManager
│   ├── session.py           # SSMSession
│   └── port_forwarder.py    # PortForwarder
└── utils/
    ├── __init__.py
    └── hosts_manager.py     # HostsManager
```

### ✅ Good: DynamoDB Structure
```
cli_tool/commands/dynamodb/
├── __init__.py
├── commands/
│   ├── __init__.py
│   ├── export_table.py      # Main export command
│   └── list_templates.py    # Template management
├── core/
│   ├── __init__.py
│   ├── exporter.py          # Export logic
│   └── parallel_scanner.py  # Scanning logic
└── utils/
    ├── __init__.py
    ├── templates.py         # Template management
    └── filter_builder.py    # Query building
```

### ❌ Bad: Mixed Structure at Root Level
```
cli_tool/
├── ssm/                     # Feature
├── dynamodb/                # Feature
├── agents/                  # Infrastructure
├── ui/                      # Infrastructure
├── utils/                   # Infrastructure
└── cli.py                   # Entry point
```

### ❌ Bad: Large Single File
```
cli_tool/commands/
└── ssm.py                   # 600+ lines, multiple concerns
```

### ❌ Bad: Missing Subdirectories for Command Groups
```
cli_tool/commands/ssm/commands/
├── database_connect.py      # Should be database/connect.py
├── database_list.py         # Should be database/list.py
├── instance_shell.py        # Should be instance/shell.py
└── instance_list.py         # Should be instance/list.py
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
4. **Scalability** - Easy to add new subcommands (just add new file)
5. **Onboarding** - New developers know where to look
6. **Small Files** - Each command file is 20-100 lines (easy to understand)
7. **Git Friendly** - Less merge conflicts with small, focused files
8. **Discoverability** - File structure mirrors CLI structure
