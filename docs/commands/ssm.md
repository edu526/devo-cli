# devo ssm

AWS Systems Manager Session Manager commands for database and instance connections.

## Synopsis

```bash
devo ssm <command> [OPTIONS]
devo ssm database <subcommand> [OPTIONS]
devo ssm instance <subcommand> [OPTIONS]
devo ssm hosts <subcommand> [OPTIONS]
```

## Description

Manages SSM port forwarding connections to private databases and services through bastion instances. Supports hostname forwarding using /etc/hosts and loopback IPs for seamless application integration.

## Commands

### Shortcuts

#### connect

Shortcut for `devo ssm database connect`.

```bash
devo ssm connect [NAME] [OPTIONS]
```

#### shell

Shortcut for `devo ssm instance shell`.

```bash
devo ssm shell [NAME] [OPTIONS]
```

### database

Manage database connections.

```bash
devo ssm database <subcommand> [OPTIONS]
```

#### database connect

Connect to a configured database (uses hostname forwarding by default).

```bash
devo ssm database connect [NAME] [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `NAME` | No | - | Database name (shows menu if omitted) |
| `--profile` | No | Config profile | Override AWS profile for this connection |
| `--no-hosts` | No | `false` | Disable hostname forwarding, use localhost |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Connect with menu selection
devo ssm database connect

# Connect to specific database
devo ssm database connect mydb

# Connect without hostname forwarding
devo ssm database connect mydb --no-hosts

# Using shortcut
devo ssm connect mydb
```

#### database list

List all configured databases.

```bash
devo ssm database list [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
devo ssm database list
```

#### database add

Add a database configuration.

```bash
devo ssm database add [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--name` | No | Interactive | Configuration name |
| `--bastion` | No | Interactive | Bastion instance ID |
| `--host` | No | Interactive | Database hostname |
| `--port` | No | Interactive | Remote port |
| `--local-port` | No | Same as `--port` | Local port for forwarding |
| `--region` | No | `us-east-1` | AWS region |
| `--profile` | No | - | AWS profile |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Interactive mode
devo ssm database add

# With options
devo ssm database add --name mydb --bastion i-xxx --host db.rds.amazonaws.com --port 5432
```

#### database remove

Remove a database configuration.

```bash
devo ssm database remove [NAME] [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `NAME` | No | Interactive | Database name to remove |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Interactive mode
devo ssm database remove

# Direct removal
devo ssm database remove mydb
```

### instance

Manage EC2 instance connections.

```bash
devo ssm instance <subcommand> [OPTIONS]
```

#### instance shell

Connect to a configured instance via interactive shell.

```bash
devo ssm instance shell [NAME] [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `NAME` | No | Interactive | Instance name (shows menu if omitted) |
| `--profile` | No | Config profile | Override AWS profile for this connection |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Interactive mode
devo ssm instance shell

# Connect to specific instance
devo ssm instance shell bastion-dev

# Using shortcut
devo ssm shell bastion-dev
```

#### instance list

List all configured instances.

```bash
devo ssm instance list [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
devo ssm instance list
```

#### instance add

Add an EC2 instance configuration.

```bash
devo ssm instance add [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--name` | No | Interactive | Instance configuration name |
| `--instance-id` | No | Interactive | EC2 instance ID |
| `--region` | No | `us-east-1` | AWS region |
| `--profile` | No | - | AWS profile |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Interactive mode
devo ssm instance add

# With options
devo ssm instance add --name bastion-dev --instance-id i-xxx --region us-east-1
```

#### instance remove

Remove an instance configuration.

```bash
devo ssm instance remove [NAME] [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `NAME` | No | Interactive | Instance name to remove |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Interactive mode
devo ssm instance remove

# Direct removal
devo ssm instance remove bastion-dev
```

### hosts

Manage /etc/hosts entries for hostname forwarding.

```bash
devo ssm hosts <subcommand> [OPTIONS]
```

#### hosts setup

Setup /etc/hosts entries for all configured databases.

```bash
devo ssm hosts setup [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

Automatically assigns unique loopback IPs, updates /etc/hosts, and saves configuration.

**Example:**

```bash
devo ssm hosts setup
```

#### hosts list

List all /etc/hosts entries managed by Devo CLI.

```bash
devo ssm hosts list [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
devo ssm hosts list
```

#### hosts add

Add a single database hostname to /etc/hosts.

```bash
devo ssm hosts add [NAME] [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `NAME` | No | Interactive | Database name |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Interactive mode
devo ssm hosts add

# Direct addition
devo ssm hosts add mydb
```

#### hosts remove

Remove a database hostname from /etc/hosts.

```bash
devo ssm hosts remove [NAME] [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `NAME` | No | Interactive | Database name |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
# Interactive mode
devo ssm hosts remove

# Direct removal
devo ssm hosts remove mydb
```

#### hosts clear

Remove all Devo CLI managed entries from /etc/hosts.

```bash
devo ssm hosts clear [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**

```bash
devo ssm hosts clear
```

### forward

Manual port forwarding without saving configuration.

```bash
devo ssm forward [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--bastion` | Yes | - | Bastion instance ID |
| `--host` | Yes | - | Database/service hostname |
| `--port` | No | `5432` | Remote port |
| `--local-port` | No | Same as `--port` | Local port for forwarding |
| `--region` | No | `us-east-1` | AWS region |
| `--profile` | No | - | AWS profile |

**Example:**

```bash
devo ssm forward --bastion i-xxx --host db.rds.amazonaws.com --port 5432
```

## Platform Support

| Feature | Linux | macOS | Windows |
|---------|-------|-------|---------|
| Basic SSM forwarding | ✅ | ✅ | ✅ |
| Hostname forwarding | ✅ | ✅ | ✅ |
| /etc/hosts management | ✅ | ✅ | ✅ |
| Loopback IPs (127.0.0.x) | ✅ | ✅ | ✅ |

## Requirements

### All Platforms

- AWS Session Manager Plugin (separate from AWS CLI)
- Verify: `session-manager-plugin`

### Linux/macOS

- `socat` for hostname forwarding
- `sudo` access for /etc/hosts modification

### Windows

- `netsh portproxy` (built-in)
- Administrator privileges for hostname forwarding setup only

## Configuration File Format

Location: `~/.devo/ssm-config.json`

```json
{
  "databases": {
    "mydb": {
      "bastion": "i-0123456789abcdef0",
      "host": "mydb.cluster-xyz.us-east-1.rds.amazonaws.com",
      "port": 5432,
      "local_port": 5432,
      "local_address": "127.0.0.2",
      "region": "us-east-1",
      "profile": "dev"
    }
  },
  "instances": {
    "bastion-dev": {
      "instance_id": "i-0123456789abcdef0",
      "region": "us-east-1",
      "profile": "dev"
    }
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS profile for credentials | Default profile |
| `AWS_REGION` | AWS region | `us-east-1` |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (configuration not found, connection failed, etc.) |

## Common Workflows

### Initial Setup

```bash
# 1. Add a database
devo ssm database add --name mydb --bastion i-xxx --host db.rds.amazonaws.com --port 5432

# 2. Setup hostname forwarding
devo ssm hosts setup

# 3. Connect
devo ssm connect mydb
```

### Daily Usage

```bash
# Connect to database (using shortcut)
devo ssm connect mydb

# Connect to instance shell (using shortcut)
devo ssm shell bastion-dev

# List all databases
devo ssm database list

# List all instances
devo ssm instance list
```

### Team Configuration Sharing

```bash
# Export configuration
devo ssm export team-config.json

# Share team-config.json with team

# Import on another machine
devo ssm import team-config.json --merge
```

### Troubleshooting

```bash
# List current hosts entries
devo ssm hosts list

# Clear all hosts entries
devo ssm hosts clear

# Re-setup hosts
devo ssm hosts setup

# Connect without hostname forwarding
devo ssm connect mydb --no-hosts
```

## See Also

- [SSM Port Forwarding Guide](../guides/ssm-port-forwarding.md) - Complete setup and usage guide
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [DynamoDB Commands](dynamodb.md) - DynamoDB table management
