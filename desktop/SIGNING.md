# Devo Desktop — Code Signing

Devo Desktop signs its bundles and update artifacts with a minisign
keypair. The `tauri-plugin-updater` runtime verifies the signature
against the public key embedded in `tauri.conf.json` before applying
any update.

## TL;DR

```bash
# 1. Generate the keypair (once, on a secure machine)
pnpm tauri signer generate -w ~/.tauri/devo.key -f

# 2. Fix the comment label (see "The label bug" below) and rewrap
base64 -d ~/.tauri/devo.key \
  | sed 's/rsign encrypted/minisign encrypted/' \
  | base64 -w 0 \
  | pbcopy   # → paste into GitHub secret TAURI_SIGNING_PRIVATE_KEY

# 3. Embed the public key in the app
#    Copy the full content of ~/.tauri/devo.key.pub into
#    desktop/src-tauri/tauri.conf.json → plugins.updater.pubkey

# 4. Verify locally
TAURI_SIGNING_PRIVATE_KEY="$(base64 -d ~/.tauri/devo.key \
  | sed 's/rsign encrypted/minisign encrypted/' \
  | base64 -w 0)" \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD='your-password' \
  pnpm --dir desktop tauri build --bundles appimage
```

A successful run ends with `Finished 1 updater signature at:
…/Devo_…_amd64.AppImage.sig`.

---

## The label bug

`tauri signer generate` (Tauri CLI 2.x) writes the priv key file with
the header:

```
untrusted comment: rsign encrypted secret key
```

But `tauri signer sign` reads it with the `minisign` Rust crate, which
only accepts:

```
untrusted comment: minisign encrypted secret key
```

The pubkey is unaffected — it is written with the `minisign public key`
label from the start. Result: signing works on the CLI's own check but
fails at parse time in CI with errors like:

```
failed to decode base64 secret key: failed to decode base64 key:
  Invalid symbol 61, offset 346.
```

or (when the env var is passed without re-encoding):

```
incorrect updater private key password: Missing encoded key in secret key
```

or (when the file is read as a path):

```
failed to decode base64 secret key: failed to decode base64 key:
  Invalid symbol 32, offset 9.
```

The fix is to relabel the comment line in the priv key before storing
it. The inner key bytes (the actual 158-byte minisign secret-key
blob) are unchanged and remain compatible with the standard minisign
crate that tauri uses to verify updates.

---

## Generating the keypair

Use the Tauri CLI to generate a password-protected keypair:

```bash
# macOS / Linux
pnpm tauri signer generate -w ~/.tauri/devo.key -f -p 'your-password'

# Windows (PowerShell)
pnpm tauri signer generate -w "$HOME/.tauri/devo.key" -f -p 'your-password'
```

The `-f` flag overwrites any existing key. The `-p` flag sets the
password non-interactively (use a strong one — the password is the
only thing protecting the key on disk and in CI).

This produces two files:

| File | Purpose |
|---|---|
| `~/.tauri/devo.key` | **Private key** — never commit, never log |
| `~/.tauri/devo.key.pub` | **Public key** — embedded in `tauri.conf.json` |

---

## Storing in GitHub

The CI workflow (`.github/workflows/desktop.yml`) signs bundles via
`tauri-apps/tauri-action`, which reads the key from
`TAURI_SIGNING_PRIVATE_KEY` and the password from
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD`.

### `TAURI_SIGNING_PRIVATE_KEY`

The env var is a base64 string that decodes to the priv key file
content (the multi-line `untrusted comment: …` form). Store the
**relabeled** content:

```bash
base64 -d ~/.tauri/devo.key \
  | sed 's/rsign encrypted/minisign encrypted/' \
  | base64 -w 0 \
  | pbcopy   # or xclip on Linux
```

Paste the clipboard into the GitHub repo under
**Settings → Secrets and variables → Actions →
`TAURI_SIGNING_PRIVATE_KEY` → Update**.

### `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`

Set to the same password used with `-p` above. Use the same quoting
rules as in CI (the value is a string, no shell expansion).

### `tauri.conf.json`

The pubkey goes in the `plugins.updater.pubkey` field. The full
content of the `.key.pub` file (the base64-wrapped form, with the
`untrusted comment: minisign public key …` header) is what Tauri
expects:

```json
{
  "plugins": {
    "updater": {
      "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDg2ODFCOTM3Njg1QzBFNEYKUldSUERseG9ON21CaHNIQkx1YTdsNDhMUTAyUnJWYlBST2FoWmFFZENva1NGT2l3eW9qVzBPLzgK",
      "endpoints": [
        "https://github.com/edu526/devo-cli/releases/download/app-alpha/latest.json"
      ]
    }
  }
}
```

---

## Local build verification

Before pushing, reproduce the CI signing locally to catch key/secret
mismatches early:

```bash
# from the repo root
cd desktop
pnpm install --frozen-lockfile
pnpm build

KEY_B64="$(base64 -d ~/.tauri/devo.key \
  | sed 's/rsign encrypted/minisign encrypted/' \
  | base64 -w 0)"

TAURI_SIGNING_PRIVATE_KEY="$KEY_B64" \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD='your-password' \
  pnpm tauri build --bundles appimage
```

Expected final lines:

```
Finished 1 bundle at:
  …/Devo_<version>_amd64.AppImage
Finished 1 updater signature at:
  …/Devo_<version>_amd64.AppImage.sig
```

No errors from `tauri signer sign`. The `.sig` file is the per-bundle
signature that ships alongside the bundle in the GitHub release.

On macOS, swap `--bundles appimage` for `--bundles app,dmg` and run on
a `macos-14` runner (or use the same env vars on a Mac). On Windows,
the env var is read the same way; PowerShell just needs the values
set in the step's `env:` block.

---

## Rotating the keypair

Rotating is a destructive operation — every installed copy of the
app will need to be re-signed with the new key, and any in-flight
updates will fail verification. Plan a version bump alongside.

1. Generate the new keypair (see above).
2. Update `tauri.conf.json` with the new pubkey.
3. Update `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
   in the GitHub repo.
4. Bump the version in `tauri.conf.json` (so the updater treats it as
   a release that requires the new key).
5. Push — the workflow produces a release with the new signature.
6. Announce the rotation in the release notes so users know to
   upgrade manually if auto-update fails.

The old key should be kept offline (in a password manager or printed
in a safe) for at least one release cycle, in case a rollback is
needed.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Invalid symbol 61, offset 346` | Secret is the wrapped `.key` file content with `=` padding the decoder rejects | Re-encode through `base64 -d … \| sed … \| base64 -w 0` (the relabel command above) |
| `Invalid symbol 32, offset 9` | Secret is the raw key file (multi-line UTF-8) | Same: re-encode through the relabel pipeline |
| `Missing encoded key in secret key` | Secret is URL-safe base64 (no `=`) of a key without the comment header | Use the relabel command to produce a standard base64 of the relabeled file |
| `Invalid utf-8 sequence` | Secret is base64 of the raw 158-byte key blob (binary, not UTF-8) | Same: re-encode the file, not the inner blob |
| `Wrong password for that key` | Password doesn't match the one used at `generate` time | Regenerate with a known password and update `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` |
| `Key is not encrypted` | Key was generated without a password | Regenerate with `-p` to produce an encrypted key |
| macOS CI: `failed to bundle` | Code signing identity not configured | For now, leave unsigned (alpha). Production builds need an Apple Developer ID + notarization credentials. |
