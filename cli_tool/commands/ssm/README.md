# AWS Systems Manager Session Manager

AWS Systems Manager Session Manager integration for secure shell access, database connections, and port forwarding.

## Structure

```
cli_tool/commands/ssm/
├── __init__.py              # Public API exports
├── README.md                # This file
├── commands/                # CLI command definitions
│   ├── __init__.py          # Command registration
│   ├── database/            # Database command group
│   │   ├── __init__.py
│   │   ├── connect.py       # Database connection via SSM
│   │   ├── list.py          # List configured databases
│   │   ├── add.py           # Add database configuration
│   │   └── remove.py        # Remove database configuration
│   ├── instance/            # Instance command group
│   │   ├── __init__.py
│   │   ├── shell.py         # Shell session to instance
│   │   ├── list.py          # List configured instances
│   │   ├── add.py           # Add instance configuration
│   │   └── remove.py        # Remove instance configuration
│   ├── hosts/               # Hosts management group
│   │   ├── __init__.py
│   │   ├── setup.py         # Setup /etc/hosts entries
│   │   ├── list.py          # List configured hosts
│   │   ├── clear.py         # Clear all hosts entries
│   │   ├── add.py           # Add host entry
│   │   └── remove.py        # Remove host entry
│   ├── forward.py           # Port forwarding command
│   └── shortcuts.py         # Command shortcuts
├── core/                    # Business logic
│   ├── __init__.py
│   ├── config.py            # SSMConfigManager
│   ├── session.py           # SSMSession
│   └── port_forwarder.py    # PortForwarder
└── utils/                   # Utilities
    ├── __init__.py
    └── hosts_manager.py     # HostsManager
```

## Requirements

- AWS CLI installed and configured
- Session Manager plugin installed
- AWS credentials with SSM permissions
- For database connections: appropriate database client (psql, mysql, etc.)

## Usage

### Database Connections

```bash
# Add database configuration
devo ssm database add my-db \
  --instance-id i-1234567890abcdef0 \
  --local-port 5432 \
  --remote-port 5432 \
  --database-type postgresql

# Connect to database
devo ssm database connect my-db

# List configured databases
devo ssm database list

# Remove database configuration
devo ssm database remove my-db
```

### Instance Shell Sessions

```bash
# Add instance configuration
devo ssm instance add my-server \
  --instance-id i-1234567890abcdef0

# Start shell session
devo ssm instance shell my-server

# Or use instance ID directly
devo ssm instance shell i-1234567890abcdef0

# List configured instances
devo ssm instance list

# Remove instance configuration
devo ssm instance remove my-server
```

### Port Forwarding

```bash
# Forward local port to remote service
devo ssm forward my-service 8080 \
  --instance-id i-1234567890abcdef0 \
  --local-port 8080 \
  --remote-port 8080

# Access via http://localhost:8080
```

### Hosts Management

```bash
# Setup /etc/hosts entries for all databases
devo ssm hosts setup

# List configured hosts
devo ssm hosts list

# Add custom host entry
devo ssm hosts add my-service 127.0.0.1

# Remove host entry
devo ssm hosts remove my-service

# Clear all managed hosts
devo ssm hosts clear
```

## Features

- Secure shell access to EC2 instances via SSM
- Database connections through SSM tunnels
- Port forwarding for any service
- Automatic /etc/hosts management
- Configuration persistence
- Support for multiple database types (PostgreSQL, MySQL, etc.)
- macOS loopback alias management
- Cross-platform support (Linux, macOS, Windows)

## Architecture

### Commands Layer (`commands/`)
- CLI interface using Click
- User input validation
- Output formatting with Rich
- Command groups for organization

### Core Layer (`core/`)
- `config.py`: Configuration management (SSMConfigManager)
- `session.py`: SSM session handling (SSMSession)
- `port_forwarder.py`: Port forwarding logic (PortForwarder)
- No Click dependencies

### Utils Layer (`utils/`)
- `hosts_manager.py`: /etc/hosts file management
- Platform-specific implementations

## Configuration

Configuration stored in `~/.devo/config.json`:

```json
{
  "ssm": {
    "databases": {
      "my-db": {
        "instance_id": "i-1234567890abcdef0",
        "local_port": 5432,
        "remote_port": 5432,
        "database_type": "postgresql"
      }
    },
    "instances": {
      "my-server": {
        "instance_id": "i-1234567890abcdef0"
      }
    },
    "hosts": {
      "my-db.local": "127.0.0.1"
    }
  }
}
```

## Platform-Specific Notes

### macOS
- Automatically manages loopback aliases for database connections
- Requires sudo for /etc/hosts modifications

### Linux
- Uses standard /etc/hosts management
- Requires sudo for /etc/hosts modifications

### Windows
- Uses Windows hosts file (`C:\Windows\System32\drivers\etc\hosts`)
- Requires administrator privileges for hosts modifications
- Session Manager plugin must be in PATH

## Security

- Uses AWS IAM for authentication
- No SSH keys required
- All traffic encrypted via AWS SSM
- Audit trail in CloudTrail
- No inbound ports needed on instances

## Troubleshooting

### Session Manager Plugin Not Found
```bash
# Install on macOS
brew install --cask session-manager-plugin

# Install on Linux
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "session-manager-plugin.deb"
sudo dpkg -i session-manager-plugin.deb

# Install on Windows
# Download from: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
```

### Permission Denied
Ensure your AWS credentials have the following permissions:
- `ssm:StartSession`
- `ssm:TerminateSession`
- `ec2:DescribeInstances`

### Database Connection Fails
- Verify instance ID is correct
- Check security groups allow traffic from instance to database
- Ensure database client is installed locally
