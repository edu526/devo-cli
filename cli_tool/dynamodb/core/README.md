# DynamoDB Core Modules

This directory contains the core business logic for DynamoDB operations, separated from CLI concerns.

## Modules

### `exporter.py`
Main DynamoDB export functionality. Handles reading data from tables and writing to various formats (CSV, JSON, JSONL).

### `parallel_scanner.py`
Parallel scan implementation for faster exports of large tables. Splits table into segments and scans them concurrently.

### `query_optimizer.py`
**Smart query optimization** - Automatically detects when filters can use indexes for better performance.

Features:
- Auto-detects partition key equality conditions in filters
- Identifies usable GSI/LSI indexes
- Handles OR conditions with multiple indexed attributes
- Suggests optimal query strategies

Example:
```python
# User provides simple filter
filter = "userId = user123"

# query_optimizer automatically:
# 1. Detects userId is a partition key
# 2. Converts to KeyConditionExpression
# 3. Uses Query instead of Scan (much faster!)
```

### `multi_query_executor.py`
Executes multiple queries in parallel for OR-optimized filters.

When a filter has OR conditions with multiple indexed attributes:
```python
filter = "userId = user1 OR email = user@example.com"
```

The executor:
1. Splits into separate queries (one per indexed attribute)
2. Executes queries in parallel
3. Deduplicates results by primary key
4. Combines into single result set

This is much faster than a full table scan with filter.

## Design Philosophy

### Separation of Concerns
- **Commands** (`cli_tool/dynamodb/commands/`) - CLI interface, Click decorators, user interaction
- **Core** (`cli_tool/dynamodb/core/`) - Business logic, no CLI dependencies
- **Utils** (`cli_tool/dynamodb/utils/`) - Helper functions, templates, filters

### Auto-Detection Over Manual Configuration
Users should rarely need to specify `--key-condition` or `--index` manually. The query optimizer handles this automatically in 90% of cases.

**Simple usage (recommended):**
```bash
devo dynamodb export my-table --filter "userId = user123"
```

**Advanced usage (rarely needed):**
```bash
devo dynamodb export my-table --key-condition "userId = :uid" --filter-values '{":uid": "user123"}'
```

### Benefits
1. **Easier to use** - Users don't need to understand DynamoDB internals
2. **Better performance** - Automatic optimization uses the fastest query method
3. **Testable** - Core logic can be tested without CLI
4. **Reusable** - Core modules can be used in other contexts (APIs, scripts, etc.)
