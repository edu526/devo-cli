# EventBridge Command

Check AWS EventBridge scheduled rules status filtered by environment.

## Usage

```bash
devo eventbridge [OPTIONS]
```

## Options

- `--env, -e TEXT` - Filter by environment (e.g., dev, staging, prod)
- `--region, -r TEXT` - AWS region (default: us-east-1)
- `--status, -s [ENABLED|DISABLED|ALL]` - Filter by rule status (default: ALL)
- `--help` - Show help message

## Examples

### List all EventBridge rules

```bash
devo eventbridge
```

### Filter by environment

```bash
devo eventbridge --env dev
devo eventbridge -e prod
```

### Filter by status

```bash
devo eventbridge --status ENABLED
devo eventbridge --status DISABLED
```

### Combine filters

```bash
devo eventbridge --env staging --status ENABLED
devo eventbridge -e prod -s DISABLED -r us-west-2
```

## How It Works

The command filters EventBridge rules by environment using two methods:

1. **Target ARN Pattern Matching**
   - Checks if any target ARN contains `service-<env>-lambda` or `-<env>-lambda`
   - Example: `arn:aws:lambda:us-east-1:123456789:function:service-dev-processor`

2. **Tag Matching**
   - Checks if the rule has an `Env` or `Environment` tag matching the specified environment
   - Example: Tag `Env=dev`

## Output

The command displays a table with:

- **Rule Name** - Name of the EventBridge rule
- **Status** - ✅ ENABLED or ❌ DISABLED
- **Schedule** - Cron or rate expression
- **Targets** - Lambda functions or other targets (max 3 shown)
- **Environment** - Environment tag value

Summary includes:
- Total number of rules found
- Count of enabled vs disabled rules

## Requirements

- AWS credentials configured (via profile or environment variables)
- Permissions required:
  - `events:ListRules`
  - `events:ListTargetsByRule`
  - `events:ListTagsForResource`

## Use Cases

1. **Environment Audit**
   ```bash
   devo eventbridge --env prod
   ```
   Check all production scheduled rules

2. **Find Disabled Rules**
   ```bash
   devo eventbridge --env dev --status DISABLED
   ```
   Identify disabled rules in development

3. **Cross-Region Check**
   ```bash
   devo eventbridge --env prod --region us-west-2
   ```
   Check rules in different regions

4. **Quick Status Overview**
   ```bash
   devo eventbridge --status ENABLED
   ```
   See all active scheduled rules

## Tips

- Use `--env` to focus on specific environments
- Combine with `--status` to find issues (e.g., disabled prod rules)
- Check multiple regions by changing `--region`
- The command respects your AWS profile from `--profile` or `AWS_PROFILE` env var
