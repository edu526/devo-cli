# DynamoDB

DynamoDB utilities for table management and data export.

## Structure

```
cli_tool/dynamodb/
├── __init__.py              # Public API exports
├── README.md                # This file
├── commands/                # CLI command definitions
│   ├── __init__.py          # Command exports
│   ├── cli.py               # Main CLI group with all commands
│   ├── describe_table.py    # Describe table command logic
│   ├── export_table.py      # Export table command logic
│   ├── list_tables.py       # List tables command logic
│   └── list_templates.py    # List templates command logic
├── core/                    # Business logic
│   ├── __init__.py
│   ├── exporter.py          # Main export logic
│   ├── parallel_scanner.py  # Parallel scan implementation
│   ├── query_optimizer.py   # Query optimization
│   ├── multi_query_executor.py # Multi-query execution
│   └── README.md            # Core documentation
└── utils/                   # Utilities
    ├── __init__.py
    ├── filter_builder.py    # Filter expression builder
    ├── templates.py         # Template management
    └── utils.py             # General utilities
```

## Usage

```bash
# List all tables
devo dynamodb list

# Describe a table
devo dynamodb describe my-table

# Export entire table to CSV
devo dynamodb export my-table

# Export with filter (auto-detects indexes)
devo dynamodb export my-table --filter "userId = user123"

# Export specific attributes
devo dynamodb export my-table -a "id,name,email"

# Export to JSON with compression
devo dynamodb export my-table -f json --compress gzip

# List saved templates
devo dynamodb list-templates
```

## Features

- Table listing and description
- Smart export with multiple formats (CSV, JSON, JSONL, TSV)
- Auto-detection of indexes for optimized queries
- Filter expression support with automatic optimization
- Parallel scanning for faster exports
- Template system for reusable configurations
- Compression support (gzip, zip)
- Multiple export modes (strings, flatten, normalize)

## Architecture

### Commands Layer (`commands/`)
- `cli.py`: Main CLI group with all Click decorators
- Individual command modules: Business logic without Click
- No core business logic in CLI definitions

### Core Layer (`core/`)
- `exporter.py`: Main export orchestration
- `parallel_scanner.py`: Parallel scan implementation
- `query_optimizer.py`: Query optimization and index selection
- `multi_query_executor.py`: Multi-query execution
- No Click dependencies

### Utils Layer (`utils/`)
- `filter_builder.py`: Filter expression parsing and building
- `templates.py`: Template save/load functionality
- `utils.py`: General utility functions
