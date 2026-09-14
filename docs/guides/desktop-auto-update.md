# Devo Desktop — Auto Update

Devo Desktop uses [`tauri-plugin-updater`](https://v2.tauri.app/plugin/updater/)
to poll a hosted manifest and apply signed updates in place. The manifest
is hosted as a release asset on GitHub.

## How it works

1. CI (`.github/workflows/desktop.yml`) builds a Tauri bundle per platform
   on every push to `main`.
2. The Tauri action generates a `latest.json` manifest (and per-platform
   `.sig` signature files) and attaches everything to a draft GitHub
   release.
3. When Devo Desktop starts, `TitleBar.svelte` calls `fetchUpdate()` (which
   invokes the `fetch_update` Tauri command) once on mount and again every
   `POLL_INTERVAL_MS` (6 hours) via `setInterval`.
4. If a newer version is available, an **↑ update** badge appears next to
   the app version in the title bar. Clicking it triggers `install_update`,
   which streams chunks over a Tauri Channel, installs the new bundle, and
   relaunches the app.

## Manifest format

`latest.json` is the static JSON manifest described in the
[Tauri updater docs](https://v2.tauri.app/plugin/updater/#static-json-file).
Example:

```json
{
  "version": "0.2.0",
  "notes": "Initial multi-OS release",
  "pub_date": "2026-07-01T12:00:00Z",
  "platforms": {
    "linux-x86_64": {
      "signature": "dW50cnVzdGVkIGNvbW1lbnQ6...",
      "url": "https://github.com/edu526/devo-cli/releases/download/app-v0.2.0/Devo_0.2.0_amd64.AppImage"
    },
    "darwin-aarch64": {
      "signature": "...",
      "url": "https://github.com/edu526/devo-cli/releases/download/app-v0.2.0/Devo_0.2.0_aarch64.app.tar.gz"
    },
    "darwin-x86_64": {
      "signature": "...",
      "url": "https://github.com/edu526/devo-cli/releases/download/app-v0.2.0/Devo_0.2.0_x64.app.tar.gz"
    },
    "windows-x86_64": {
      "signature": "...",
      "url": "https://github.com/edu526/devo-cli/releases/download/app-v0.2.0/Devo_0.2.0_x64-setup.exe"
    }
  }
}
```

The Tauri action generates this file automatically — no manual work needed
once the signing keys are in place.

## Signing keys

The updater **requires** a public key to validate signatures. To generate
a fresh keypair locally:

```bash
cd desktop
pnpm tauri signer generate -- -w ~/.tauri/devo.key
```

This creates a public key in `~/.tauri/devo.key.pub` and a private key in
`~/.tauri/devo.key`.

### Configure the public key

Copy the contents of `~/.tauri/devo.key.pub` (the PEM block) into
`desktop/src-tauri/tauri.conf.json` under `plugins.updater.pubkey`:

```json
"updater": {
  "pubkey": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
  "endpoints": ["https://github.com/edu526/devo-cli/releases/latest/download/latest.json"]
}
```

### Configure the private key in CI

Add a GitHub Actions secret `TAURI_SIGNING_PRIVATE_KEY` whose value is the
**content** (not path) of the private key file. Tauri reads this at build
time to sign the update artifacts.

Optional: add a second secret `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` if the
key is passphrase-protected.

> **Never commit the private key.** It cannot be recovered if lost — every
> installed copy of the app would be unable to verify future updates.

## Polling behaviour

- `TitleBar.svelte` polls the manifest on mount and every 6 hours thereafter
  (`POLL_INTERVAL_MS`).
- There is no dismiss/snooze — the badge stays visible until the update is
  installed.
- If `install_update` reports an error, the button's `title` tooltip shows
  the error and re-enables for another attempt.

## Release workflow

To publish a new version:

1. Bump the `version` field in `desktop/src-tauri/tauri.conf.json`
   (or use a release tool that does it automatically).
2. Push to `main` — the workflow creates a **draft** release named
   `app-v<version>` containing all bundles plus the manifest.
3. Review the draft on GitHub, edit release notes, and **publish**.
4. Users get the banner on their next poll (max 6h delay).
