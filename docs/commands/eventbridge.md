# devo eventbridge

Check EventBridge scheduled rules status by environment.

## Synopsis

```bash
devo eventbridge [OPTIONS]
```

## Description

Lists and monitors AWS EventBridge scheduled rules with filtering by environment, status, and region. Useful for checking which scheduled tasks are enabled or disabled across environments.

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--env TEXT` | `-e` | Filter by environment (e.g., dev, staging, prod) |
| `--region TEXT` | `-r` | AWS region (default: us-east-1) |
| `--status [enabled\|disabled\|all]` | `-s` | Filter by rule status (default: all) |
| `--output [table\|json]` | `-o` | Output format (default: table) |

## Usage

### Basic Usage

```bash
# List all rules
devo eventbridge

# List rules in specific region
devo eventbridge --region us-west-2

# With specific AWS profile
devo --profile production eventbridge
```

### Filter by Environment

```bash
# Show only dev environment rules
devo eventbridge --env dev

# Show production rules
devo eventbridge --env prod

# Show staging rules
devo eventbridge --env staging
```

### Filter by Status

```bash
# Show only enabled rules
devo eventbridge --status enabled

# Show only disabled rules
devo eventbridge --status disabled

# Show all rules (default)
devo eventbridge --status all
```

### Output Formats

```bash
# Table format (default, human-readable)
devo eventbridge

# JSON format (for scripting/CI/CD)
devo eventbridge --output json
```

### Combined Filters

```bash
# Production enabled rules
devo eventbridge --env prod --status enabled

# Dev disabled rules in us-west-2
devo eventbridge --env dev --status disabled --region us-west-2

# All staging rules as JSON
devo eventbridge --env staging --output json
```

## Output

### Table Format

```
EventBridge Scheduled Rules (us-east-1)

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Rule Name                            ┃ Environment  ┃ Status                               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ daily-backup-prod                    │ prod         │ ENABLED                              │
│ hourly-sync-dev                      │ dev          │ DISABLED                             │
│ weekly-report-staging                │ staging      │ ENABLED                              │
└──────────────────────────────────────┴──────────────┴──────────────────────────────────────┘
```

### JSON Format

```json
[
  {
    "name": "daily-backup-prod",
    "environment": "prod",
    "status": "ENABLED",
    "schedule": "cron(0 2 * * ? *)",
    "description": "Daily backup job"
  },
  {
    "name": "hourly-sync-dev",
    "environment": "dev",
    "status": "DISABLED",
    "schedule": "rate(1 hour)",
    "description": "Hourly data sync"
  }
]
```

## Environment Detection

The command detects environment from rule names using common patterns:

- Rules containing `prod`, `production` → prod
- Rules containing `dev`, `development` → dev
- Rules containing `stg`, `staging` → staging
- Rules containing `qa`, `test` → qa

## Examples

### Monitor Production Rules

```bash
# Check all production rules
devo eventbridge --env prod

# Check if any production rules are disabled
devo eventbridge --env prod --status disabled
```

### CI/CD Integration

```bash
# Get JSON output for processing
devo eventbridge --env prod --output json | jq '.[] | select(.status == "DISABLED")'

# Check if specific rule is enabled
devo eventbridge --output json | jq '.[] | select(.name == "my-rule") | .status'
```

### Multi-Region Check

```bash
# Check rules in multiple regions
for region in us-east-1 us-west-2 eu-west-1; do
  echo "=== $region ==="
  devo eventbridge --region $region --env prod
done
```

## Use Cases

1. **Environment Monitoring**: Check which scheduled tasks are running in each environment
2. **Deployment Verification**: Verify rules are enabled/disabled after deployment
3. **Troubleshooting**: Identify disabled rules that should be enabled
4. **Auditing**: Generate reports of scheduled tasks across environments
5. **CI/CD**: Automate checks in deployment pipelines

## Requirements

- AWS credentials with EventBridge read permissions
- `events:ListRules` permission
- `events:DescribeRule` permission (for detailed info)

## Troubleshooting

### No rules found

```
No EventBridge rules found
```

**Possible causes:**

- No rules exist in the region
- Insufficient permissions
- Wrong region specified

**Solution:**

```bash
# Check different region
devo eventbridge --region us-west-2

# Verify AWS credentials
aws sts get-caller-identity
```

### Access denied

```
Error: Access denied
```

**Solution:** Ensure your AWS credentials have EventBridge read permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "events:ListRules",
        "events:DescribeRule"
      ],
      "Resource": "*"
    }
  ]
}
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (access denied, invalid region, etc.) |

## See Also

- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [devo aws-login](aws-login.md) - AWS SSO authentication

## Notes

- Only lists scheduled rules (not event pattern rules)
- Environment detection is based on rule name patterns
- Requires read-only EventBridge permissions
- Output can be piped to other tools for processing
