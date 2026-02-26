# SSM Port Forwarding Guide

Learn how to securely connect to private databases and services using AWS Systems Manager Session Manager with hostname support.

## Quick Start

```bash
# 1. Add database
devo ssm add-db \
  --name mydb \
  --bastion i-0123456789abcdef0 \
  --host mydb.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 5432

# 2. Setup hostname forwarding
devo ssm hosts setup

# 3. Connect
devo ssm connect mydb
```

Your application can now use the real hostname without code changes!

## How It Works

```
Your App -> mydb.rds.amazonaws.com:5432
         |
         v
/etc/hosts resolves to 127.0.0.2
         |
         v
Port forwarder -> 127.0.0.1:local_port
         |
         v
SSM Session Manager (encrypted tunnel)
         |
         v
Bastion Instance
         |
         v
Database (RDS, ElastiCache, etc.)
```

## Prerequisites

### Install Session Manager Plugin

This is required for all platforms and is different from AWS CLI:

```bash
# Verify installation
session-manager-plugin
```

Installation guides:

- [Windows](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-windows.html)
- [macOS](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-macos-overview.html)
- [Linux (Debian/Ubuntu)](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-debian-and-ubuntu.html)
- [Linux (RedHat/CentOS)](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-linux.html)

### Platform-Specific Requirements

**Linux/macOS:**
```bash
# Install socat
brew install socat  # macOS
sudo apt-get install socat  # Ubuntu/Debian
```

**Windows:**

- Run terminal as Administrator for hostname forwarding setup
- `netsh portproxy` is built-in, no installation needed

## Common Workflows

### Single Database Setup

Connect to one database:

```bash
# 1. Add database configuration
devo ssm add-db \
  --name myapp-dev \
  --bastion i-0123456789abcdef0 \
  --host myapp-dev.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --profile dev

# 2. Setup hostname forwarding
devo ssm hosts setup

# 3. Connect
devo ssm connect myapp-dev
```

Your application uses:
```bash
# .env
DATABASE_HOST=myapp-dev.cluster-xyz.us-east-1.rds.amazonaws.com
DATABASE_PORT=5432
```

No code changes needed!

### Multiple Databases

Connect to multiple databases simultaneously:

```bash
# Add databases
devo ssm add-db --name dev-db --bastion i-xxx --host dev.rds.amazonaws.com --port 5432
devo ssm add-db --name prod-db --bastion i-yyy --host prod.rds.amazonaws.com --port 5432
devo ssm add-db --name redis --bastion i-xxx --host redis.cache.amazonaws.com --port 6379

# Setup all at once
devo ssm hosts setup

# Connect to all
devo ssm connect
# Select: "Connect to all databases"
```

Each database gets a unique loopback IP automatically, avoiding port conflicts.

### Team Configuration Sharing

Share database configurations with your team:

```bash
# Team lead exports configuration
devo ssm export team-ssm-config.json

# Share file via git, Slack, etc.

# Team members import
devo ssm import team-ssm-config.json

# Each person runs setup
devo ssm hosts setup

# Connect
devo ssm connect
```

### Multi-Environment Setup

Manage databases across different environments:

```bash
# Add databases for each environment
devo ssm add-db \
  --name myapp-dev \
  --bastion i-dev \
  --host dev.rds.amazonaws.com \
  --port 5432 \
  --profile dev

devo ssm add-db \
  --name myapp-staging \
  --bastion i-staging \
  --host staging.rds.amazonaws.com \
  --port 5432 \
  --profile staging

devo ssm add-db \
  --name myapp-prod \
  --bastion i-prod \
  --host prod.rds.amazonaws.com \
  --port 5432 \
  --profile prod

# Setup
devo ssm hosts setup
```

Your microservices use environment variables:

```bash
# .env.dev
DATABASE_HOST=dev.rds.amazonaws.com
DATABASE_PORT=5432

# .env.staging
DATABASE_HOST=staging.rds.amazonaws.com
DATABASE_PORT=5432

# .env.prod
DATABASE_HOST=prod.rds.amazonaws.com
DATABASE_PORT=5432
```

No code changes needed across environments!

### Temporary Connection

Quick connection without saving configuration:

```bash
devo ssm forward \
  --bastion i-0123456789abcdef0 \
  --host mydb.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --profile dev
```

## Database Types

### PostgreSQL / RDS

```bash
devo ssm add-db \
  --name postgres-db \
  --bastion i-xxx \
  --host mydb.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 5432
```

### MySQL / Aurora

```bash
devo ssm add-db \
  --name mysql-db \
  --bastion i-xxx \
  --host mydb.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 3306
```

### Redis / ElastiCache

```bash
devo ssm add-db \
  --name redis \
  --bastion i-xxx \
  --host redis.cache.amazonaws.com \
  --port 6379
```

### MongoDB / DocumentDB

```bash
devo ssm add-db \
  --name mongodb \
  --bastion i-xxx \
  --host docdb.cluster-xyz.us-east-1.docdb.amazonaws.com \
  --port 27017
```

## Managing Connections

### List Configured Databases

```bash
devo ssm list
```

### Connect to Specific Database

```bash
devo ssm connect mydb
```

### Connect with Different Profile

Override the configured AWS profile:

```bash
devo ssm connect mydb --profile production
```

Useful for:

- Testing with different credentials
- Accessing same database from different accounts
- Temporary access without modifying configuration

### Connect Without Hostname Forwarding

Use localhost instead of real hostname:

```bash
devo ssm connect mydb --no-hosts
```

Your application uses:
```bash
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

### Stop Connections

Press `Ctrl+C` to stop connections and clean up port forwarding rules.

## Hostname Management

### Setup All Hostnames

```bash
devo ssm hosts setup
```

Automatically:

- Assigns unique loopback IPs (127.0.0.2, 127.0.0.3, etc.)
- Updates /etc/hosts
- Configures port forwarding

### List Managed Hostnames

```bash
devo ssm hosts list
```

### Add Single Hostname

```bash
devo ssm hosts add mydb
```

### Remove Hostname

```bash
devo ssm hosts remove mydb
```

### Clear All Hostnames

```bash
devo ssm hosts clear
```

## EC2 Instance Management

### Add Instance for Shell Access

```bash
devo ssm add-instance \
  --name bastion-dev \
  --instance-id i-0123456789abcdef0 \
  --region us-east-1 \
  --profile dev
```

### Connect to Instance

```bash
devo ssm shell bastion-dev
```

### List Instances

```bash
devo ssm list-instances
```

### Remove Instance

```bash
devo ssm remove-instance bastion-dev
```

## Configuration Management

### View Configuration Path

```bash
devo ssm show-config
```

Default: `~/.devo/ssm-config.json`

### Export Configuration

```bash
devo ssm export team-config.json
```

### Import Configuration

```bash
# Replace current configuration
devo ssm import team-config.json

# Merge with existing
devo ssm import team-config.json --merge
```

## Troubleshooting

### Session Manager Plugin Not Found

Install the plugin (separate from AWS CLI):

```bash
# Verify installation
session-manager-plugin

# If not found, install from AWS documentation
```

### Permission Denied (Linux/macOS)

The tool will prompt for sudo password when modifying /etc/hosts.

### Access Denied (Windows)

Run terminal as Administrator:

1. Right-click Command Prompt/PowerShell
2. Select "Run as administrator"
3. Run `devo ssm hosts setup`

### Connection Refused

Check:

1. Bastion instance is running
2. Security groups allow SSM connections
3. SSM agent is installed on bastion
4. IAM permissions for SSM sessions

### Database Not in /etc/hosts

```bash
# Run setup to configure hostname forwarding
devo ssm hosts setup
```

### Port Already in Use

Each database automatically gets a unique loopback IP, avoiding conflicts. Check configuration:

```bash
devo ssm list
```

### Cleanup Port Forwarding (Windows)

```cmd
# List all port proxy rules
netsh interface portproxy show all

# Delete specific rule
netsh interface portproxy delete v4tov4 listenaddress=127.0.0.2 listenport=5432

# Delete all rules
netsh interface portproxy reset
```

## Security Considerations

- Loopback IPs (127.0.0.x) are only accessible from your local machine
- All traffic goes through encrypted SSM tunnels (TLS 1.2+)
- No SSH keys or direct bastion access required
- IAM policies control access to SSM sessions
- /etc/hosts entries are managed in a dedicated section

## Best Practices

1. **Use descriptive names**: `myapp-dev-db` instead of `db1`
2. **Run setup after adding databases**: `devo ssm hosts setup`
3. **Export configuration for team**: Share `ssm-config.json`
4. **Use environment-specific profiles**: `--profile dev`, `--profile prod`
5. **Install Session Manager Plugin first**: Verify before using SSM commands
6. **Clean up on exit**: Press Ctrl+C to properly stop connections
7. **Test connections**: Verify with `devo ssm connect` before deploying

## Next Steps

- [SSM Command Reference](../commands/ssm.md) - Full command options
- [AWS Setup](aws-setup.md) - Configure AWS credentials
- [DynamoDB Export](dynamodb-export.md) - Export DynamoDB data

