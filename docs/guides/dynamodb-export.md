# DynamoDB Export Guide

Learn how to export DynamoDB table data to various formats for backup, analysis, and migration.

## Quick Start

```bash
# Export table to CSV
devo dynamodb export my-table

# Export to JSON with compression
devo dynamodb export my-table -f json --compress gzip
```

## Common Use Cases

### Backup Tables

Create regular backups of your DynamoDB tables:

```bash
# Daily backup with timestamp
devo dynamodb export production-users \
  --output backup-$(date +%Y%m%d).json \
  -f json \
  --compress gzip
```

Add to cron for automated backups:

```bash
# Daily at 2 AM
0 2 * * * devo dynamodb export production-users -f json --compress gzip
```

### Data Analysis

Export data for analysis in Excel, Pandas, or other tools:

```bash
# Export to CSV for Excel
devo dynamodb export analytics-data -f csv

# Flatten nested objects for easier analysis
devo dynamodb export analytics-data -f csv --mode flatten
```

### Filtered Exports

Export only specific data:

```bash
# Export active users only
devo dynamodb export users \
  --filter "status = :s" \
  --filter-values '{"s": "active"}'

# Export specific user's data
devo dynamodb export orders \
  --key-condition "userId = :uid" \
  --filter-values '{"uid": "user123"}'
```

### Data Migration

Export from one environment and import to another:

```bash
# Export from production
devo --profile prod dynamodb export users -f jsonl

# Import to staging (using AWS CLI)
aws dynamodb batch-write-item --request-items file://users.jsonl --profile staging
```

## Export Formats

### CSV (Default)

Best for Excel and spreadsheet analysis:

```bash
devo dynamodb export my-table -f csv
```

Output:
```csv
id,name,email,status
1,John,john@example.com,active
2,Jane,jane@example.com,inactive
```

### JSON

Best for programmatic processing:

```bash
devo dynamodb export my-table -f json --pretty
```

Output:
```json
[
  {"id": 1, "name": "John", "email": "john@example.com"},
  {"id": 2, "name": "Jane", "email": "jane@example.com"}
]
```

### JSONL (JSON Lines)

Best for streaming and large datasets:

```bash
devo dynamodb export my-table -f jsonl
```

Output:
```jsonl
{"id": 1, "name": "John", "email": "john@example.com"}
{"id": 2, "name": "Jane", "email": "jane@example.com"}
```

### TSV

Tab-separated format:

```bash
devo dynamodb export my-table -f tsv
```

## Handling Nested Data

### Strings Mode (Default)

Serializes nested objects as JSON strings:

```bash
devo dynamodb export my-table --mode strings
```

Output:
```csv
id,name,metadata
1,John,"{\"age\": 30, \"city\": \"NYC\"}"
```

### Flatten Mode

Flattens nested objects into separate columns:

```bash
devo dynamodb export my-table --mode flatten
```

Output:
```csv
id,name,metadata.age,metadata.city
1,John,30,NYC
```

### Normalize Mode

Expands lists into multiple rows:

```bash
devo dynamodb export my-table --mode normalize
```

Output:
```csv
id,name,tag
1,John,developer
1,John,python
```

## Performance Optimization

### Parallel Scan

For large tables, use parallel scanning:

```bash
# Use 8 parallel segments
devo dynamodb export large-table \
  --parallel-scan \
  --segments 8
```

Recommended segments by table size:

- Small (<1GB): 2-4 segments
- Medium (1-10GB): 4-8 segments
- Large (>10GB): 8-16 segments

### Limit Results

Export only a subset of data:

```bash
# Export first 1000 items
devo dynamodb export my-table --limit 1000
```

## Using Templates

### Save Export Configuration

Save frequently used export configurations:

```bash
devo dynamodb export my-table \
  -a "id,name,email,status" \
  --filter "status = :s" \
  --filter-values '{"s": "active"}' \
  --save-template active-users
```

### Use Saved Template

Reuse saved configurations:

```bash
devo dynamodb export my-table --use-template active-users
```

### List Templates

View all saved templates:

```bash
devo dynamodb list-templates
```

## Filtering Data

### Simple Filter

```bash
devo dynamodb export users \
  --filter "age > :age" \
  --filter-values '{"age": 18}'
```

### Multiple Conditions

```bash
devo dynamodb export users \
  --filter "status = :s AND age > :age" \
  --filter-values '{"s": "active", "age": 18}'
```

### Query with Key Condition

```bash
devo dynamodb export orders \
  --key-condition "userId = :uid AND orderDate > :date" \
  --filter-values '{"uid": "user123", "date": "2024-01-01"}'
```

### Using Index

```bash
devo dynamodb export users \
  --index email-index \
  --key-condition "email = :email" \
  --filter-values '{"email": "john@example.com"}'
```

## Customizing Output

### Select Specific Attributes

```bash
devo dynamodb export users -a "id,name,email"
```

### Custom Delimiter

```bash
devo dynamodb export users --delimiter "|"
```

### Boolean Format

```bash
# Numeric format (1/0)
devo dynamodb export users --bool-format numeric

# Uppercase (True/False)
devo dynamodb export users --bool-format uppercase
```

### Null Values

```bash
# Use "NULL" for null values
devo dynamodb export users --null-value "NULL"
```

### Include Metadata

```bash
# Add metadata header with export info
devo dynamodb export users --metadata
```

## Team Workflows

### Share Export Templates

```bash
# Export configuration
devo dynamodb export users \
  -a "id,name,email" \
  --save-template user-export

# Share template file with team
# Templates stored in: ~/.devo/dynamodb-templates/
```

### Automated Reports

Create scheduled exports:

```bash
#!/bin/bash
# daily-report.sh

DATE=$(date +%Y%m%d)
devo dynamodb export analytics \
  --use-template daily-report \
  --output reports/analytics-$DATE.csv
```

## Troubleshooting

### Access Denied

Verify IAM permissions:

```bash
aws dynamodb list-tables --profile your-profile
```

Required permissions:

- `dynamodb:Scan`
- `dynamodb:Query`
- `dynamodb:DescribeTable`

### Table Not Found

Check region and table name:

```bash
devo dynamodb list --region us-east-1
```

### Export Timeout

For large tables:

1. Use parallel scan: `--parallel-scan --segments 8`
2. Export in chunks: `--limit 10000`
3. Use filters to reduce data: `--filter`

### Memory Issues

For very large exports:
1. Use JSONL format instead of JSON
2. Enable compression: `--compress gzip`
3. Export specific attributes: `-a "id,name"`

## Best Practices

1. **Use compression for large exports**: `--compress gzip`
2. **Save frequently used configurations**: `--save-template`
3. **Use parallel scan for large tables**: `--parallel-scan`
4. **Filter data when possible**: Reduce export size with `--filter`
5. **Choose appropriate format**: CSV for analysis, JSONL for processing
6. **Test with dry-run**: `--dry-run` to preview before exporting
7. **Monitor costs**: DynamoDB charges for read capacity

## Next Steps

- [DynamoDB Command Reference](../commands/dynamodb.md) - Full command options
- [AWS Setup](aws-setup.md) - Configure AWS credentials
- [Configuration Guide](../getting-started/configuration.md) - DynamoDB settings

