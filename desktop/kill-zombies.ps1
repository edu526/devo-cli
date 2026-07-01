# Kill any running devo or devo-sidecar processes
Stop-Process -Name 'devo', 'devo-sidecar*' -Force -ErrorAction SilentlyContinue

# Kill python processes running the sidecar module
try {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*cli_tool.sidecar*' } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
} catch {
    Get-WmiObject Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*cli_tool.sidecar*' } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

exit 0
