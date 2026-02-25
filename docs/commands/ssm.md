# SSM Port Forwarding with Hostname Support

AWS Systems Manager Session Manager port forwarding with cross-platform hostname resolution support.

## Platform Support

| Feature | Linux | macOS | Windows |
|---------|-------|-------|---------|
| Basic SSM forwarding | ✅ | ✅ | ✅ |
| Hostname forwarding | ✅ | ✅ | ✅ |
| /etc/hosts management | ✅ | ✅ | ✅ (C:\Windows\System32\drivers\etc\hosts) |
| Loopback IPs (127.0.0.x) | ✅ | ✅ | ✅ |

## Requirements by Platform

### All Platforms

**AWS Session Manager Plugin** (required for all platforms):

This is different from AWS CLI and must be installed separately.

| Platform | Installation Guide |
|----------|-------------------|
| Windows | [Install on Windows](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-windows.html) |
| macOS | [Install on macOS](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-macos-overview.html) |
| Linux (Debian/Ubuntu) | [Install on Debian/Ubuntu](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-debian-and-ubuntu.html) |
| Linux (RedHat/CentOS) | [Install on RedHat/CentOS](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-linux.html) |

Verify installation:

```bash
session-manager-plugin
```

### Linux

- `socat` for port forwarding (hostname forwarding feature)
- `sudo` access for /etc/hosts modification

```bash
# Ubuntu/Debian
sudo apt-get install socat

# RHEL/CentOS/Fedora
sudo yum install socat

# Arch
sudo pacman -S socat
```

### macOS

- `socat` for port forwarding (hostname forwarding feature)
- `sudo` access for /etc/hosts modification

```bash
brew install socat
```

### Windows

- `netsh portproxy` (built-in, no installation needed)
- Administrator privileges required **only for hostname forwarding setup** (`devo ssm hosts setup`)

**Important**: Administrator privileges are only needed when setting up hostname forwarding. Regular connections without hostname forwarding (`--no-hosts`) don't require admin rights.

To run commands that need admin privileges:

1. Right-click on Command Prompt or PowerShell
2. Select "Run as administrator"
3. Run `devo ssm hosts setup`

## Quick Start

### 1. Add a database

```bash
devo ssm add-db \
  --name mydb \
  --bastion i-0123456789abcdef0 \
  --host mydb.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --profile dev
```

### 2. Setup hostname forwarding

```bash
devo ssm hosts setup
```

This automatically:
- Assigns unique loopback IPs (127.0.0.2, 127.0.0.3, etc.)
- Updates /etc/hosts with hostname mappings
- Configures port forwarding

### 3. Connect

```bash
# Interactive menu (select database or connect to all)
devo ssm connect

# Or connect directly
devo ssm connect mydb
```

### 4. Use in your applications

Your applications can now use the real hostnames:

```bash
# .env
DATABASE_HOST=mydb.cluster-xyz.us-east-1.rds.amazonaws.com
DATABASE_PORT=5432
```

No code changes needed!

## How It Works

### Architecture

```
Your App -> hostname:port (e.g., mydb.rds.amazonaws.com:5432)
         |
         v
/etc/hosts resolves hostname to 127.0.0.x
         |
         v
Port forwarder (socat/netsh) forwards 127.0.0.x:port -> 127.0.0.1:local_port
         |
         v
AWS SSM Session Manager Plugin creates encrypted tunnel
         |
         v
Bastion instance (EC2 with SSM Agent)
         |
         v
Remote host (RDS, ElastiCache, etc.)
```

### Platform-Specific Implementation

**Linux/macOS**: Uses `socat` to create TCP forwarding from loopback aliases to 127.0.0.1

```bash
socat TCP-LISTEN:5432,bind=127.0.0.2,reuseaddr,fork TCP:127.0.0.1:15432
```

**Windows**: Uses `netsh portproxy` to create port forwarding rules

```cmd
netsh interface portproxy add v4tov4 listenaddress=127.0.0.2 listenport=5432 connectaddress=127.0.0.1 connectport=15432
```

### Why This Architecture?

AWS SSM Session Manager Plugin only binds to `127.0.0.1` (localhost). To enable hostname forwarding with real database hostnames, we:

1. Assign unique loopback IPs (127.0.0.2, 127.0.0.3, etc.) to each database hostname in /etc/hosts
2. Use platform-specific port forwarding to redirect traffic from loopback aliases to 127.0.0.1
3. SSM Session Manager Plugin handles the encrypted tunnel to the remote host

This allows your applications to use real hostnames without code changes.

## Commands Reference

### Database Management

#### `devo ssm add-db`
Add a database configuration.

```bash
devo ssm add-db \
  --name <name> \
  --bastion <instance-id> \
  --host <hostname> \
  --port <port> \
  [--local-port <port>] \
  [--region <region>] \
  [--profile <profile>]
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

**Example:**
```bash
devo ssm add-db \
  --name prod-db \
  --bastion i-0123456789abcdef0 \
  --host prod.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --profile production
```

#### `devo ssm list`
List all configured databases.

```bash
devo ssm list
```

#### `devo ssm remove-db`
Remove a database configuration.

```bash
devo ssm remove-db <name>
```

### Connection Commands

#### `devo ssm connect`
Connect to a database (uses hostname forwarding by default).

```bash
# Interactive menu
devo ssm connect

# Connect to specific database
devo ssm connect <name>

# Override AWS profile
devo ssm connect <name> --profile production

# Disable hostname forwarding (use localhost)
devo ssm connect <name> --no-hosts
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `name` | No | - | Database name (shows menu if omitted) |
| `--profile` | No | Config profile | Override AWS profile for this connection |
| `--no-hosts` | No | `false` | Disable hostname forwarding, use localhost |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Interactive Menu:**
When run without arguments, shows a menu to:
1. Select a specific database
2. Connect to all databases simultaneously

**Profile Override:**
The `--profile` option allows you to temporarily use a different AWS profile than the one configured in the database. Useful for:
- Testing with different credentials
- Accessing the same database from different AWS accounts
- Temporary access without modifying the configuration

**Validation:**
Automatically checks if hostname is configured in /etc/hosts and prompts to run setup if needed.

### Hostname Management

#### `devo ssm hosts setup`
Setup /etc/hosts entries for all configured databases.

```bash
devo ssm hosts setup
```

Automatically:
- Assigns unique loopback IPs
- Updates /etc/hosts
- Saves configuration

#### `devo ssm hosts list`
List all managed /etc/hosts entries.

```bash
devo ssm hosts list
```

#### `devo ssm hosts add`
Add a single database hostname to /etc/hosts.

```bash
devo ssm hosts add <name>
```

#### `devo ssm hosts remove`
Remove a database hostname from /etc/hosts.

```bash
devo ssm hosts remove <name>
```

#### `devo ssm hosts clear`
Remove all managed entries from /etc/hosts.

```bash
devo ssm hosts clear
```

### Instance Management

#### `devo ssm add-instance`
Add an EC2 instance configuration.

```bash
devo ssm add-instance \
  --name <name> \
  --instance-id <id> \
  [--region <region>] \
  [--profile <profile>]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--name` | Yes | - | Instance configuration name |
| `--instance-id` | Yes | - | EC2 instance ID |
| `--region` | No | `us-east-1` | AWS region |
| `--profile` | No | - | AWS profile |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

#### `devo ssm shell`
Connect to an instance via interactive shell.

```bash
devo ssm shell <name>
```

#### `devo ssm list-instances`
List all configured instances.

```bash
devo ssm list-instances
```

#### `devo ssm remove-instance`
Remove an instance configuration.

```bash
devo ssm remove-instance <name>
```

### Configuration Management

#### `devo ssm export`
Export configuration to a file.

```bash
devo ssm export <output-file>
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `output-file` | Yes | - | Path to output file |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**
```bash
devo ssm export team-config.json
```

#### `devo ssm import`
Import configuration from a file.

```bash
# Replace current configuration
devo ssm import <input-file>

# Merge with existing configuration
devo ssm import <input-file> --merge
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `input-file` | Yes | - | Path to input file |
| `--merge` | No | `false` | Merge with existing config instead of replacing |
| `--config-path` | No | `~/.devo/ssm-config.json` | Custom config file path |

**Example:**
```bash
devo ssm import team-config.json --merge
```

#### `devo ssm show-config`
Show the path to the configuration file.

```bash
devo ssm show-config
```

Default location: `~/.devo/ssm-config.json`

### Manual Connection (without config)

#### `devo ssm forward`
Manual port forwarding without saving configuration.

```bash
devo ssm forward \
  --bastion <instance-id> \
  --host <hostname> \
  --port <port> \
  [--local-port <port>] \
  [--region <region>] \
  [--profile <profile>]
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
# PostgreSQL/RDS
devo ssm forward \
  --bastion i-0123456789abcdef0 \
  --host mydb.cluster-xyz.us-east-1.rds.amazonaws.com \
  --port 5432 \
  --profile dev

# Redis/ElastiCache
devo ssm forward \
  --bastion i-0123456789abcdef0 \
  --host redis.cache.amazonaws.com \
  --port 6379 \
  --profile dev
```

## Usage Examples

### Single Database Setup

```bash
# 1. Add database
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

# Your app uses:
# DATABASE_HOST=myapp-dev.cluster-xyz.us-east-1.rds.amazonaws.com
# DATABASE_PORT=5432
```

### Multiple Databases

```bash
# Add multiple databases
devo ssm add-db --name dev-db --bastion i-xxx --host dev.rds.amazonaws.com --port 5432
devo ssm add-db --name prod-db --bastion i-yyy --host prod.rds.amazonaws.com --port 5432
devo ssm add-db --name redis --bastion i-xxx --host redis.cache.amazonaws.com --port 6379

# Setup all at once
devo ssm hosts setup

# Connect to all
devo ssm connect
# Select option: "Connect to all databases"
```

### Team Workflow

```bash
# Team lead exports configuration
devo ssm export team-ssm-config.json

# Share file via git, slack, etc.

# Team members import
devo ssm import team-ssm-config.json

# Each person runs setup
devo ssm hosts setup

# Connect
devo ssm connect
```

### Microservices with Different Environments

```bash
# Add databases for different environments
devo ssm add-db --name myapp-dev --bastion i-dev --host dev.rds.amazonaws.com --port 5432 --profile dev
devo ssm add-db --name myapp-staging --bastion i-staging --host staging.rds.amazonaws.com --port 5432 --profile staging
devo ssm add-db --name myapp-prod --bastion i-prod --host prod.rds.amazonaws.com --port 5432 --profile prod

# Setup
devo ssm hosts setup

# Your microservices use environment variables:
# .env.dev
DATABASE_HOST=dev.rds.amazonaws.com
DATABASE_PORT=5432

# .env.staging
DATABASE_HOST=staging.rds.amazonaws.com
DATABASE_PORT=5432

# .env.prod
DATABASE_HOST=prod.rds.amazonaws.com
DATABASE_PORT=5432

# No code changes needed!
```

## Troubleshooting

### Linux/macOS

**Error: "socat is not installed"**
```bash
# Install socat
brew install socat  # macOS
sudo apt-get install socat  # Ubuntu/Debian
sudo yum install socat  # RHEL/CentOS
```

**Error: "Permission denied" when modifying /etc/hosts**
- The command will prompt for sudo password
- Make sure your user has sudo privileges

**Error: "Connection refused"**

- Verify the bastion instance is running
- Check security groups allow SSM connections
- Ensure SSM agent is installed on bastion
- Verify IAM permissions for SSM sessions

**Error: "SessionManagerPlugin is not found"**

- Install AWS Session Manager Plugin (see Requirements section)
- Verify installation: `session-manager-plugin`
- This is different from AWS CLI and must be installed separately

### Windows

**Error: "Permission denied" or "Access is denied"**

- Run terminal as Administrator
- Right-click Command Prompt/PowerShell → "Run as administrator"
- The tool will show a helpful error message with instructions

**Error: "netsh command failed"**

- Ensure you're running as Administrator
- Check Windows Firewall isn't blocking the ports

**Cleanup netsh rules** (if needed):

```cmd
# List all port proxy rules
netsh interface portproxy show all

# Delete specific rule
netsh interface portproxy delete v4tov4 listenaddress=127.0.0.2 listenport=5432

# Delete all rules
netsh interface portproxy reset
```

### Common Issues

**"Database not found in /etc/hosts"**
```bash
# Run setup to configure hostname forwarding
devo ssm hosts setup
```

**"No databases configured"**
```bash
# Add a database first
devo ssm add-db --name mydb --bastion i-xxx --host mydb.rds.amazonaws.com --port 5432
```

**Multiple databases on same port**
- Each database automatically gets a unique loopback IP
- Port conflicts are avoided by design
- Run `devo ssm list` to see assigned IPs

## Security Notes

- Loopback IPs (127.0.0.x) are only accessible from your local machine
- /etc/hosts entries are managed in a dedicated section with markers (`DEVO-CLI-SSM-START` / `DEVO-CLI-SSM-END`)
- Port forwarding rules are automatically cleaned up when connections are stopped
- All traffic goes through encrypted SSM tunnels (TLS 1.2+)
- No SSH keys or direct bastion access required
- IAM policies control access to SSM sessions
- Requires `ssm:StartSession` permission on the bastion instance
- Bastion instance must have SSM Agent installed and running

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

## Best Practices

1. **Use descriptive names**: `myapp-dev-db` instead of `db1`
2. **Run setup after adding databases**: `devo ssm hosts setup`
3. **Export configuration for team**: Share `ssm-config.json` with team
4. **Use environment-specific profiles**: `--profile dev`, `--profile prod`
5. **Keep configuration in version control**: Add `ssm-config.json` to git (without sensitive data)
6. **Validate connections**: Test with `devo ssm connect` before deploying
7. **Install Session Manager Plugin first**: Verify with `session-manager-plugin` before using SSM commands
8. **Use unique local ports**: Avoid port conflicts by using different local ports for each database
9. **Clean up on exit**: Press Ctrl+C to properly stop connections and clean up port forwarding rules

## See Also

- [AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [SSM Session Manager Plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
- [DynamoDB Commands](dynamodb.md)
- [EventBridge Commands](eventbridge.md)
