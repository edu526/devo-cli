<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { EditorView, basicSetup } from "codemirror";
  import { json } from "@codemirror/lang-json";
  import { oneDark } from "@codemirror/theme-one-dark";
  import { EditorState } from "@codemirror/state";
  import { keymap } from "@codemirror/view";
  import { configApi, ApiError } from "../lib/api";
  import { get } from "svelte/store";
  import { configCache } from "../lib/page-stores";
  import { isAutostartEnabled, setAutostartEnabled } from "../lib/autostart";
  import { theme, type Theme } from "../lib/theme";
  import { fetchUpdate, getAppVersion } from "../lib/update";

  const initialCache = get(configCache);
  let config: Record<string, unknown> = $state(initialCache ?? {});
  let loading = $state(!initialCache);
  let saving = $state(false);
  let parseError: string | null = $state(null);
  let saveOk = $state(false);

  let autostart = $state(false);
  let autostartBusy = $state(false);
  let autostartError: string | null = $state(null);

  async function toggleAutostart() {
    const next = !autostart;
    autostartBusy = true;
    autostartError = null;
    try {
      await setAutostartEnabled(next);
      autostart = next;
    } catch (e) {
      autostartError = e instanceof Error ? e.message : String(e);
    } finally {
      autostartBusy = false;
    }
  }

  let currentVersion: string | null = $state(null);
  let checkingUpdate = $state(false);
  let updateCheckResult: string | null = $state(null);

  async function checkForUpdates() {
    checkingUpdate = true;
    updateCheckResult = null;
    try {
      const result = await fetchUpdate();
      if (result) {
        updateCheckResult = `Update available: v${result.version}`;
      } else {
        updateCheckResult = `You're up to date (v${currentVersion})`;
      }
    } finally {
      checkingUpdate = false;
    }
  }

  let notificationsEnabled = $state(true);
  let notificationsBusy = $state(false);
  let notificationsError: string | null = $state(null);

  async function toggleNotifications() {
    const next = !notificationsEnabled;
    notificationsBusy = true;
    notificationsError = null;
    try {
      config = await configApi.patch({ notifications_enabled: next });
      configCache.set(config);
      notificationsEnabled = config.notifications_enabled !== false;
    } catch (e) {
      notificationsError = e instanceof Error ? e.message : String(e);
    } finally {
      notificationsBusy = false;
    }
  }

  let debugMode = $state(false);

  async function toggleDebugMode() {
    const nextVal = !debugMode;
    try {
      await configApi.patch({ debug_mode: nextVal });
      debugMode = nextVal;
    } catch {
      parseError = "Failed to update debug mode";
    }
  }

  const configPath = navigator.userAgent.includes("Windows")
    ? "%USERPROFILE%\\.devo\\config.json"
    : "~/.devo/config.json";

  let editorEl: HTMLDivElement;
  let view: EditorView | null = null;

  function createEditor(initialContent: string) {
    if (view) view.destroy();

    const saveKeymap = keymap.of([
      {
        key: "Mod-s",
        run: () => {
          save();
          return true;
        },
      },
    ]);

    const state = EditorState.create({
      doc: initialContent,
      extensions: [
        basicSetup,
        json(),
        oneDark,
        saveKeymap,
        EditorView.theme({
          "&": { height: "100%", fontSize: "0.82rem" },
          ".cm-scroller": {
            fontFamily: '"JetBrains Mono", "Cascadia Code", monospace',
            overflow: "auto",
          },
          ".cm-content": { padding: "0.75rem 0" },
          "&.cm-focused": { outline: "none" },
        }),
        EditorView.lineWrapping,
      ],
    });

    view = new EditorView({ state, parent: editorEl });
  }

  async function load() {
    try {
      config = await configApi.get();
      configCache.set(config);
      notificationsEnabled = config.notifications_enabled !== false;
      debugMode = !!config.debug_mode;
      const text = JSON.stringify(config, null, 2);
      if (view) {
        view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
      } else {
        createEditor(text);
      }
    } catch (e) {
      parseError = String(e);
    } finally {
      loading = false;
    }
  }

  async function save() {
    if (!view) return;
    parseError = null;
    saveOk = false;
    const raw = view.state.doc.toString();
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      parseError = `JSON parse error: ${e}`;
      return;
    }
    saving = true;
    try {
      config = await configApi.put(parsed);
      const updated = JSON.stringify(config, null, 2);
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: updated } });
      saveOk = true;
      setTimeout(() => {
        saveOk = false;
      }, 2000);
    } catch (e) {
      parseError = e instanceof ApiError ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  function reset() {
    if (!view) return;
    parseError = null;
    const text = JSON.stringify(config, null, 2);
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
  }

  onMount(() => {
    createEditor("");
    load();
    isAutostartEnabled().then((v) => {
      autostart = v;
    });
    getAppVersion().then((v) => {
      currentVersion = v;
    });
  });

  onDestroy(() => view?.destroy());
</script>

<div class="page" style="height: calc(100vh - 36px - 4rem);">
  <div class="page-header">
    <h1>Config</h1>
    <div class="actions">
      <button class="btn-secondary" onclick={reset}>Reset</button>
      <button class="btn-primary" onclick={save} disabled={saving}>
        {#if saving}
          <span class="spinner-sm"></span> Saving…
        {:else if saveOk}
          Saved ✓
        {:else}
          Save
        {/if}
      </button>
    </div>
  </div>

  {#if parseError}
    <div class="alert-error">{parseError}</div>
  {/if}

  <div class="app-settings">
    <label class="autostart-toggle" title="Registers Devo to start automatically when you log in.">
      <input
        type="checkbox"
        checked={autostart}
        disabled={autostartBusy}
        onchange={toggleAutostart}
      />
      Launch Devo at system startup
    </label>
    {#if autostartError}
      <span class="autostart-error">{autostartError}</span>
    {/if}

    <label class="theme-select">
      Theme
      <select value={$theme} onchange={(e) => theme.set(e.currentTarget.value as Theme)}>
        <option value="dark">Dark</option>
        <option value="light">Light</option>
        <option value="system">System</option>
      </select>
    </label>

    <label class="notifications-toggle" title="Show OS desktop notifications for background events.">
      <input
        type="checkbox"
        checked={notificationsEnabled}
        disabled={notificationsBusy}
        onchange={toggleNotifications}
      />
      Desktop notifications
    </label>
    {#if notificationsError}
      <span class="autostart-error">{notificationsError}</span>
    {/if}

    <label class="autostart-toggle" title="Enable Uvicorn debug logs. Requires app restart to take effect.">
      <input type="checkbox" checked={debugMode} onchange={toggleDebugMode} />
      Backend Debug Mode
    </label>
  </div>

  <div class="app-settings">
    <button class="btn-secondary" onclick={checkForUpdates} disabled={checkingUpdate}>
      {checkingUpdate ? "Checking…" : "Check for updates"}
    </button>
    {#if updateCheckResult}
      <span class="update-status">{updateCheckResult}</span>
    {/if}
  </div>

  {#if loading}
    <p class="muted">Loading…</p>
  {:else}
    <p class="muted hint">
      Edit the JSON below. Changes are written to <code>{configPath}</code>.
      <span class="shortcuts">Ctrl+Z undo · Ctrl+Y redo · Ctrl+S save</span>
    </p>
  {/if}

  <div class="editor-wrap" class:hidden={loading} bind:this={editorEl}></div>
</div>

<style>
  .app-settings {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem 1.25rem;
    margin-bottom: 0.75rem;
  }

  .autostart-toggle,
  .notifications-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
  }

  .autostart-toggle input,
  .notifications-toggle input {
    cursor: pointer;
  }

  .autostart-error {
    color: var(--danger);
    font-size: 0.8rem;
  }

  .theme-select {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-secondary);
    user-select: none;
  }

  .theme-select select {
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.2rem 0.4rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .theme-select select:focus-visible {
    outline: none;
    border-color: var(--accent);
  }

  .update-status {
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .hint {
    margin-bottom: 0.5rem;
  }

  .shortcuts {
    margin-left: 0.75rem;
    color: var(--text-faint);
    font-size: 0.75rem;
  }

  .editor-wrap {
    flex: 1;
    min-height: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    transition: border-color 0.15s;
  }

  .editor-wrap:focus-within {
    border-color: var(--accent);
  }

  .editor-wrap.hidden {
    display: none;
  }

  .editor-wrap :global(.cm-editor) {
    background: var(--bg-surface);
    width: 100%;
    height: 100%;
    min-height: 0;
  }

  .editor-wrap :global(.cm-gutters) {
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
  }
</style>
