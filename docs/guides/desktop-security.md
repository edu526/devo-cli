# Devo Desktop — Security

Devo Desktop treats the local sidecar (a FastAPI server bound to
`127.0.0.1`) as a privileged control plane: it spawns SSM sessions,
edits `/etc/hosts`, and writes AWS credentials. The webview has no
direct access to these capabilities — every operation must go through
the sidecar, and the sidecar enforces several layers of defence.

## Threat model

| Adversary | Capability | Mitigation |
|---|---|---|
| Local malware on the same machine | Try to read AWS creds or start tunnels by hitting the sidecar | Bearer token in memory only; CORS allowlist; rate limit |
| Network attacker | Reach the sidecar from the network | Binds to `127.0.0.1` only (no `--host 0.0.0.0` exposed in the UI) |
| Compromised dev tool / browser | Try to read audit log or rotate tokens | Bearer required for all sensitive endpoints; tokens auto-rotate |
| Bug in a CLI command | Send a huge body that exhausts memory | Body size limit (1 MB) at the middleware layer |
| User leaves machine unlocked | Theif kicks off a flood of operations | Per-endpoint rate limit + 429 with `Retry-After` |

## Layered defences

### 1. CORS allowlist

Only two origins can reach the sidecar:

- `tauri://localhost` — the production webview
- `http://localhost:5173` — the Vite dev server (development only)

For staging or E2E setups, set `DEVO_SIDECAR_ALLOWED_ORIGINS` to a
comma-separated list of additional origins. Bare `http://localhost`
and `http://127.0.0.1` are intentionally excluded because any local
process can claim them.

### 2. Bearer token

A 32-byte URL-safe token is generated when the sidecar starts. The token
is:

- Printed on stdout in the `DEVO_SIDECAR_READY` handshake (the Tauri
  shell reads it, never persists it)
- Held in memory by the frontend only — it is **never** written to disk
- Validated on every request via the `Authorization: Bearer <token>`
  header

Tokens expire after **8 hours** (`DEFAULT_TOKEN_TTL_SECONDS`). The
frontend transparently rotates them via `POST /api/v1/auth/refresh`,
which:

1. Accepts the current (or recently-expired) token
2. Issues a fresh token
3. Invalidates the old one immediately (the old token returns 401 on
   the next request)

If a token is older than **2 × TTL** (16 hours), `/auth/refresh`
rejects it with 401. The user must restart the app to get a fresh
sidecar with a new bootstrap token.

### 3. Rate limits

| Endpoint | Limit |
|---|---|
| `POST /profiles:refresh_all` | 1 / minute |
| `POST /connections:start_all` | 1 / minute |
| `POST /connections/{name}` | 10 / minute |
| `DELETE /logs` | 5 / hour |

Exceeding a limit returns `429 Too Many Requests` with a `Retry-After`
header and `X-RateLimit-*` telemetry. The limits are per-client-IP; the
sidecar only binds to localhost so in practice only the Tauri webview
and the Vite dev server compete for the budget.

### 4. Body size limit

The middleware layer rejects any request with `Content-Length > 1 MB`
with `413 Payload Too Large`. The largest legitimate payload (a full
config patch) is under 64 KB.

### 5. Audit log

Every request is recorded in `~/.devo/audit-YYYY-MM-DD.log` as one
JSONL line:

```json
{"ts":"2026-06-12T10:00:00.123Z","method":"POST","path":"/api/v1/connections/db1","status":202,"ip":"127.0.0.1","token":"a1b2c3d4e5f60718","duration_ms":12.34}
```

- `token` is a SHA-256 prefix (16 hex chars) of the bearer — never the
  raw value.
- `duration_ms` is wall-clock time spent in handlers, useful for
  spotting slow endpoints.
- Logs rotate daily and files older than 30 days are pruned on each
  new-day open.

To inspect recent activity:

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:$PORT/api/v1/audit?limit=50
```

The endpoint requires the same bearer as every other protected
endpoint.

### 6. Tauri capability minimization

`desktop/src-tauri/capabilities/default.json` only exposes the
permissions the webview actually needs:

- `core:default` plus window controls (minimize / maximize / close)
- `core:event:allow-listen` / `allow-unlisten` for WS subscriptions
- `shell:allow-spawn` — required to launch the sidecar binary
- `updater:default` — required by `tauri-plugin-updater`

`shell:allow-execute` and `shell:allow-kill` are intentionally
**not** granted. The webview cannot execute arbitrary programs or kill
processes via the Tauri shell plugin. Process management happens
server-side in the sidecar.

## Reporting a vulnerability

Email `edu526@proton.me` with a description and reproduction steps.
Please do not file a public issue for suspected vulnerabilities.
