# Devo Desktop — Installation

Devo Desktop is the Tauri 2.x companion app for the `devo` CLI. It bundles
the CLI as a Python sidecar (FastAPI + WebSocket) and exposes a Svelte
front-end for managing SSM tunnels, AWS profiles, databases and
`/etc/hosts` entries.

## Supported platforms

| OS | Arch | Bundle | Notes |
|---|---|---|---|
| Linux | x86_64 | AppImage or `.deb` | Requires WebKitGTK 4.1, glibc 2.31+ (Ubuntu 22.04+ / Debian 12+ for the `.deb`) |
| macOS | aarch64 | `.app` + `.dmg` | Apple Silicon (M1/M2/M3/M4) |
| macOS | x86_64 | `.app` + `.dmg` | Intel |
| Windows | x86_64 | `.msi` + NSIS `.exe` | WebView2 runtime (preinstalled on Win 11) |

Not sure which Mac build you need? **Apple menu → About This Mac** — if it
says "Chip: Apple M1/M2/M3/M4" use `aarch64`; if it says "Intel processor"
use `x86_64`.

## Install

### Linux

Two bundles are published — pick whichever fits your workflow.

**AppImage** (no install, runs from anywhere):

```bash
# Download the latest AppImage from the GitHub release page
chmod +x Devo_*.AppImage
./Devo_*.AppImage
```

WebKitGTK runtime libraries must be present (they are on every mainstream
desktop distro shipped after 2022). On minimal / headless distros:

```bash
sudo apt-get install libwebkit2gtk-4.1-0 libgtk-3-0 libayatana-appindicator3-1
```

**`.deb`** (apt-based distros — Ubuntu 22.04+ / Debian 12+): installs
icons, a `.desktop` entry, and resolves the same runtime deps
automatically.

```bash
sudo apt install ./Devo_*.deb
```

### macOS

```bash
# Open the .dmg
open Devo_*.dmg
# Drag Devo.app to /Applications
```

The app isn't signed with an Apple Developer ID or notarized yet (no
Apple Developer license), so the first launch triggers a Gatekeeper
warning. Depending on the macOS version you'll see either:

- *"Devo can't be opened because the developer cannot be verified"*, or
- *"Devo.app is damaged and can't be opened"* — this happens when the
  browser tags the downloaded file with the quarantine attribute.

To fix it:

```bash
# Clears the quarantine attribute the browser added on download
xattr -cr /Applications/Devo.app
```

Then right-click (or Control-click) `Devo.app` → **Open** → confirm in the
dialog. This is only needed once. If it's still blocked, go to
**System Settings → Privacy & Security**, scroll to the Security section,
and click **Open Anyway** (the button appears after the first blocked
attempt).

See [Auto Update](desktop-auto-update.md) for the production signing story
— once installed, in-app updates verify against a bundled minisign key and
don't require Apple notarization.

### Windows

```bash
# Run the MSI installer
msiexec /i Devo_*.msi
# Or the NSIS installer (interactive)
Devo_*.exe
```

The installer isn't code-signed either, so SmartScreen will show
**"Windows protected your PC"**. Click **More info → Run anyway** to
proceed.

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

- **"Devo.app is damaged" (macOS):** quarantine attribute from the
  browser download. Run `xattr -cr /Applications/Devo.app`.
- **"Unidentified developer" (macOS):** no Apple notarization yet.
  Right-click → **Open** instead of double-clicking.
- **SmartScreen blocks the installer (Windows):** no code-signing
  certificate yet. Click **More info → Run anyway**.
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
- **Desktop shortcut opens the CLI instead of the app, or does nothing
  (Linux, `.deb` installs):** older builds shipped a desktop binary also
  named `devo`, which could collide with the CLI's `devo` command
  depending on `$PATH` order. Fixed in newer releases — the desktop
  binary is now `devo-desktop`, so it never shadows (or gets shadowed by)
  the CLI. Update to the latest release and, if you previously edited the
  `.desktop` file's `Exec=` line to a hardcoded path as a workaround, you
  can revert it to `Exec=devo-desktop %U`.
