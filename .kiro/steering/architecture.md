# Architecture Overview

Devo CLI follows a modular, scalable architecture with clear separation of concerns.

## Project Structure

```
devo-cli/
├── cli_tool/                    # Main package
│   ├── cli.py                   # CLI entry point
│   ├── config.py                # Global configuration
│   ├── _version.py              # Auto-generated version
│   │
│   ├── commands/                # Feature commands
│   │   ├── aws_login/           # AWS SSO authentication
│   │   ├── autocomplete/        # Shell completion
│   │   ├── code_reviewer/       # AI code review
│   │   ├── codeartifact/        # CodeArtifact auth
│   │   ├── commit/              # AI commit messages
│   │   ├── config_cmd/          # Configuration management
│   │   ├── dynamodb/            # DynamoDB utilities
│   │   ├── eventbridge/         # EventBridge management
│   │   ├── ssm/                 # SSM Session Manager
│   │   └── upgrade/             # Self-update system
│   │
│   └── core/                    # Shared infrastructure
│       ├── agents/              # AI agent framework
│       ├── ui/                  # Rich UI components
│       └── utils/               # Shared utilities
│
├── tests/                       # Test suite
├── docs/                        # Documentation
└── .kiro/                       # Kiro IDE configuration
```

## Design Principles

### 1. Modularity

Each command is a self-contained module with its own structure:

```
command_name/
├── __init__.py              # Public API exports
├── README.md                # Command documentation
├── commands/                # CLI definitions
│   ├── __init__.py
│   └── *.py                 # Individual commands
├── core/                    # Business logic
│   ├── __init__.py
│   └── *.py                 # Core classes
└── utils/                   # Command-specific utilities
    ├── __init__.py
    └── *.py                 # Helper functions
```

### 2. Separation of Concerns

**Commands Layer** (`commands/`)
- Click decorators and CLI interface
- User input validation
- Output formatting with Rich
- Error handling and user messages
- NO business logic

**Core Layer** (`core/`)
- Business logic
- Data processing
- API calls
- NO Click dependencies
- NO Rich console output (return data)

**Utils Layer** (`utils/`)
- Helper functions
- Data transformations
- Validators
- Reusable across commands

### 3. Shared Infrastructure

**Core Infrastructure** (`cli_tool/core/`)
- `agents/` - AI agent framework (BaseAgent)
- `ui/` - Rich UI components (console_ui)
- `utils/` - Shared utilities (config_manager, aws, git_utils)

## Key Components

### CLI Entry Point

`cli_tool/cli.py` - Main Click group that:
- Registers all commands
- Handles global options (--profile, --version)
- Manages context passing
- Shows version check notifications

### Configuration System

`cli_tool/core/utils/config_manager.py` - Centralized config:
- JSON-based configuration
- Nested key access with dot notation
- Default values
- Validation

Location: `~/.devo/config.json`

### AI Agent Framework

`cli_tool/core/agents/base_agent.py` - BaseAgent class:
- AWS Bedrock integration
- Pydantic models for structured outputs
- System prompt management
- Tool integration

Used by:
- `commit` - Commit message generation
- `code-reviewer` - Code analysis

### Version Management

`cli_tool/_version.py` - Auto-generated from git tags:
- Uses setuptools_scm
- Semantic versioning
- Fallback to "0.0.0" for development

### Binary Distribution

PyInstaller-based binaries:
- **Linux**: Single executable
- **macOS**: Tarball with onedir structure
- **Windows**: ZIP with onedir structure

## Command Architecture Patterns

### Simple Command

Single command with minimal logic:

```
command_name/
├── __init__.py              # Public API exports (includes CLI command)
├── README.md                # Feature documentation (optional)
├── commands/
│   └── main.py              # Single command implementation
└── core/
    └── processor.py         # Business logic
```

Example: `autocomplete`, `upgrade`

**Key Principles:**
- One file per command (~50-100 lines each)
- CLI command exported from `__init__.py` for direct import in `cli.py`
- All feature code contained within feature directory

### Command Group

Multiple related commands:

```
command_name/
├── __init__.py              # Public API exports
├── README.md                # Feature documentation (optional)
├── commands/
│   ├── __init__.py          # Registers all commands
│   ├── list.py              # List resources (~30-50 lines)
│   ├── add.py               # Create resource (~30-50 lines)
│   └── remove.py            # Delete resource (~20-30 lines)
└── core/
    └── manager.py           # Main service class
```

Example: `config`, `eventbridge`

### Complex Feature

Multiple command groups with subcommands:

```
command_name/
├── __init__.py              # Public API exports
├── README.md                # Feature documentation (optional)
├── commands/                # CLI command definitions
│   ├── __init__.py          # Registers all command groups
│   ├── resource1/           # Command group for resource1
│   │   ├── __init__.py      # Registers resource1 commands
│   │   ├── list.py          # List resources (~30-50 lines)
│   │   ├── add.py           # Create resource (~30-50 lines)
│   │   └── remove.py        # Delete resource (~20-30 lines)
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

Example: `ssm`, `dynamodb`

**Reference Implementation - SSM:**
```
cli_tool/commands/ssm/
├── __init__.py
├── commands/
│   ├── database/            # Database command group
│   │   ├── connect.py       # ~230 lines (complex logic)
│   │   ├── list.py          # ~30 lines
│   │   ├── add.py           # ~25 lines
│   │   └── remove.py        # ~20 lines
│   ├── instance/            # Instance command group
│   │   ├── shell.py         # ~30 lines
│   │   ├── list.py          # ~30 lines
│   │   ├── add.py           # ~25 lines
│   │   └── remove.py        # ~20 lines
│   ├── hosts/               # Hosts command group
│   │   ├── setup.py         # ~80 lines
│   │   ├── list.py          # ~25 lines
│   │   ├── clear.py         # ~20 lines
│   │   ├── add.py           # ~35 lines
│   │   └── remove.py        # ~25 lines
│   ├── forward.py           # Standalone command (~40 lines)
│   └── shortcuts.py         # Shortcuts (~40 lines)
├── core/
│   ├── config.py            # SSMConfigManager
│   ├── session.py           # SSMSession
│   └── port_forwarder.py    # PortForwarder
└── utils/
    └── hosts_manager.py     # HostsManager
```

### AI-Powered Feature

Commands with AI integration:

```
command_name/
├── __init__.py
├── commands/
│   └── analyze.py
├── core/
│   └── analyzer.py          # Extends BaseAgent
├── prompt/
│   ├── system_prompt.py
│   └── rules.py
└── tools/
    └── analysis_tools.py
```

Example: `code-reviewer`

## Data Flow

### User Command Execution

```
User Input
    ↓
CLI Entry Point (cli.py)
    ↓
Command Handler (commands/*.py)
    ↓
Core Business Logic (core/*.py)
    ↓
External Services (AWS, Git, etc.)
    ↓
Response Processing
    ↓
Rich UI Output
    ↓
User
```

### Configuration Access

```
Command
    ↓
config_manager.load_config()
    ↓
~/.devo/config.json
    ↓
Return config dict
    ↓
Command uses config
```

### AI Agent Flow

```
Command
    ↓
Create Agent Instance (extends BaseAgent)
    ↓
Set System Prompt
    ↓
Call AWS Bedrock
    ↓
Parse Structured Output (Pydantic)
    ↓
Return Result
    ↓
Command formats output
```

## Code Organization Rules

### File Naming Conventions

- **Commands:** `snake_case.py` (e.g., `aws_login.py`, `commit_prompt.py`)
- **Modules:** `snake_case.py` (e.g., `config_manager.py`, `git_utils.py`)
- **Classes:** `PascalCase` (e.g., `SSMConfigManager`, `BaseAgent`)
- **Functions:** `snake_case` (e.g., `load_config()`, `get_template()`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `BEDROCK_MODEL_ID`)
- **Private members:** prefix `_` (e.g., `_internal_method`)

### Configuration Management

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

### Command File Structure Example

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

### Command Group Registration Example

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

### Testing Structure

Tests should mirror the source structure:

```
tests/
├── test_feature_name/
│   ├── test_commands.py
│   ├── test_core.py
│   └── test_utils.py
└── test_simple_command.py
```

### Documentation Requirements

Each feature module should have:

1. **README.md** - Feature overview, usage examples
2. **Docstrings** - All public functions and classes
3. **Type hints** - All function signatures

## Benefits of This Architecture

1. **Consistency** - Easy to find code across features
2. **Maintainability** - Clear separation of concerns
3. **Testability** - Business logic isolated from CLI
4. **Scalability** - Easy to add new subcommands (just add new file)
5. **Onboarding** - New developers know where to look
6. **Small Files** - Each command file is 20-100 lines (easy to understand)
7. **Git Friendly** - Less merge conflicts with small, focused files
8. **Discoverability** - File structure mirrors CLI structure

## Build & Distribution

### Development
```bash
pip install -e .
```

### Binary Build
```bash
pyinstaller devo.spec
```

### Release Process
1. Commit with conventional format
2. Push to main branch
3. Semantic Release analyzes commits
4. Creates git tag
5. Builds binaries for all platforms
6. Creates GitHub release
7. Uploads binaries as assets

## Security Considerations

### Credentials
- Never store credentials in code
- Use AWS credential chain
- Support AWS profiles
- Respect environment variables

### Configuration
- Store config in user home directory
- Use JSON for human readability
- Validate all inputs
- Sanitize outputs

### Binary Distribution
- Sign binaries (future)
- Verify downloads with checksums
- Use HTTPS for all downloads
- Automatic security updates

## Performance Optimizations

### Binary Startup
- Onedir format for macOS/Windows (faster)
- Exclude unnecessary modules
- Lazy imports where possible

### AWS Operations
- Reuse boto3 sessions
- Cache credentials
- Parallel operations where safe

### DynamoDB Exports
- Parallel scanning
- Streaming writes
- Compression support

## Future Enhancements

### Planned Features
- Plugin system for custom commands
- Local caching for faster operations
- Offline mode for some commands
- Enhanced error recovery

### Architecture Improvements
- Command dependency injection
- Event-driven architecture
- Async operations
- Better error handling

## Contributing

See [Contributing Guide](development/contributing.md) for:
- Code style guidelines
- Testing requirements
- Pull request process
- Release procedures
