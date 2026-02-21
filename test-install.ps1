# Test script for Windows installer
# This simulates the installation process without actually installing

Write-Host "Testing Devo CLI Installer..." -ForegroundColor Cyan
Write-Host ""

# Test 1: Check PowerShell version
Write-Host "[1/4] Checking PowerShell version..." -ForegroundColor Blue
$PSVersion = $PSVersionTable.PSVersion
Write-Host "PowerShell version: $PSVersion" -ForegroundColor Gray
if ($PSVersion.Major -lt 5) {
    Write-Host "WARNING: PowerShell 5.0 or higher recommended" -ForegroundColor Yellow
} else {
    Write-Host "OK" -ForegroundColor Green
}
Write-Host ""

# Test 2: Check internet connectivity
Write-Host "[2/4] Checking internet connectivity..." -ForegroundColor Blue
try {
    $response = Invoke-WebRequest -Uri "https://github.com" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "OK - Can reach GitHub" -ForegroundColor Green
} catch {
    Write-Host "WARNING: Cannot reach GitHub" -ForegroundColor Yellow
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Gray
}
Write-Host ""

# Test 3: Check if devo is already installed
Write-Host "[3/4] Checking for existing installation..." -ForegroundColor Blue
$devoPath = Get-Command devo -ErrorAction SilentlyContinue
if ($devoPath) {
    Write-Host "Found existing installation: $($devoPath.Source)" -ForegroundColor Yellow
    try {
        $version = & devo --version 2>&1
        Write-Host "Current version: $version" -ForegroundColor Gray
    } catch {
        Write-Host "Could not determine version" -ForegroundColor Gray
    }
} else {
    Write-Host "No existing installation found" -ForegroundColor Gray
}
Write-Host ""

# Test 4: Check write permissions
Write-Host "[4/4] Checking write permissions..." -ForegroundColor Blue
$testLocations = @(
    @{Path = "$env:LOCALAPPDATA\Programs"; Name = "User Programs (recommended)"},
    @{Path = "C:\Program Files"; Name = "System Programs (requires admin)"},
    @{Path = (Get-Location).Path; Name = "Current directory"}
)

foreach ($location in $testLocations) {
    try {
        $testFile = Join-Path $location.Path "devo-test-$([guid]::NewGuid().ToString().Substring(0,8)).tmp"
        New-Item -ItemType File -Path $testFile -Force -ErrorAction Stop | Out-Null
        Remove-Item $testFile -Force -ErrorAction SilentlyContinue
        Write-Host "  $($location.Name): OK" -ForegroundColor Green
    } catch {
        Write-Host "  $($location.Name): NO ACCESS" -ForegroundColor Yellow
    }
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To install Devo CLI, run:" -ForegroundColor White
Write-Host "  irm https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1 | iex" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or download and run locally:" -ForegroundColor White
Write-Host "  Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/edu526/devo-cli/main/install.ps1' -OutFile 'install-devo.ps1'" -ForegroundColor Yellow
Write-Host "  .\install-devo.ps1" -ForegroundColor Yellow
Write-Host ""
