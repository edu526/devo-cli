Add-Type -AssemblyName System.Drawing
$sourcePath = $args[0]
$destPath = $args[1]
try {
    $img = [System.Drawing.Image]::FromFile($sourcePath)
    $img.Save($destPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "Success"
} catch {
    Write-Host "Error: $_"
}
