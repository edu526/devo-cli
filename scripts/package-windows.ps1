# Package Windows binary folder into ZIP for distribution
# Run after building with PyInstaller

param(
    [string]$Version = "dev"
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

# Create release folder if it doesn't exist
if (!(Test-Path "release")) {
    New-Item -ItemType Directory -Path "release" | Out-Null
}

# Determine output filename
$ZipName = "devo-windows-amd64.zip"
$ZipPath = "release\$ZipName"

Write-Host "Creating ZIP archive..." -ForegroundColor Blue
Write-Host "  Source: dist\devo\" -ForegroundColor Gray
Write-Host "  Output: $ZipPath" -ForegroundColor Gray
Write-Host ""

# Remove existing ZIP if present
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

# Create ZIP archive
try {
    Compress-Archive -Path "dist\devo\*" -DestinationPath $ZipPath -CompressionLevel Optimal

    $ZipSize = (Get-Item $ZipPath).Length / 1MB
    Write-Host "Package created successfully!" -ForegroundColor Green
    Write-Host "  Size: $([math]::Round($ZipSize, 2)) MB" -ForegroundColor Gray
    Write-Host "  Location: $ZipPath" -ForegroundColor Gray
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
