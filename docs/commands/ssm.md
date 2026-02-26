# devo ssm

AWS Systems Manager Session Manager port forwarding with hostname support.

## Synopsis

```bash
devo ssm <subcommand> [OPTIONS]
```

## Description

Manages SSM port forwarding connections to private databases and services through bastion instances. Supports hostname forwarding using /etc/hosts and loopback IPs for seamless application integration.

## Subcommands

### Database Management

#### add-db

Add a database configuration.

```bash
devo ssm add-db --name NAME --bastion INSTANCE_ID --host HOSTNAME --port PORT [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--name` | Yes | - | Configuration name |
| `--bastion` | Yes | - | Bastion instance ID |
| `--host` | Yes | - | Database hostname |
| `--port` | Yes | - | Remote port |
| `--local-port` | No | Same as `--port` | Local port for forwarding |
| `--region` | No | `us-east-1` | AWS region |
| `--profile` | No | - | AWS profile |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

#### list

List all configured databases.

```bash
devo ssm list
```

#### remove-db

Remove a database configuration.

```bash
devo ssm remove-db NAME
```

### Connection Commands

#### connect

Connect to a database (uses hostname forwarding by default).

```bash
devo ssm connect [NAME] [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `NAME` | No | - | Database name (shows menu if omitted) |
| `--profile` | No | Config profile | Override AWS profile for this connection |
| `--no-hosts` | No | `false` | Disable hostname forwarding, use localhost |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

### Hostname Management

#### hosts setup

Setup /etc/hosts entries for all configured databases.

```bash
devo ssm hosts setup
```

Automatically assigns unique loopback IPs, updates /etc/hosts, and saves configuration.

#### hosts list

List all managed /etc/hosts entries.

```bash
devo ssm hosts list
```

#### hosts add

Add a single database hostname to /etc/hosts.

```bash
devo ssm hosts add NAME
```

#### hosts remove

Remove a database hostname from /etc/hosts.

```bash
devo ssm hosts remove NAME
```

#### hosts clear

Remove all managed entries from /etc/hosts.

```bash
devo ssm hosts clear
```

### Instance Management

#### add-instance

Add an EC2 instance configuration.

```bash
devo ssm add-instance --name NAME --instance-id ID [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--name` | Yes | - | Instance configuration name |
| `--instance-id` | Yes | - | EC2 instance ID |
| `--region` | No | `us-east-1` | AWS region |
| `--profile` | No | - | AWS profile |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

#### shell

Connect to an instance via interactive shell.

```bash
devo ssm shell NAME
```

#### list-instances

List all configured instances.

```bash
devo ssm list-instances
```

#### remove-instance

Remove an instance configuration.

```bash
devo ssm remove-instance NAME
```

### Configuration Management

#### export

Export configuration to a file.

```bash
devo ssm export OUTPUT_FILE [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `OUTPUT_FILE` | Yes | - | Path to output file |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

#### import

Import configuration from a file.

```bash
devo ssm import INPUT_FILE [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `INPUT_FILE` | Yes | - | Path to input file |
| `--merge` | No | `false` | Merge with existing config instead of replacing |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

#### show-config

Show the path to the configuration file.

```bash
devo ssm show-config
```

Default location: `~/.devo/ssm-config.json`

### Manual Connection

#### forward

Manual port forwarding without saving configuration.

```bash
devo ssm forward --bastion INSTANCE_ID --host HOSTNAME --port PORT [OPTIONS]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--bastion` | Yes | - | Bastion instance ID |
| `--host` | Yes | - | Database/service hostname |
| `--port` | No | `5432` | Remote port |
| `--local-port` | No | Same as `--port` | Local port for forwarding |
| `--region` | No | `us-east-1` | AWS region |
| `--profile` | No | - | AWS profile |

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

## Examples

```bash
# Add database
devo ssm add-db --name mydb --bastion i-xxx --host db.rds.amazonaws.com --port 5432

# Setup hostname forwarding
devo ssm hosts setup

# Connect to database
devo ssm connect mydb

# Connect without hostname forwarding
devo ssm connect mydb --no-hosts

# Export configuration
devo ssm export team-config.json

# Import configuration
devo ssm import team-config.json --merge
```

## See Also

- [SSM Port Forwarding Guide](../guides/ssm-port-forwarding.md) - Complete setup and usage guide
- [AWS Setup](../guides/aws-setup.md) - Configure AWS credentials
- [DynamoDB Commands](dynamodb.md) - DynamoDB table management
