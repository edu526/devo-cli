# Troubleshooting Guide

Common issues and solutions for Devo CLI.

## Installation Issues

### Command Not Found

**Problem:** `devo: command not found` after installation

**Solutions:**

1. **Restart terminal:**
   ```bash
   # Close and reopen terminal
   # Or reload shell configuration
   source ~/.bashrc  # or ~/.zshrc
   ```

2. **Check PATH:**
   ```bash
   # Verify devo is in PATH
   which devo

   # Add to PATH if needed
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. **Verify installation:**
   ```bash
   # Check if binary exists
   ls -la ~/.local/bin/devo
   ls -la /usr/local/bin/devo
   ```

### Permission Denied

**Problem:** `Permission denied` when running devo

**Solutions:**

```bash
# Make executable
chmod +x ~/.local/bin/devo

# Or reinstall with correct permissions
curl -fsSL https://raw.githubusercontent.com/edu526/devo-cli/main/install.sh | bash
```

### Windows Execution Policy Error

**Problem:** PowerShell blocks script execution

**Solution:**

```powershell
# Allow script execution for current user
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Then retry installation
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
```

## AWS Credentials Issues

### No Credentials Found

**Problem:** `Unable to locate credentials` or `NoCredentialsError`

**Solutions:**

1. **Configure AWS CLI:**
   ```bash
   aws configure
   ```

2. **Use AWS SSO:**
   ```bash
   aws sso login --profile my-profile
   export AWS_PROFILE=my-profile
   ```

3. **Verify credentials:**
   ```bash
   aws sts get-caller-identity
   ```

### Access Denied to Bedrock

**Problem:** `AccessDeniedException` when using AI features

**Solutions:**

1. **Enable Bedrock model access:**
   - Go to AWS Console → Bedrock
   - Navigate to "Model access"
   - Request access to Claude models

2. **Check IAM permissions:**
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "bedrock:InvokeModel",
       "bedrock:InvokeModelWithResponseStream"
     ],
     "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
   }
   ```

3. **Verify region:**
   ```bash
   # Bedrock is not available in all regions
   devo config set aws.region us-east-1
   ```

### Wrong AWS Account/Role

**Problem:** Using wrong AWS account or role

**Solutions:**

```bash
# Check current identity
aws sts get-caller-identity

# Use specific profile
devo --profile production commit

# Set default profile
export AWS_PROFILE=production
```

## Configuration Issues

### Configuration Not Loading

**Problem:** Configuration changes not taking effect

**Solutions:**

1. **Verify configuration file:**
   ```bash
   devo config path
   devo config show
   ```

2. **Validate configuration:**
   ```bash
   devo config validate
   ```

3. **Reset if corrupted:**
   ```bash
   devo config reset
   ```

### Invalid Configuration Values

**Problem:** Configuration validation fails

**Solutions:**

```bash
# Check specific value
devo config get aws.region

# Fix invalid value
devo config set aws.region us-east-1

# Or edit manually
devo config edit
```

## Command-Specific Issues

### Commit Command Issues

**Problem:** `No staged changes found`

**Solution:**

```bash
# Stage changes first
git add .

# Then generate commit message
devo commit
```

**Problem:** Commit message generation fails

**Solutions:**

1. **Check AWS credentials:**
   ```bash
   aws sts get-caller-identity
   ```

2. **Verify Bedrock access:**
   ```bash
   aws bedrock list-foundation-models --region us-east-1
   ```

3. **Try different model:**
   ```bash
   devo config set bedrock.model_id us.anthropic.claude-3-7-sonnet-20250219-v1:0
   ```

### Code Reviewer Issues

**Problem:** Code review fails or returns errors

**Solutions:**

1. **Check diff size:**
   ```bash
   # Large diffs may timeout
   git diff --staged --stat

   # Review smaller chunks
   git add file1.py
   devo code-reviewer
   ```

2. **Verify AWS credentials:**
   ```bash
   aws sts get-caller-identity
   ```

### Upgrade Command Issues

**Problem:** `Failed to download latest version`

**Solutions:**

1. **Check internet connection:**
   ```bash
   curl -I https://github.com
   ```

2. **Verify GitHub access:**
   ```bash
   curl -I https://api.github.com/repos/edu526/devo-cli/releases/latest
   ```

3. **Manual upgrade:**
   ```bash
   # Download manually
   curl -L https://github.com/edu526/devo-cli/releases/latest/download/devo-linux-amd64 -o devo
   chmod +x devo
   sudo mv devo /usr/local/bin/
   ```

### CodeArtifact Login Issues

**Problem:** `Failed to authenticate with CodeArtifact`

**Solutions:**

1. **Check IAM permissions:**
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "codeartifact:GetAuthorizationToken",
       "codeartifact:GetRepositoryEndpoint",
       "codeartifact:ReadFromRepository",
       "sts:GetServiceBearerToken"
     ],
     "Resource": "*"
   }
   ```

2. **Verify configuration:**
   ```bash
   devo config get codeartifact.region
   devo config get codeartifact.account_id
   ```

3. **Use AWS SSO:**
   ```bash
   aws sso login --profile my-profile
   devo --profile my-profile codeartifact-login
   ```

## Performance Issues

### Slow Command Execution

**Problem:** Commands take long time to execute

**Solutions:**

1. **Disable version check:**
   ```bash
   export DEVO_SKIP_VERSION_CHECK=1
   devo commit
   ```

2. **Check network connectivity:**
   ```bash
   ping api.github.com
   ```

3. **Use faster Bedrock model:**
   ```bash
   devo config set bedrock.model_id us.anthropic.claude-3-7-sonnet-20250219-v1:0
   ```

### Large Diff Timeouts

**Problem:** Code review times out on large diffs

**Solutions:**

```bash
# Review smaller chunks
git add specific-files
devo code-reviewer

# Or increase timeout (if supported)
# Split large changes into smaller commits
```

## Shell Completion Issues

### Completion Not Working

**Problem:** Tab completion doesn't work

**Solutions:**

1. **Reload shell configuration:**
   ```bash
   source ~/.bashrc  # or ~/.zshrc
   ```

2. **Verify completion is loaded:**
   ```bash
   # Zsh
   echo $_comps[devo]

   # Bash
   complete -p devo
   ```

3. **Reinstall completion:**
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   eval "$(_DEVO_COMPLETE=bash_source devo)"  # Bash
   eval "$(_DEVO_COMPLETE=zsh_source devo)"   # Zsh
   ```

## Binary Issues

### Antivirus False Positive

**Problem:** Antivirus flags devo binary as malicious

**Solutions:**

1. **Add exception** in antivirus software
2. **Build from source:**
   ```bash
   git clone https://github.com/edu526/devo-cli.git
   cd devo-cli
   ./setup-dev.sh
   make build-binary
   ```

3. **Use Python installation:**
   ```bash
   pip install -e .
   ```

### Binary Won't Execute

**Problem:** Binary fails to run

**Solutions:**

```bash
# Check if executable
ls -la $(which devo)

# Make executable
chmod +x $(which devo)

# Check for missing dependencies (Linux)
ldd $(which devo)
```

## Getting Help

If you can't resolve your issue:

1. **Check documentation:**
   - [Installation Guide](../getting-started/installation.md)
   - [Configuration Guide](../getting-started/configuration.md)
   - [AWS Setup](../guides/aws-setup.md)

2. **Enable debug output:**
   ```bash
   # Set verbose logging (if supported)
   devo --verbose commit
   ```

3. **Report issue:**
   - [GitHub Issues](https://github.com/edu526/devo-cli/issues)
   - Include:
     - Devo version (`devo --version`)
     - Operating system
     - Error message
     - Steps to reproduce

## Common Error Messages

### `NoCredentialsError`

**Cause:** AWS credentials not configured

**Fix:** Run `aws configure` or `aws sso login`

### `AccessDeniedException`

**Cause:** Insufficient IAM permissions

**Fix:** Check IAM permissions for Bedrock/CodeArtifact

### `ModelNotFoundException`

**Cause:** Bedrock model not available in region

**Fix:** Use supported region (us-east-1) or different model

### `ValidationException`

**Cause:** Invalid configuration or parameters

**Fix:** Validate configuration with `devo config validate`

### `ConnectionError`

**Cause:** Network connectivity issues

**Fix:** Check internet connection and firewall settings

## See Also

- [Configuration Reference](configuration.md)
- [Environment Variables](environment.md)
- [AWS Setup Guide](../guides/aws-setup.md)
