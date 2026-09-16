; Tauri's default installer.nsi already detects a running `devo.exe` and
; offers to close it before installing — but it has no idea the app spawned
; a separate `devo-sidecar.exe` child process, which stays alive and keeps
; the file locked. This hook runs right before file copying starts and kills
; any leftover sidecar so the extract step below doesn't fail with
; "Error opening file for writing".
; `taskkill /IM` does NOT support partial wildcards like "devo-sidecar*.exe"
; — Windows only treats a bare "*" as "match everything" — so this must be
; the exact image name or the kill silently fails to match anything.
!macro NSIS_HOOK_PREINSTALL
  nsExec::Exec 'taskkill /F /IM devo-sidecar.exe /T'
!macroend
