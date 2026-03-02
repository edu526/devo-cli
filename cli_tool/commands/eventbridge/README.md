# EventBridge

AWS EventBridge rule management utilities.

## Structure

```
cli_tool/commands/eventbridge/
├── __init__.py              # Public API exports
├── README.md                # This file
├── commands/                # CLI command definitions
│   ├── __init__.py          # Command registration
│   └── list.py              # List rules command
├── core/                    # Business logic
│   ├── __init__.py
│   └── rules_manager.py     # RulesManager
└── utils/                   # Utilities
    ├── __init__.py
    └── formatters.py        # Output formatters
```

## Usage

```bash
# List all EventBridge rules
devo eventbridge list

# List rules with specific environment
devo eventbridge list --env prod
devo eventbridge list --env dev

# List rules with specific state
devo eventbridge list --status ENABLED
devo eventbridge list --status DISABLED

# List rules in specific region
devo eventbridge list --region us-west-2

# Output as JSON
devo eventbridge list --output json
```

## Features

- List all EventBridge rules with status
- Filter by environment (dev, staging, prod)
- Filter by rule state (ENABLED, DISABLED, ALL)
- Show rule schedules and targets
- Multiple output formats (table, JSON)
- Rich terminal output with tables
- Environment detection from tags and target names

## Architecture

### Commands Layer (`commands/`)
- CLI interface using Click
- User input validation
- Output formatting with Rich
- No business logic

### Core Layer (`core/`)
- `rules_manager.py`: EventBridge operations (RulesManager)
- AWS SDK integration (boto3)
- Rule listing, target retrieval, tag management
- No Click dependencies

### Utils Layer (`utils/`)
- `formatters.py`: Output formatting utilities
- Table generation for Rich display
- JSON output formatting
- Environment detection logic

## Configuration

Uses AWS credentials from:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS credentials file (`~/.aws/credentials`)
- IAM role (when running on EC2)
- AWS profile (via `--profile` flag)

## Required Permissions

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
