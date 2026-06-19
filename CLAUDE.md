# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See [AGENTS.md](./AGENTS.md) for full project instructions and guidelines.

> **Active plan:** [`.agents/plans/desktop-roadmap.md`](.agents/plans/desktop-roadmap.md) — multi-phase roadmap for the desktop app. All work happens on branch `feature/desktop` until ready to merge to `main`. Read the plan first when resuming work to find the current `in_progress` or first `pending` phase.

---

## Desktop app (`desktop/`)

A Tauri 2.x + Svelte 5 + Vite desktop application that wraps the CLI via a FastAPI sidecar.

### Status

| Phase | Description | State |
|---|---|---|
| A | Python sidecar (FastAPI, 7 routers, WebSocket, EventHub) | ✅ done — 81 tests |
| B | Tauri shell (spawn + READY handshake, managed state, invoke) | ✅ done |
| C | Frontend pages (Connections, Instances, Databases, Profiles, Hosts, Config) | ✅ done |
| D | Bundling + CI (devo-sidecar.spec, desktop.yml → AppImage) | ✅ done |
| E | Auto-update | ⬜ pending |

### Stack

| Layer | Tech |
|---|---|
| UI | Svelte 5 (`writable` stores), Vite 6, TypeScript |
| Shell | Tauri 2.x (Rust), `tauri-plugin-shell` |
| Sidecar | FastAPI + uvicorn (`cli_tool/sidecar/`) |
| Package manager | **pnpm** (never use npm in `desktop/`) |

### Commands

```bash
# Install sidecar Python deps (first time only)
venv/bin/pip install -e ".[sidecar]"

# Dev — hot-reload, spawns sidecar automatically
cd desktop && pnpm tauri dev

# Frontend only (browser at localhost:5173, no Tauri invoke)
cd desktop && pnpm dev

# Build desktop app (AppImage on Linux)
cd desktop && pnpm tauri build
```

### Sidecar architecture

```
Tauri (Rust) — find_repo_root() walks up from binary to find venv/
  └─ debug:   venv/bin/python -m cli_tool.sidecar --port 0
  └─ release: binaries/devo-sidecar-<triple>  --port 0
       │
       └─ stdout: DEVO_SIDECAR_READY port=N token=X
       └─ FastAPI on 127.0.0.1:<N>  (Bearer <token>, CORS allowed)
            ├─ /api/v1/connections  – SSM tunnel lifecycle
            ├─ /api/v1/instances    – EC2 bastion CRUD
            ├─ /api/v1/databases    – DB tunnel config CRUD
            ├─ /api/v1/profiles     – AWS SSO profile info
            ├─ /api/v1/hosts        – /etc/hosts management
            ├─ /api/v1/config       – ~/.devo/config.json
            └─ /api/v1/events       – WebSocket (real-time, auth via Sec-WebSocket-Protocol)
```

### Key files

| File | Purpose |
|---|---|
| `cli_tool/sidecar/app.py` | FastAPI factory — includes CORS middleware for Tauri webview |
| `cli_tool/sidecar/routers/ws.py` | WS handler — reads app_state via `websocket.app.state`, accepts before closing |
| `desktop/src/lib/api.ts` | Typed HTTP client for all endpoints + TypeScript types |
| `desktop/src/lib/ws.ts` | WebSocket singleton with auto-reconnect (3 s) |
| `desktop/src/lib/stores.ts` | `writable` stores — **not** runes (runes only work in `.svelte`/`.svelte.ts`) |
| `desktop/src-tauri/src/sidecar.rs` | `find_repo_root()` + spawn + READY handshake (30 s timeout) |
| `desktop/src-tauri/src/lib.rs` | App setup, `SidecarState`, `get_sidecar_info` invoke handler |
| `devo-sidecar.spec` | PyInstaller spec for the sidecar binary |
| `.github/workflows/desktop.yml` | CI: PyInstaller → copy to `binaries/` → `tauri build` → AppImage |

### Known gotchas

- **Svelte stores in `.ts` files**: use `writable` from `svelte/store`. `$state` runes only work inside `.svelte` or `.svelte.ts` files.
- **CORS**: sidecar has `CORSMiddleware` allowing `tauri://localhost` and `http://localhost:5173`. Security is the Bearer token, not origin.
- **WS auth**: `websocket.close(code=4401)` must come *after* `websocket.accept()` — close codes are only valid post-handshake. App state accessed via `websocket.app.state.app_state`, not via `Request` injection.
- **Sidecar repo root detection**: `find_repo_root()` in `sidecar.rs` walks up from the binary path looking for `venv/bin/python` — do NOT use `current_dir()` which is unreliable under `tauri dev`.
- **Sidecar extras**: `fastapi`, `uvicorn`, `watchdog`, `websockets` are in the optional `[sidecar]` extras — install with `venv/bin/pip install -e ".[sidecar]"` before running dev.

### Sidecar binary for release

CI (`.github/workflows/desktop.yml`) builds the sidecar via:
```bash
pyinstaller devo-sidecar.spec --distpath dist-sidecar
cp dist-sidecar/devo-sidecar desktop/src-tauri/binaries/devo-sidecar-x86_64-unknown-linux-gnu
```

The file `desktop/src-tauri/binaries/devo-sidecar-x86_64-unknown-linux-gnu` is a shell
script placeholder (tracked in git) used so `cargo check` passes locally. CI overwrites
it with the real PyInstaller binary before `tauri build`.

### Bundle ID / metadata

- **Bundle ID:** `dev.heyedu.devo`
- **Display name:** Devo
- **Author:** HeyEdu.dev
- **First target:** Linux AppImage
