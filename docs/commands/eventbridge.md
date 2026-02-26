# devo eventbridge

Check EventBridge scheduled rules status by environment.

## Overview

The `eventbridge` command lists and filters AWS EventBridge scheduled rules, showing their status, schedules, targets, and environment tags. This is useful for monitoring scheduled Lambda functions and other automated workflows.

## Usage

```bash
devo eventbridge [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-e, --env TEXT` | Filter by environment (e.g., dev, staging, prod) |
| `-r, --region TEXT` | AWS region (default: us-east-1) |
| `-s, --status [ENABLED\|DISABLED\|ALL]` | Filter by rule status (default: ALL) |
| `-o, --output [table\|json]` | Output format (default: table) |
| `--profile TEXT` | AWS profile to use for authentication |

## Examples

### List All Rules

```bash
# List all EventBridge rules in default region
devo eventbridge

# List rules in specific region
devo eventbridge --region us-west-2
```

### Filter by Environment

```bash
# Show only production rules
devo eventbridge --env prod

# Show only development rules
devo eventbridge --env dev

# Show staging rules
devo eventbridge --env staging
```

### Filter by Status

```bash
# Show only enabled rules
devo eventbridge --status ENABLED

# Show only disabled rules
devo eventbridge --status DISABLED

# Show all rules (default)
devo eventbridge --status ALL
```

### JSON Output

```bash
# Output as JSON for scripting
devo eventbridge --output json

# Filter and output as JSON
devo eventbridge --env prod --status ENABLED --output json
```

### Use with AWS Profile

```bash
# Use specific AWS profile
devo --profile production eventbridge

# Or use command-level profile option
devo eventbridge --profile production --env prod
```

## Output Format

### Table Output (Default)

Displays rules in a formatted table with:

- **Rule Name**: EventBridge rule name
- **Status**: ✅ ENABLED or ❌ DISABLED
- **Schedule**: Cron or rate expression
- **Targets**: Lambda functions or other AWS services
- **Env**: Environment tag (dev, staging, prod, etc.)

### JSON Output

Returns structured JSON with:

- `name`: Rule name
- `arn`: Rule ARN
- `state`: ENABLED or DISABLED
- `schedule`: Schedule expression
- `description`: Rule description
- `targets`: Array of target configurations
- `tags`: Rule tags

## Environment Detection

The command detects environment in multiple ways:

| Method | Description |
|--------|-------------|
| **Tags** | Checks for `Env` or `Environment` tags on the rule |
| **Target Names** | Extracts environment from Lambda function names (e.g., `service-prod-lambda`) |
| **Common Patterns** | Recognizes standard environment names (dev, staging, prod, test, qa, uat, demo) |

## Use Cases

### Monitor Production Rules

```bash
# Check all production scheduled rules
devo eventbridge --env prod
```

### Find Disabled Rules

```bash
# Find disabled rules that might need attention
devo eventbridge --status DISABLED
```

### Audit Scheduled Jobs

```bash
# Export all rules to JSON for auditing
devo eventbridge --output json > eventbridge-audit.json
```

### Cross-Region Check

```bash
# Check rules in multiple regions
devo eventbridge --region us-east-1 --env prod
devo eventbridge --region us-west-2 --env prod
devo eventbridge --region eu-west-1 --env prod
```

## Required Permissions

Your AWS user/role needs these EventBridge permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "events:ListRules",
        "events:ListTargetsByRule",
        "events:ListTagsForResource"
      ],
      "Resource": "*"
    }
  ]
}
```

## Troubleshooting

### Access Denied

Verify IAM permissions:
```bash
aws events list-rules --profile your-profile
```

### No Rules Found

Check region and environment filter:
```bash
# List all rules without filters
devo eventbridge --status ALL

# Check different region
devo eventbridge --region us-west-2
```

### Environment Not Detected

If environment is not detected automatically:

1. Add `Env` or `Environment` tag to the rule
2. Use standard naming patterns in Lambda function names (e.g., `service-prod-lambda`)

## See Also

- [Configuration](../getting-started/configuration.md) - AWS configuration
- [AWS Setup](../guides/aws-setup.md) - AWS credentials setup
- [Troubleshooting](../reference/troubleshooting.md) - Common issues
- [AWS EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
