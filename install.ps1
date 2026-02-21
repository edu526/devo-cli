# Devo CLI Installer for Windows
# Downloads and installs the latest Devo CLI binary from GitHub Releases

param(
    [string]$Version = "latest",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

# Configuration
$Repo = "edu526/devo-cli"
$BinaryName = "devo-windows-amd64.exe"

Write-Host "Devo CLI Installer" -ForegroundColor Blue
Write-Host ""

# Determine download URL
if ($Version -eq "latest") {
    $DownloadUrl = "https://github.com/$Repo/releases/latest/download/$BinaryName"
} else {
    $DownloadUrl = "https://github.com/$Repo/releases/download/$Version/$BinaryName"
}

Write-Host "Platform: Windows-amd64" -ForegroundColor Blue
Write-Host "Version: $Version" -ForegroundColor Blue
Write-Host ""

# Download binary
Write-Host "Downloading Devo CLI..." -ForegroundColor Blue
$TempFile = Join-Path $env:TEMP "devo.exe"

try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $TempFile -UseBasicParsing
    Write-Host "Download complete" -ForegroundColor Green
} catch {
    Write-Host "Download failed" -ForegroundColor Red
    Write-Host "Please check:" -ForegroundColor Yellow
    Write-Host "  1. The URL is correct: $DownloadUrl"
    Write-Host "  2. You have internet connection"
    Write-Host "  3. The version exists"
    exit 1
}

# Test the binary
Write-Host ""
Write-Host "Testing binary..." -ForegroundColor Blue
try {
    $output = & $TempFile --version 2>&1
    Write-Host $output
    Write-Host "Binary verified" -ForegroundColor Green
} catch {
    Write-Host "Binary test failed" -ForegroundColor Red
    Remove-Item $TempFile -ErrorAction SilentlyContinue
    exit 1
}

Write-Host ""

# Determine installation directory
if ($InstallDir -eq "") {
    # Check if running interactively
    if ([Environment]::UserInteractive) {
        Write-Host "Where would you like to install Devo CLI?"
        Write-Host "  1) C:\Program Files\Devo (system-wide, requires admin)"
        Write-Host "  2) $env:LOCALAPPDATA\Programs\Devo (user-only, recommended)"
        Write-Host "  3) Current directory (manual PATH setup)"
        Write-Host ""

        $choice = Read-Host "Choose [1-3] (default: 2)"
        if ($choice -eq "") { $choice = "2" }
    } else {
        # Non-interactive mode - use default
        Write-Host "Installing to $env:LOCALAPPDATA\Programs\Devo (non-interactive mode)" -ForegroundColor Blue
        Write-Host "To choose a different location, run the script directly with -InstallDir parameter"
        Write-Host ""
        $choice = "2"
    }
} else {
    $choice = "0"
}

switch ($choice) {
    "0" {
        # Custom directory
        Write-Host ""
        Write-Host "Installing to $InstallDir..." -ForegroundColor Blue

        if (!(Test-Path $InstallDir)) {
            New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        }

        $DestPath = Join-Path $InstallDir "devo.exe"
        Move-Item -Path $TempFile -Destination $DestPath -Force
        Write-Host "Installed to $DestPath" -ForegroundColor Green

        # Add to PATH if not already there
        $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($UserPath -notlike "*$InstallDir*") {
            Write-Host ""
            Write-Host "Adding $InstallDir to PATH..." -ForegroundColor Yellow
            [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
            Write-Host "PATH updated (restart terminal to apply)" -ForegroundColor Green
        }
    }
    "1" {
        # System-wide installation
        Write-Host ""
        Write-Host "Installing to C:\Program Files\Devo..." -ForegroundColor Blue

        # Check for admin rights
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

        if (!$isAdmin) {
            Write-Host "Administrator rights required for system-wide installation" -ForegroundColor Red
            Write-Host "Please run PowerShell as Administrator or choose option 2" -ForegroundColor Yellow
            Remove-Item $TempFile -ErrorAction SilentlyContinue
            exit 1
        }

        $InstallPath = "C:\Program Files\Devo"
        if (!(Test-Path $InstallPath)) {
            New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
        }

        $DestPath = Join-Path $InstallPath "devo.exe"
        Move-Item -Path $TempFile -Destination $DestPath -Force
        Write-Host "Installed to $DestPath" -ForegroundColor Green

        # Add to system PATH
        $SystemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        if ($SystemPath -notlike "*$InstallPath*") {
            Write-Host ""
            Write-Host "Adding $InstallPath to system PATH..." -ForegroundColor Yellow
            [Environment]::SetEnvironmentVariable("Path", "$SystemPath;$InstallPath", "Machine")
            Write-Host "PATH updated (restart terminal to apply)" -ForegroundColor Green
        }
    }
    "2" {
        # User installation (default)
        Write-Host ""
        Write-Host "Installing to $env:LOCALAPPDATA\Programs\Devo..." -ForegroundColor Blue

        $InstallPath = Join-Path $env:LOCALAPPDATA "Programs\Devo"
        if (!(Test-Path $InstallPath)) {
            New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
        }

        $DestPath = Join-Path $InstallPath "devo.exe"
        Move-Item -Path $TempFile -Destination $DestPath -Force
        Write-Host "Installed to $DestPath" -ForegroundColor Green

        # Add to user PATH
        $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($UserPath -notlike "*$InstallPath*") {
            Write-Host ""
            Write-Host "Adding $InstallPath to PATH..." -ForegroundColor Yellow
            [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallPath", "User")
            Write-Host "PATH updated (restart terminal to apply)" -ForegroundColor Green
        }
    }
    "3" {
        # Current directory
        Write-Host ""
        $DestPath = Join-Path (Get-Location) "devo.exe"
        Move-Item -Path $TempFile -Destination $DestPath -Force
        Write-Host "Binary ready in current directory" -ForegroundColor Green
        Write-Host ""
        Write-Host "To use from anywhere, add to PATH or move to a directory in PATH" -ForegroundColor Yellow
    }
    default {
        Write-Host "Invalid choice" -ForegroundColor Red
        Remove-Item $TempFile -ErrorAction SilentlyContinue
        exit 1
    }
}

Write-Host ""
Write-Host "Devo CLI installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart your terminal to apply PATH changes"
Write-Host "  2. Configure AWS credentials: aws configure"
Write-Host "  3. Test the CLI: devo --help"
Write-Host "  4. Generate a commit: devo commit"
Write-Host ""
Write-Host "Documentation: https://github.com/$Repo"
