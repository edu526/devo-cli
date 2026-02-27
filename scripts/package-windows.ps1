# Package Windows binary folder into ZIP for distribution
# Run after building with PyInstaller

param(
    [string]$Version = $env:RELEASE_VERSION
)

Write-Host "Packaging Devo CLI for Windows distribution..." -ForegroundColor Cyan
Write-Host ""

# Check if dist/devo folder exists
if (!(Test-Path "dist\devo")) {
    Write-Host "ERROR: dist\devo folder not found" -ForegroundColor Red
    Write-Host "Run 'scripts\build-windows.bat' first" -ForegroundColor Yellow
    exit 1
}

# Check if devo.exe exists
if (!(Test-Path "dist\devo\devo.exe")) {
    Write-Host "ERROR: dist\devo\devo.exe not found" -ForegroundColor Red
    exit 1
}

# Determine version and output paths
if ([string]::IsNullOrEmpty($Version)) {
    # No version specified, use simple release folder
    $ReleaseDir = "release"
    $ZipName = "devo-windows-amd64.zip"
} else {
    # Version specified, create versioned release
    $ReleaseDir = "release\$Version"
    $ZipName = "devo-windows-amd64.zip"
}

# Create release folder if it doesn't exist
if (!(Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
}

$ZipPath = "$ReleaseDir\$ZipName"

Write-Host "Creating ZIP archive..." -ForegroundColor Blue
Write-Host "  Source: dist\devo\" -ForegroundColor Gray
Write-Host "  Output: $ZipPath" -ForegroundColor Gray
if (![string]::IsNullOrEmpty($Version)) {
    Write-Host "  Version: $Version" -ForegroundColor Gray
}
Write-Host ""

# Remove existing ZIP if present
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

# Create ZIP archive with nested structure (devo-windows-amd64 folder inside ZIP)
try {
    # Create temporary directory with proper name
    $TempDir = "dist\devo-windows-amd64"
    if (Test-Path $TempDir) {
        Remove-Item $TempDir -Recurse -Force
    }
    
    # Copy devo folder to temp with proper name
    Copy-Item -Path "dist\devo" -Destination $TempDir -Recurse
    
    # Create ZIP from temp directory
    Push-Location "dist"
    Compress-Archive -Path "devo-windows-amd64" -DestinationPath "..\$ZipPath" -CompressionLevel Optimal
    Pop-Location
    
    # Clean up temp directory
    Remove-Item $TempDir -Recurse -Force

    $ZipSize = (Get-Item $ZipPath).Length / 1MB
    Write-Host "Package created successfully!" -ForegroundColor Green
    Write-Host "  Size: $([math]::Round($ZipSize, 2)) MB" -ForegroundColor Gray
    Write-Host "  Location: $ZipPath" -ForegroundColor Gray
    Write-Host ""

    # Generate checksum
    $ChecksumPath = "$ReleaseDir\SHA256SUMS"
    $Hash = (Get-FileHash -Path $ZipPath -Algorithm SHA256).Hash.ToLower()
    $ChecksumLine = "$Hash  $ZipName"
    
    if (Test-Path $ChecksumPath) {
        Add-Content -Path $ChecksumPath -Value $ChecksumLine
    } else {
        Set-Content -Path $ChecksumPath -Value $ChecksumLine
    }
    
    Write-Host "Checksum generated: SHA256SUMS" -ForegroundColor Green
    Write-Host ""

    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Test the package: Expand-Archive $ZipPath -DestinationPath test\" -ForegroundColor Gray
    Write-Host "  2. Upload to GitHub Release as: $ZipName" -ForegroundColor Gray
    Write-Host ""

} catch {
    Write-Host "ERROR: Failed to create ZIP" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    exit 1
}
