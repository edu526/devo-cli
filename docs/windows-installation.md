# Windows Installation Guide

Complete guide for installing Devo CLI on Windows systems.

## Quick Install

Open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
```

## Installation Methods

### Method 1: One-Line Install (Recommended)

```powershell
irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex
```

**Pros:**
- Fastest method
- Automatic updates to PATH
- Interactive installation options

**Cons:**
- Errors may close window quickly
- Harder to debug if issues occur

### Method 2: Download and Run Locally

```powershell
# Download the installer
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1" -OutFile "install-devo.ps1"

# Run the installer
.\install-devo.ps1
```

**Pros:**
- Pauses on errors so you can read them
- Pauses on success so you can read instructions
- Easier to debug
- Can inspect the script before running

**Cons:**
- Requires two steps

### Method 3: Manual Installation

```powershell
# Download the binary directly
Invoke-WebRequest -Uri "https://github.com/edu526/devo-cli/releases/latest/download/devo-windows-amd64.exe" -OutFile "devo.exe"

# Move to a directory in your PATH
Move-Item devo.exe "$env:LOCALAPPDATA\Programs\Devo\devo.exe" -Force

# Add to PATH manually
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$UserPath;$env:LOCALAPPDATA\Programs\Devo", "User")
```

## Installation Options

When you run the installer, you'll be prompted to choose an installation location:

### Option 1: System-Wide Installation

- **Location:** `C:\Program Files\Devo`
- **Requires:** Administrator privileges
- **Available to:** All users on the system
- **PATH:** Added to system PATH

**When to use:** Installing for multiple users on a shared machine

**How to run as admin:**
1. Right-click PowerShell
2. Select "Run as Administrator"
3. Run the installer

### Option 2: User-Only Installation (Recommended)

- **Location:** `%LOCALAPPDATA%\Programs\Devo` (e.g., `C:\Users\YourName\AppData\Local\Programs\Devo`)
- **Requires:** No special privileges
- **Available to:** Current user only
- **PATH:** Added to user PATH

**When to use:** Most common scenario, no admin rights needed

### Option 3: Current Directory

- **Location:** Current working directory
- **Requires:** Write access to current directory
- **Available to:** Manual usage only
- **PATH:** Not automatically added

**When to use:** Testing or temporary usage

## Troubleshooting

### Installer Closes Immediately

**Problem:** The PowerShell window closes before you can read the error.

**Solution:** Download and run locally (Method 2):

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1" -OutFile "install-devo.ps1"
.\install-devo.ps1
```

The local version pauses on both errors and success.

### Execution Policy Error

**Error:** `cannot be loaded because running scripts is disabled on this system`

**Solution:** Allow script execution for current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run the installer again.

### Download Fails

**Error:** `Download failed` or `Cannot reach GitHub`

**Possible causes:**
1. No internet connection
2. Firewall blocking GitHub
3. Proxy configuration needed
4. GitHub is down

**Solutions:**

1. Test connectivity:
   ```powershell
   Test-NetConnection github.com -Port 443
   ```

2. Configure proxy (if needed):
   ```powershell
   $env:HTTPS_PROXY = "http://proxy.company.com:8080"
   ```

3. Download manually from browser:
   - Visit: https://github.com/edu526/devo-cli/releases/latest
   - Download: `devo-windows-amd64.exe`
   - Rename to `devo.exe` and move to desired location

### Binary Test Fails

**Error:** `Binary test failed`

**Possible causes:**
1. Corrupted download
2. Antivirus blocking execution
3. Incompatible Windows version

**Solutions:**

1. Check antivirus logs and whitelist the binary
2. Verify Windows version (Windows 10/11 required)
3. Try downloading again
4. Check file integrity (should be ~70-80 MB)

### Access Denied

**Error:** `Access denied` or `Cannot create directory`

**Solutions:**

1. Choose option 2 (user-only installation) instead of option 1
2. Run PowerShell as Administrator for system-wide installation
3. Check disk space and permissions

### Command Not Found After Installation

**Error:** `devo : The term 'devo' is not recognized`

**Solutions:**

1. Restart your terminal (PATH changes require restart)
2. Open a new PowerShell window
3. Verify PATH was updated:
   ```powershell
   $env:Path -split ';' | Select-String "Devo"
   ```

4. Manually add to PATH if needed:
   ```powershell
   $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
   [Environment]::SetEnvironmentVariable("Path", "$UserPath;$env:LOCALAPPDATA\Programs\Devo", "User")
   ```

## Testing Your Installation

### Verify Installation

After installing:

```powershell
# Check version
devo --version

# Show help
devo --help

# Test AWS connection (requires AWS credentials)
devo config show
```

## Uninstallation

### Remove Binary

```powershell
# User installation
Remove-Item "$env:LOCALAPPDATA\Programs\Devo\devo.exe"

# System installation (requires admin)
Remove-Item "C:\Program Files\Devo\devo.exe"
```

### Remove from PATH

```powershell
# User PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$NewPath = ($UserPath -split ';' | Where-Object { $_ -notlike "*Devo*" }) -join ';'
[Environment]::SetEnvironmentVariable("Path", $NewPath, "User")

# System PATH (requires admin)
$SystemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$NewPath = ($SystemPath -split ';' | Where-Object { $_ -notlike "*Devo*" }) -join ';'
[Environment]::SetEnvironmentVariable("Path", $NewPath, "Machine")
```

### Remove Configuration

```powershell
Remove-Item "$env:USERPROFILE\.devo" -Recurse -Force
```

## Advanced Usage

### Install Specific Version

```powershell
# Download installer
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1" -OutFile "install-devo.ps1"

# Install specific version
.\install-devo.ps1 -Version v1.2.0
```

### Custom Installation Directory

```powershell
.\install-devo.ps1 -InstallDir "C:\Tools\Devo"
```

### Silent Installation (Non-Interactive)

```powershell
# Uses default option 2 (user installation)
.\install-devo.ps1 < NUL
```

## PowerShell Commands Reference

### Useful Commands

```powershell
# Check PowerShell version
$PSVersionTable.PSVersion

# List environment variables
Get-ChildItem Env:

# Show PATH
$env:Path -split ';'

# Find command location
Get-Command devo

# Test network connectivity
Test-NetConnection github.com -Port 443

# Download file
Invoke-WebRequest -Uri "URL" -OutFile "filename"

# Execute remote script
Invoke-RestMethod "URL" | Invoke-Expression
# Short form: irm "URL" | iex
```

## Security Considerations

### Script Execution

The installer requires script execution to be enabled. This is safe when:
- You trust the source (official GitHub repository)
- You inspect the script before running
- You use HTTPS URLs only

### Antivirus

Some antivirus software may flag the binary as suspicious because:
- It's a standalone executable
- It's downloaded from the internet
- It makes network requests (AWS Bedrock)

This is a false positive. You can:
1. Verify the source (official GitHub releases)
2. Check file hash against published values
3. Whitelist the binary in your antivirus

### Permissions

The installer requests minimal permissions:
- User installation: No special permissions needed
- System installation: Administrator rights required
- Network access: Required for downloading and AWS API calls

## Getting Help

If you encounter issues not covered here:

1. Check the main [README](../README.md)
2. Review [GitHub Issues](https://github.com/edu526/devo-cli/issues)
3. Open a new issue with:
   - Windows version
   - PowerShell version
   - Error messages
   - Installation method used

## Related Documentation

- [Configuration Guide](./configuration.md)
- [Development Guide](./development.md)
- [Contributing Guidelines](./contributing.md)
