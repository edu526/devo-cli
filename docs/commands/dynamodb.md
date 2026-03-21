# devo dynamodb

DynamoDB table management and data export utilities.

## Synopsis

```bash
devo dynamodb <command> [OPTIONS]
```

## Description

Provides utilities for working with AWS DynamoDB tables, including listing tables, describing table schemas, and exporting table data to various formats (CSV, JSON, JSONL, TSV) with advanced filtering and optimization.

## Commands

### list

List all DynamoDB tables in the region.

```bash
devo dynamodb list [OPTIONS]
```

**Options:**

- `-r, --region TEXT` - AWS region (default: us-east-1)

**Examples:**

```bash
# List tables in default region
devo dynamodb list

# List tables in specific region
devo dynamodb list --region us-west-2

# With specific profile
devo --profile production dynamodb list
```

### describe

Show detailed information about a table.

```bash
devo dynamodb describe TABLE_NAME [OPTIONS]
```

**Options:**

- `-r, --region TEXT` - AWS region (default: us-east-1)

**Examples:**

```bash
# Describe table
devo dynamodb describe users-table

# Describe in specific region
devo dynamodb describe orders-prod --region us-east-1
```

**Output includes:**

- Table name and ARN
- Primary key schema
- Global and Local Secondary Indexes
- Item count and table size
- Provisioned/On-Demand capacity
- Stream settings
- Encryption settings

### export

Export DynamoDB table to CSV, JSON, or JSONL format.

```bash
devo dynamodb export TABLE_NAME [OPTIONS]
```

#### Basic Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output file path (default: `<table_name>_<timestamp>.csv`) |
| `--format [csv\|json\|jsonl\|tsv]` | `-f` | Output format (default: csv) |
| `--region TEXT` | `-r` | AWS region (default: us-east-1) |
| `--limit INTEGER` | `-l` | Maximum number of items to export |
| `--attributes TEXT` | `-a` | Comma-separated list of attributes to export |

#### Filtering Options

| Option | Description |
|--------|-------------|
| `--filter TEXT` | Filter expression — handles all types automatically, use this for most cases |
| `--filter-values TEXT` | [Advanced] Manual expression attribute values in DynamoDB typed format — only needed with `--key-condition` or complex manual expressions |
| `--filter-names TEXT` | [Advanced] Expression attribute name substitutions as JSON — only needed for DynamoDB reserved keywords |
| `--key-condition TEXT` | Manual key condition expression for query mode (rarely needed — auto-detected from `--filter`) |
| `--index TEXT` | Force specific GSI/LSI (auto-selected from filter) |

#### Export Modes

| Option | Short | Description |
|--------|-------|-------------|
| `--mode [strings\|flatten\|normalize]` | `-m` | Export mode (see below) |

**Export Modes:**

- `strings` - Serialize complex types as JSON strings
- `flatten` - Flatten nested objects (e.g., `address.city`)
- `normalize` - Expand lists to multiple rows

#### CSV Options

| Option | Description |
|--------|-------------|
| `--null-value TEXT` | Value for NULL fields (default: empty string) |
| `--delimiter TEXT` | CSV delimiter (default: comma) |
| `--encoding TEXT` | File encoding (default: utf-8) |
| `--bool-format [lowercase\|uppercase\|numeric\|letter]` | Boolean format (default: lowercase) |
| `--metadata` | Include metadata header in CSV |

**Boolean Formats:**

- `lowercase` - true/false
- `uppercase` - True/False
- `numeric` - 1/0
- `letter` - t/f

#### JSON Options

| Option | Description |
|--------|-------------|
| `--pretty` | Pretty print JSON output (ignored for JSONL) |

#### Performance Options

| Option | Description |
|--------|-------------|
| `--compress [gzip\|zip]` | Compress output file |
| `--parallel-scan` | Use parallel scan for faster export (experimental) |
| `--segments INTEGER` | Number of parallel scan segments (default: 4) |

#### Template Options

| Option | Description |
|--------|-------------|
| `--save-template TEXT` | Save current configuration as a template |
| `--use-template TEXT` | Use saved template configuration |

#### Other Options

| Option | Short | Description |
|--------|-------|-------------|
| `--dry-run` | | Show what would be exported without exporting |
| `--yes` | `-y` | Skip confirmation prompts |

### list-templates

List all saved export templates.

```bash
devo dynamodb list-templates
```

Shows all templates saved with `--save-template`.

## Examples

### Basic Export

```bash
# Export entire table to CSV
devo dynamodb export my-table

# Export to JSON
devo dynamodb export my-table -f json

# Export to specific file
devo dynamodb export my-table -o data/users.csv

# Export with limit
devo dynamodb export my-table -l 1000
```

## Query Optimization

The export command automatically optimizes queries:

1. **Index Detection**: Analyzes filter expression and selects best index
2. **Query vs Scan**: Uses Query when possible (faster and cheaper)
3. **Projection**: Only fetches requested attributes
4. **Parallel Scan**: Optionally splits scan across multiple segments

### Example: Automatic Optimization

```bash
# This filter expression:
devo dynamodb export users --filter "userId = 'user123'"

# Automatically:
# 1. Detects userId is a key in GSI "userId-index"
# 2. Uses Query instead of Scan
# 3. Much faster and cheaper
```

## Configuration

Export templates are stored in `~/.devo/config.json`:

```json
{
  "dynamodb": {
    "export_templates": {
      "active-users": {
        "table_name": "users",
        "filter_expression": "status = :status",
        "expression_attribute_values": {
          ":status": "active"
        },
        "attributes": ["id", "name", "email"]
      }
    }
  }
}
```

## Performance Tips

1. **Use filters**: Export only needed data
2. **Use projections**: Specify attributes with `-a`
3. **Use parallel scan**: For large tables (>1GB)
4. **Use compression**: For large exports
5. **Use Query**: Let auto-optimization detect indexes

## Troubleshooting

### Export is slow

```bash
# Use parallel scan
devo dynamodb export my-table --parallel-scan --segments 8
```

### Filter not working

```bash
# Check filter syntax
devo dynamodb export my-table --filter "status = 'active'" --dry-run

# Use manual filter values if needed
devo dynamodb export my-table \
  --filter "status = :st" \
  --filter-values '{":st": {"S": "active"}}'

```bash
# Use expression attribute names
devo dynamodb export my-table \
  --filter "#status = :st" \
  --filter-names '{"#status": "status"}' \
  --filter-values '{":st": {"S": "active"}}'
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (table not found, access denied, invalid filter, etc.) |

## See Also

- [DynamoDB Export Guide](../guides/dynamodb-export.md)
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [devo config](config.md) - Manage templates

## Notes

- Requires AWS credentials with DynamoDB read permissions
- Large exports may take time and consume read capacity
- Use `--limit` for testing filters
- Templates are stored in `~/.devo/config.json`
- Parallel scan is experimental and may not work with all filters
