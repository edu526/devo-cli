# devo dynamodb

DynamoDB table management and data export utilities.

## Overview

The `dynamodb` command provides utilities for working with AWS DynamoDB tables, including listing tables, describing table schemas, and exporting table data to various formats.

## Subcommands

### list

List all DynamoDB tables in the current AWS account and region.

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

Show detailed information about a DynamoDB table including schema, indexes, and capacity settings.

```bash
devo dynamodb describe TABLE_NAME [OPTIONS]
```

**Options:**
- `-r, --region TEXT` - AWS region (default: us-east-1)

**Examples:**
```bash
devo dynamodb describe users-table
devo dynamodb describe orders-prod --region us-east-1
```

### export

Export DynamoDB table data to CSV, JSON, JSONL, or TSV format with advanced filtering and formatting options.

```bash
devo dynamodb export TABLE_NAME [OPTIONS]
```

**Options:**

#### Output Options

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file path (default: `<table_name>_<timestamp>.csv`) |
| `-f, --format [csv\|json\|jsonl\|tsv]` | Output format (default: csv) |
| `--compress [gzip\|zip]` | Compress output file |

#### Data Selection

| Option | Description |
|--------|-------------|
| `-l, --limit INTEGER` | Maximum number of items to export |
| `-a, --attributes TEXT` | Comma-separated list of attributes to export |
| `--filter TEXT` | Filter expression for scan/query |
| `--filter-values TEXT` | Expression attribute values as JSON |
| `--filter-names TEXT` | Expression attribute names as JSON |
| `--key-condition TEXT` | Key condition expression for query |
| `--index TEXT` | Global or Local Secondary Index name to use |

#### Formatting Options

| Option | Description |
|--------|-------------|
| `-m, --mode [strings\|flatten\|normalize]` | Export mode (default: strings)<br>• `strings` - Serialize nested objects as JSON strings<br>• `flatten` - Flatten nested objects<br>• `normalize` - Expand lists to multiple rows |
| `--null-value TEXT` | Value for NULL fields in CSV (default: empty string) |
| `--delimiter TEXT` | CSV delimiter (default: comma) |
| `--encoding TEXT` | File encoding (default: utf-8) |
| `--bool-format [lowercase\|uppercase\|numeric\|letter]` | Boolean format (default: lowercase)<br>• `lowercase` - true/false<br>• `uppercase` - True/False<br>• `numeric` - 1/0<br>• `letter` - t/f |
| `--metadata` | Include metadata header in CSV output |
| `--pretty` | Pretty print JSON output (ignored for JSONL) |

#### Performance Options

| Option | Description |
|--------|-------------|
| `--parallel-scan` | Use parallel scan for faster export (experimental) |
| `--segments INTEGER` | Number of parallel scan segments (default: 4) |

#### Other Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would be exported without actually exporting |
| `-y, --yes` | Skip confirmation prompts |
| `--save-template TEXT` | Save current configuration as a template |
| `--use-template TEXT` | Use saved template configuration |

**Examples:**

```bash
# Export entire table to CSV (default)
devo dynamodb export my-table

# Export to JSON with compression
devo dynamodb export my-table -f json --compress gzip

# Export to JSONL (JSON Lines - one object per line)
devo dynamodb export my-table -f jsonl

# Export specific attributes
devo dynamodb export my-table -a "id,name,email,status"

# Export with filter
devo dynamodb export my-table --filter "status = :status" --filter-values '{"status": "active"}'

# Query with key condition
devo dynamodb export my-table --key-condition "userId = :uid" --filter-values '{"uid": "user123"}'

# Export to TSV with custom delimiter
devo dynamodb export my-table -f tsv --delimiter "|"

# Parallel scan for large tables
devo dynamodb export large-table --parallel-scan --segments 8

# Save export configuration as template
devo dynamodb export my-table -a "id,name" --save-template my-export

# Use saved template
devo dynamodb export my-table --use-template my-export
```

### list-templates

List all saved export templates.

```bash
devo dynamodb list-templates
```

**Example:**
```bash
devo dynamodb list-templates
```

## Export Formats

### CSV (default)
Comma-separated values format, compatible with Excel and most data tools.

```csv
id,name,email
1,John,john@example.com
2,Jane,jane@example.com
```

### JSON
Single JSON array containing all records. Good for programmatic processing.

```json
[
  {"id": 1, "name": "John", "email": "john@example.com"},
  {"id": 2, "name": "Jane", "email": "jane@example.com"}
]
```

### JSONL (JSON Lines)
One JSON object per line. Efficient for streaming and large datasets.

```jsonl
{"id": 1, "name": "John", "email": "john@example.com"}
{"id": 2, "name": "Jane", "email": "jane@example.com"}
```

### TSV
Tab-separated values format. Similar to CSV but uses tabs as delimiter.

```tsv
id	name	email
1	John	john@example.com
2	Jane	jane@example.com
```

## Export Modes

The `--mode` option controls how nested data is handled (applies to CSV/TSV):

### strings (default)
Serializes nested objects and lists as JSON strings in CSV.

```csv
id,name,metadata
1,John,"{\"age\": 30, \"city\": \"NYC\"}"
```

### flatten
Flattens nested objects into separate columns.

```csv
id,name,metadata.age,metadata.city
1,John,30,NYC
```

### normalize
Expands lists into multiple rows.

```csv
id,name,tag
1,John,developer
1,John,python
```

## Required Permissions

Your AWS user/role needs these DynamoDB permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
        "dynamodb:Scan",
        "dynamodb:Query"
      ],
      "Resource": "*"
    }
  ]
}
```

## Use Cases

### Backup Tables

```bash
# Export table for backup
devo dynamodb export production-users --output backup-$(date +%Y%m%d).json -f json --compress gzip
```

### Data Analysis

```bash
# Export to CSV for analysis in Excel/Pandas
devo dynamodb export analytics-data -f csv --mode flatten
```

### Filtered Export

```bash
# Export only active users
devo dynamodb export users --filter "status = :s" --filter-values '{"s": "active"}'
```

## Troubleshooting

### Access Denied

Verify IAM permissions:
```bash
aws dynamodb list-tables --profile your-profile
```

### Table Not Found

Check region and table name:
```bash
devo dynamodb list --region us-east-1
```

### Export Timeout

For large tables, use parallel scan:
```bash
devo dynamodb export large-table --parallel-scan --segments 8
```

## See Also

- [Configuration](../getting-started/configuration.md) - AWS configuration
- [AWS Setup](../guides/aws-setup.md) - AWS credentials setup
- [Troubleshooting](../reference/troubleshooting.md) - Common issues
