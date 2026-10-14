# Kill the dev processes a previous `pnpm tauri dev` may have left behind.
#
# Only this checkout's: an installed Devo (devo-desktop.exe and its own
# devo-sidecar.exe) can be running at the same time and must survive. Killing
# by name used to take its sidecar down with the dev one.

$devTarget = Join-Path $PSScriptRoot 'src-tauri\target'
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)

# The dev app and the dev sidecar wrapper, with their children (python)
$procs | Where-Object { $_.Name -eq 'devo.exe' -or $_.Name -like 'devo-sidecar*' } | ForEach-Object {
    $path = "$($_.ExecutablePath)" -replace '^\\\\\?\\', ''
    if ($path -and $path.StartsWith($devTarget, [StringComparison]::OrdinalIgnoreCase)) {
        taskkill /F /T /PID $_.ProcessId 2>&1 | Out-Null
    }
}

# Python sidecars (`-m cli_tool.sidecar`) only exist in dev: an installed
# sidecar is the frozen devo-sidecar.exe.
$procs | Where-Object { $_.CommandLine -like '*-m cli_tool.sidecar*' } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

exit 0
