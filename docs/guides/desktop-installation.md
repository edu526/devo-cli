# Devo Desktop — Installation

Devo Desktop is the Tauri 2.x companion app for the `devo` CLI. It bundles
the CLI as a Python sidecar (FastAPI + WebSocket) and exposes a Svelte
front-end for managing SSM tunnels, AWS profiles, databases and
`/etc/hosts` entries.

## Supported platforms

| OS | Arch | Bundle | Notes |
|---|---|---|---|
| Linux | x86_64 | AppImage | Requires WebKitGTK 4.1, glibc 2.31+ |
| macOS | aarch64 | `.app` + `.dmg` | Apple Silicon |
| macOS | x86_64 | `.app` + `.dmg` | Intel |
| Windows | x86_64 | `.msi` + NSIS `.exe` | WebView2 runtime (preinstalled on Win 11) |

## Install

### Linux (AppImage)

```bash
# Download the latest AppImage from the GitHub release page
chmod +x Devo_*.AppImage
./Devo_*.AppImage
```

The AppImage is self-contained; no system-wide install is required. WebKitGTK
runtime libraries must be present (they are on every mainstream desktop
distro shipped after 2022). On minimal / headless distros:

```bash
sudo apt-get install libwebkit2gtk-4.1-0 libgtk-3-0 libayatana-appindicator3-1
```

### macOS

```bash
# Open the .dmg
open Devo_*.dmg
# Drag Devo.app to /Applications
```

The first launch needs the standard macOS "open anyway" prompt (the binary
isn't code-signed in CI yet — see [Auto Update](desktop-auto-update.md) for
the production signing story).

### Windows

```bash
# Run the MSI installer
msiexec /i Devo_*.msi
# Or the NSIS installer (interactive)
Devo_*.exe
```

On Windows 10 you may need to install the
[WebView2 runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
manually. Windows 11 ships it preinstalled.

## Update

Devo Desktop checks for updates on launch and every 6 hours. When a new
version is available, a banner appears at the top of the window. Click
**Download & Install** to fetch and apply the update — the app restarts
automatically.

See [Auto Update](desktop-auto-update.md) for the manifest format and
signing process.

## First launch

1. The app starts the Python sidecar in the background; this is invisible
   but if it fails the splash screen shows the error.
2. Navigate to **AWS Profiles** and click **Refresh All** to authenticate
   with SSO.
3. Add an **Instance** (your bastion) and a **Database** to set up a
   connection.
4. Open **Connections** and start the tunnels you need — connect to the
   forwarded ports from your local DB client.

## Troubleshooting

- **Sidecar fails to start:** check `~/.devo/sidecar.log` for the Python
  traceback. The sidecar is the CLI's `cli_tool.sidecar` module and shares
  its dependencies.
- **Connection refused on `127.0.0.1:15432`:** the sidecar only forwards
  if `local_address` is `127.0.0.1`. Set `--no-hosts` if you don't need
  hostname forwarding or add a `/etc/hosts` entry via **Hosts**.
- **WebView2 missing (Windows 10):** install it manually from
  [Microsoft's site](https://developer.microsoft.com/microsoft-edge/webview2/).
- **AppImage won't launch on Fedora / RHEL:** SELinux may block it. Either
  disable enforcement on the file or use the Flatpak once it's published.
