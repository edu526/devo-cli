# Devo CLI Installer for Windows
# Downloads and installs the latest Devo CLI binary from GitHub Releases

param(
    [string]$Version = "latest",
    [string]$InstallDir = ""
)

# Function to pause and wait for user input on error
function Pause-OnError {
    param([string]$Message)
    if ($Message) {
        Write-Host ""
        Write-Host $Message -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# Function to pause and wait for user input on success
function Pause-OnSuccess {
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Green
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Wrap entire script in try-catch for unexpected errors
try {
    # Don't stop on errors - we'll handle them manually
    $ErrorActionPreference = "Continue"

    # Configuration
    $Repo = "edu526/devo-cli"
    $BinaryName = "devo-windows-amd64.zip"  # Changed to ZIP

    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "    Devo CLI Installer for Windows" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
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
    Write-Host "Downloading Devo CLI from GitHub..." -ForegroundColor Blue
    Write-Host "URL: $DownloadUrl" -ForegroundColor Gray
    Write-Host ""
    $TempZip = Join-Path $env:TEMP "devo-cli.zip"
    $TempExtract = Join-Path $env:TEMP "devo-cli-extract"

    try {
        # Show progress
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $TempZip -UseBasicParsing -ErrorAction Stop
        $ProgressPreference = 'Continue'

        # Verify file was downloaded
        if (!(Test-Path $TempZip)) {
            Pause-OnError "ERROR: Download completed but file not found at $TempZip"
        }

        $FileSize = (Get-Item $TempZip).Length / 1MB

        # Check if file is suspiciously small
        if ($FileSize -lt 5) {
            Write-Host ""
            Write-Host "ERROR: Downloaded file is too small ($([math]::Round($FileSize, 2)) MB)" -ForegroundColor Red
            Write-Host ""
            Write-Host "This usually means the binary doesn't exist in the release." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Possible solutions:" -ForegroundColor Yellow
            Write-Host "  1. Check available releases at:" -ForegroundColor Cyan
            Write-Host "     https://github.com/$Repo/releases" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  2. The project may not have Windows binaries yet" -ForegroundColor Yellow
            Write-Host "     You can install from source instead:" -ForegroundColor Cyan
            Write-Host "     - Install Python 3.12+" -ForegroundColor Gray
            Write-Host "     - Clone the repository" -ForegroundColor Gray
            Write-Host "     - Run: pip install -e ." -ForegroundColor Gray
            Write-Host ""
            Write-Host "  3. Try a specific version that has binaries:" -ForegroundColor Yellow
            Write-Host "     .\install-devo.ps1 -Version v1.1.0" -ForegroundColor Gray
            Remove-Item $TempZip -ErrorAction SilentlyContinue
            Pause-OnError ""
        }

        Write-Host "Download complete! ($([math]::Round($FileSize, 2)) MB)" -ForegroundColor Green

        # Extract ZIP
        Write-Host ""
        Write-Host "Extracting files..." -ForegroundColor Blue

        # Clean up old extraction folder
        if (Test-Path $TempExtract) {
            Remove-Item $TempExtract -Recurse -Force
        }

        Expand-Archive -Path $TempZip -DestinationPath $TempExtract -Force

        # Verify extraction - search for devo.exe at root or in a subdirectory
        $TempExeRoot = Join-Path $TempExtract "devo.exe"
        if (Test-Path $TempExeRoot) {
            $TempExe = $TempExeRoot
        } else {
            $foundExe = Get-ChildItem -Path $TempExtract -Filter "devo.exe" -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($null -ne $foundExe) {
                $TempExe = $foundExe.FullName
            } else {
                Write-Host ""
                Write-Host "ERROR: Extraction failed - devo.exe not found" -ForegroundColor Red
                Remove-Item $TempZip -ErrorAction SilentlyContinue
                Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue
                Pause-OnError ""
            }
        }

        Write-Host "Extraction complete!" -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "ERROR: Download failed!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Details: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Please check:" -ForegroundColor Yellow
        Write-Host "  1. You have internet connection"
        Write-Host "  2. The URL is accessible: $DownloadUrl"
        Write-Host "  3. The version '$Version' exists in GitHub Releases"
        Write-Host "  4. GitHub is not blocked by your firewall/proxy"
        Pause-OnError ""
    }

    # Test the binary
    Write-Host ""
    Write-Host "Testing binary..." -ForegroundColor Blue
    try {
        # Capture both stdout and stderr
        $output = & $TempExe --version 2>&1 | Out-String
        $exitCode = $LASTEXITCODE

        if ($exitCode -ne 0) {
            Write-Host ""
            Write-Host "ERROR: Binary test failed with exit code $exitCode" -ForegroundColor Red
            Write-Host ""
            Write-Host "Binary output:" -ForegroundColor Yellow
            Write-Host $output -ForegroundColor Gray
            Write-Host ""
            Write-Host "Common causes:" -ForegroundColor Yellow
            Write-Host "  1. Missing Visual C++ Redistributable (download from Microsoft)" -ForegroundColor Gray
            Write-Host "  2. Antivirus blocking execution (check Windows Defender)" -ForegroundColor Gray
            Write-Host "  3. Binary built for wrong architecture" -ForegroundColor Gray
            Write-Host "  4. Corrupted download (try downloading again)" -ForegroundColor Gray
            Write-Host ""
            Write-Host "Try running the binary directly to see the error:" -ForegroundColor Cyan
            Write-Host "  $TempExe --version" -ForegroundColor Gray
            Write-Host ""
            Write-Host "Or check Windows Event Viewer for application errors" -ForegroundColor Cyan
            Write-Host ""

            # Ask if user wants to continue anyway
            $continue = Read-Host "Do you want to install anyway? (y/N)"
            if ($continue -ne "y" -and $continue -ne "Y") {
                Remove-Item $TempZip -ErrorAction SilentlyContinue
                Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue
                Pause-OnError "Installation cancelled"
            }
            Write-Host ""
            Write-Host "Continuing with installation (binary may not work)..." -ForegroundColor Yellow
        } else {
            Write-Host $output -ForegroundColor Gray
            Write-Host "Binary verified successfully!" -ForegroundColor Green
        }
    } catch {
        Write-Host ""
        Write-Host "ERROR: Binary test failed!" -ForegroundColor Red
        Write-Host "Details: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Common causes:" -ForegroundColor Yellow
        Write-Host "  1. Missing Visual C++ Redistributable (download from Microsoft)" -ForegroundColor Gray
        Write-Host "  2. Antivirus blocking execution (check Windows Defender)" -ForegroundColor Gray
        Write-Host "  3. Binary built for wrong architecture" -ForegroundColor Gray
        Write-Host ""

        # Ask if user wants to continue anyway
        $continue = Read-Host "Do you want to install anyway? (y/N)"
        if ($continue -ne "y" -and $continue -ne "Y") {
            Remove-Item $TempZip -ErrorAction SilentlyContinue
            Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue
            Pause-OnError "Installation cancelled"
        }
        Write-Host ""
        Write-Host "Continuing with installation (binary may not work)..." -ForegroundColor Yellow
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

            # Copy entire folder
            Copy-Item -Path "$TempExtract\*" -Destination $InstallDir -Recurse -Force
            $DestPath = Join-Path $InstallDir "devo.exe"
            Write-Host "Installed to $InstallDir" -ForegroundColor Green

            # Clean up temp files
            Remove-Item $TempZip -ErrorAction SilentlyContinue
            Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue

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
                Write-Host ""
                Write-Host "ERROR: Administrator rights required!" -ForegroundColor Red
                Write-Host ""
                Write-Host "To install system-wide, please:" -ForegroundColor Yellow
                Write-Host "  1. Right-click PowerShell and select 'Run as Administrator'"
                Write-Host "  2. Run the installer again"
                Write-Host ""
                Write-Host "Or choose option 2 for user-only installation (no admin needed)" -ForegroundColor Yellow
                Remove-Item $TempZip -ErrorAction SilentlyContinue
                Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue
                Pause-OnError ""
            }

            $InstallPath = "C:\Program Files\Devo"
            if (!(Test-Path $InstallPath)) {
                New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
            }

            # Copy entire folder
            Copy-Item -Path "$TempExtract\*" -Destination $InstallPath -Recurse -Force
            $DestPath = Join-Path $InstallPath "devo.exe"
            Write-Host "Installed to $InstallPath" -ForegroundColor Green

            # Clean up temp files
            Remove-Item $TempZip -ErrorAction SilentlyContinue
            Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue

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

            # Copy entire folder
            Copy-Item -Path "$TempExtract\*" -Destination $InstallPath -Recurse -Force
            $DestPath = Join-Path $InstallPath "devo.exe"
            Write-Host "Installed to $InstallPath" -ForegroundColor Green

            # Clean up temp files
            Remove-Item $TempZip -ErrorAction SilentlyContinue
            Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue

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
            $CurrentDir = Get-Location
            Copy-Item -Path "$TempExtract\*" -Destination $CurrentDir -Recurse -Force
            $DestPath = Join-Path $CurrentDir "devo.exe"
            Write-Host "Binary ready in current directory" -ForegroundColor Green

            # Clean up temp files
            Remove-Item $TempZip -ErrorAction SilentlyContinue
            Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue

            Write-Host ""
            Write-Host "To use from anywhere, add to PATH or move to a directory in PATH" -ForegroundColor Yellow
        }
        default {
            Write-Host ""
            Write-Host "ERROR: Invalid choice '$choice'" -ForegroundColor Red
            Write-Host "Please choose 1, 2, or 3" -ForegroundColor Yellow
            Remove-Item $TempZip -ErrorAction SilentlyContinue
            Remove-Item $TempExtract -Recurse -Force -ErrorAction SilentlyContinue
            Pause-OnError ""
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Devo CLI installed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Restart your terminal to apply PATH changes"
    Write-Host "  2. Configure AWS credentials: aws configure"
    Write-Host "  3. Test the CLI: devo --help"
    Write-Host "  4. Generate a commit: devo commit"
    Write-Host ""
    Write-Host "Documentation: https://github.com/$Repo" -ForegroundColor Gray

    # Pause before exiting so user can read the output
    Pause-OnSuccess

} catch {
    # Catch any unexpected errors
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  UNEXPECTED ERROR OCCURRED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error details:" -ForegroundColor Yellow
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Stack trace:" -ForegroundColor Gray
    Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    Write-Host ""
    Write-Host "Please report this error at:" -ForegroundColor Cyan
    Write-Host "https://github.com/$Repo/issues" -ForegroundColor Cyan
    Pause-OnError ""
}
