# Devo Desktop — Roadmap

> **Regla:** todo el trabajo parte de la rama `feature/desktop` hasta que esté listo para mergear a `main`. No se abren branches secundarios por fase.

## Estado actual

- **Rama activa:** `feature/desktop`
- **Último commit:** `703c7b5 test(sidecar,desktop): raise coverage to 90%+ and add contract tests`
- **Working tree:** limpio
- **Tests:** 61 frontend (Vitest) + 1882 backend (pytest) passing
- **Lint:** flake8 / ESLint / svelte-check 0 errors

## Cómo continuar entre sesiones

1. `cd ~/Escritorio/PERSONALES/devo-cli && git checkout feature/desktop`
2. Leer este archivo desde el inicio
3. Buscar la fase con estado `pending` o `in_progress`
4. Marcar items como `[x]` al completarlos
5. Hacer commit siguiendo conventional commits (pre-commit hooks validan formato)

---

## Fase 0 — Foundation ✅ COMPLETADA

Commit: `1806ca4`

- [x] F0.1 — `tsconfig.json` strict + `eslint.config.js` (flat) + `.prettierrc`
- [x] F0.2 — `scripts/build_sidecar_placeholder.sh` (genera wrapper según triple)
- [x] F0.3 — `vitest.config.ts` + 29 tests en `src/lib/__tests__/` (api, ws, stores)
- [x] F0.4 — Pre-commit hooks: `desktop-lint` y `desktop-typecheck` en commit, `desktop-test` en push
- [x] F0.5 — CI `.github/workflows/desktop.yml`: `pnpm lint`, `pnpm typecheck`, `pnpm test` antes del build de Tauri

**Verificación post-Fase 0:**

```bash
cd desktop && pnpm lint && pnpm typecheck && pnpm test
```

---

## Fase 1 — Funcionalidad core ✅ COMPLETADA

Commits: `0d76e5f`, `9422258`, `053f00c`

- [x] F1.1 — `cli_tool/sidecar/routers/version.py` (5 tests, 100% cov) + frontend `versionApi`
- [x] F1.2 — `tauri-plugin-updater` integrado: `src-tauri/src/updater.rs` con Channel streaming, `UpdateBanner.svelte` con polling 6h y dismiss 24h, 5 tests
- [x] F1.3 — CI: `tauri-action` con `includeUpdaterJson: true` publica `latest.json`
- [x] F1.4 — Matrix 4-way: linux x86_64, macos aarch64, macos x86_64, windows x86_64
- [x] F1.Docs — `docs/guides/desktop-installation.md` y `desktop-auto-update.md`

**Verificación post-Fase 1:**

```bash
cd desktop && pnpm lint && pnpm typecheck && pnpm test
pytest -m unit -q
```

---

---

## Fase 2 — Seguridad ✅ COMPLETADA

Commit: `9f9e11f`

- [x] F2.1 — CORS allowlist explícita (tauri://localhost + http://localhost:5173) con override via env
- [x] F2.2 — Bearer TTL 8h + `POST /api/v1/auth/refresh`; AppState centraliza emisión/expiración; frontend `authApi.refresh()` con coalescing y retry en 401
- [x] F2.3 — slowapi limiter en 4 endpoints sensibles (profiles, connections, logs); 429 con `Retry-After`; shim `enabled=False` para tests
- [x] F2.4 — `BodySizeLimitMiddleware` (1 MB) — 413 con detalle
- [x] F2.5 — Audit log JSONL con rotación diaria (30d retención), SHA-256 prefix del token, `GET /api/v1/audit?since=&limit=`
- [x] F2.6 — Tauri capabilities: removidos `shell:allow-execute` y `shell:allow-kill`
- [x] F2.7 — `.gitignore` cubre `~/.devo/` completo; `desktop-security.md` documenta el modelo de amenaza y cada capa

**45 nuevos tests backend (auth, audit, rate_limit, app CORS, body size), 2 nuevos tests frontend (api 401 retry).**

---

## Fase 3 — UI/UX ✅ COMPLETADA

Commits: `8e07b1b`, `0d0207c`, `45a8202`

- [x] F3.1 — `SearchInput.svelte` con debounce 200ms, botón clear, atajo Ctrl/Cmd+K
- [x] F3.2 — `FormField.svelte` + `forms.ts` con schemas Zod para database/instance/host; aplicado a HostsPage, InstancesPage, DatabasesPage
- [x] F3.3 — `LogsPage` reescrita: filtro por nivel + texto, streaming por WS (`log.line` event), Pause/Resume, Download `sidecar-YYYYMMDD.log`, cap 5000 líneas
- [x] F3.4 — `ConnectionRecord` con `uptime_seconds`/`attempts`/`last_error_at`; thread daemon emite `connection.metrics` cada 5s; columna Uptime + botón Restart
- [x] F3.5 — Tray icon con menu (Show/Quit), `close` intercepta a `hide()` (minimize-to-tray), `hide_to_tray` command
- [x] F3.6 — `lib/i18n/index.ts`: store locale (en/es), `t()` reactivo, dropdown en ConfigPage
- [x] F3.7 — `lib/theme.ts`: store dark/light/system con persistencia, CSS custom properties, dropdown en ConfigPage
- [x] F3.8 — `OnboardingPage.svelte`: wizard 3 pasos, marca `onboarded: true` en config
- [x] F3.9 — TitleBar badge "↑ update" cuando `updateAvailable` store; click invoca `installUpdate`

**18 nuevos tests frontend (15 SearchInput/forms + 3 update store).**

---

## Fase 4 — Test code ✅ COMPLETADA (con notas)

Commit: `703c7b5`

- [x] F4.1 — Cobertura sidecar: config_watcher 25→93%, connection_service 25→98%, profile_service 59→92%, profiles router 64→100%, audit_service 86% (defensive gaps)
- [x] F4.2 — Integration tests con `TestClient` (6 tests end-to-end: DB CRUD, conflict, connection lifecycle, 404s, WebSocket state_changed)
- [x] F4.4 — Contract tests: espejo manual de las rutas sidecar en `contract.test.ts`; cada `api.ts` helper se invoca y el path capturado se valida contra la lista (4 tests)
- [ ] F4.3 — Playwright E2E: fuera de scope. Tauri WebDriver requiere un binario compilado que el dev local no tiene siempre disponible. Se puede agregar después con `cargo tauri dev` + playwright en CI.
- [ ] F4.5 — Mutation testing (mutmut/stryker): fuera de scope, mejor correr en nightly si se quiere.

**51 nuevos tests (47 backend + 4 frontend).**

---

---

## Fase 3 — UI/UX

**Objetivo:** pulir la experiencia, no solo el MVP.

### F3.1 — Búsqueda global

- [ ] `SearchInput.svelte` (componente reusable con debounce 200ms)
- [ ] Cada page agrega un input arriba de su tabla que filtra in-memory
- [ ] Atajo `Ctrl+K` enfoca el input (handler global en `App.svelte`)
- [ ] Opcional backend: `GET /api/v1/search?q=` cross-router

### F3.2 — Validación de formularios

- [ ] `FormField.svelte` con label, input, error, hint
- [ ] Schema Zod (compartido) o Yup en cada modal
- [ ] Submit button disabled mientras `formState.valid === false`
- [ ] Aplicar en: DatabaseModal, InstanceModal, HostModal, ConfigPage
- [ ] Tests: `desktop/src/lib/__tests__/form.test.ts`

### F3.3 — LogsPage mejorada

- [ ] Filtro por nivel (DEBUG/INFO/WARN/ERROR) — select dropdown
- [ ] Búsqueda de texto
- [ ] Streaming via WS (event `log.line` desde sidecar) en vez de polling 3s
- [ ] Botón "Pause" / "Resume" auto-refresh
- [ ] Botón "Download" — `Content-Disposition: attachment; filename=sidecar-YYYYMMDD.log`

### F3.4 — Connection details en tiempo real

- [ ] `ConnectionRecord` extendido: `uptime_seconds`, `retries`, `last_error_at`
- [ ] WS event `connection.metrics` con esos datos
- [ ] `ConnectionsPage` muestra uptime, badge animado en `connecting`
- [ ] Botón "Restart" además de Start/Stop

### F3.5 — Tray icon + minimizar a tray

- [ ] `tauri-plugin-tray` (built-in en Tauri 2) o built-in tray support
- [ ] Click en X → `hide()` en vez de `close()`
- [ ] Menu tray: Show / Quit
- [ ] `tauri-plugin-single-instance` (evitar múltiples ventanas)

### F3.6 — i18n (preparación)

- [ ] `desktop/src/lib/i18n/en.ts` y `es.ts` con strings
- [ ] `t(key)` reactivo (basado en `$state` rune)
- [ ] Idioma desde `navigator.language` + override en ConfigPage
- [ ] Solo EN en este PR, ES stub para futuro

### F3.7 — Tema dark/light

- [ ] `theme: 'dark' | 'light'` en store global
- [ ] CSS custom properties en `page.css` y `modal.css`
- [ ] Toggle en `ConfigPage` o menú
- [ ] Default: respeta `prefers-color-scheme`

### F3.8 — Onboarding

- [ ] `OnboardingPage.svelte` si `~/.devo/config.json` no existe
- [ ] Wizard 3 pasos: Welcome + preflight check, SSO login, Add first instance/database
- [ ] Marca `onboarded: true` en config al terminar

### F3.9 — TitleBar: badge de updates

- [ ] Si `update.available`, dot amarillo en el logo
- [ ] Click → abre `UpdatePage` o expande `UpdateBanner`

**Commit esperado Fase 3:**
```
feat(desktop): search, form validation, log streaming, tray, i18n, theme
```

---

## Fase 4 — Test code

**Objetivo:** elevar coverage del sidecar al 90%+ y agregar tests del frontend.

### F4.1 — Sidecar coverage gaps

- [ ] `services/config_watcher.py`: 25% → 90%
- [ ] `services/connection_service.py`: 25% → 90%
- [ ] `services/profile_service.py`: 59% → 90%
- [ ] `routers/profiles.py`: 63% → 90%
- [ ] `services/audit_service.py` (nuevo en F2.5): ≥ 90%

### F4.2 — Tests de integración sidecar

- [ ] `TestClient` de FastAPI para flujos completos
- [ ] `test_full_flow.py`: create database → start connection → verify state via WS
- [ ] `test_refresh_all.py`: mock boto3, verificar polling de expiración
- [ ] `test_preflight.py`: mock subprocess con aws/socat/sm-plugin presentes y ausentes

### F4.3 — Tests E2E del frontend (Playwright)

- [ ] `desktop/tests/e2e/` con Playwright + Tauri WebDriver
- [ ] Tests:
  - `cold-start.spec.ts`: app loads, sidecar handshake, sidebar visible
  - `database-crud.spec.ts`: create, edit, delete database
  - `connection-lifecycle.spec.ts`: start, see "connecting" → "connected", stop
  - `profiles-refresh.spec.ts`: mock SSO, refresh_all, see status change
- [ ] Corren en CI en `ubuntu-22.04` con `xvfb-run`
- [ ] Script `pnpm test:e2e` en `package.json`

### F4.4 — Contract tests (sidecar ↔ frontend)

- [ ] Generar OpenAPI spec del sidecar en `/api/v1/openapi.json`
- [ ] Validar que cada `api.ts` endpoint matchea el spec
- [ ] Test falla si: response schema cambia sin actualizar TS

### F4.5 — Mutation testing (opcional, nightly)

- [ ] `mutmut` para Python, `stryker` para TS
- [ ] Solo corre en nightly, no bloquea PRs

**Commit esperado Fase 4:**
```
test(desktop,sidecar): raise coverage to 90% and add E2E suite
```

---

## Resumen de fases

| Fase | Commits estimados | Effort | Estado |
|---|---|---|---|
| 0. Foundation | 1 | 2-3 días | ✅ done (`1806ca4`) |
| 1. Funcionalidad core | 3 | 4-5 días | ✅ done (`053f00c`) |
| 2. Seguridad | 5 | 3-4 días | ✅ done (`9f9e11f`) |
| 3. UI/UX | 9 | 6-8 días | ✅ done (`45a8202`) |
| 4. Tests | 4 | 4-5 días | ✅ done (`703c7b5`) |

**Total: ~23 commits, 3-4 semanas secuenciales**

---

## Convenciones del proyecto

- **Branches:** solo `feature/desktop` mientras se desarrolla. Merge a `main` cuando esté todo verde.
- **Commits:** conventional (`feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`)
- **Pre-commit:** black + isort + flake8 (Python), ESLint + svelte-check (desktop), commitizen validator
- **Pre-push:** pytest -m unit (Python), vitest (desktop)
- **CI:** lint + typecheck + test antes del build de Tauri
- **No commit sin:** lint clean, typecheck 0 errors, tests passing

## Referencias

- `AGENTS.md` — instrucciones generales del proyecto
- `CLAUDE.md` (sección Desktop) — arquitectura, comandos, gotchas
- `desktop/package.json` — scripts y deps
- `.pre-commit-config.yaml` — hooks
- `.github/workflows/desktop.yml` — CI
