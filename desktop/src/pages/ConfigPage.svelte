<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { EditorView, basicSetup } from "codemirror";
  import { json } from "@codemirror/lang-json";
  import { oneDark } from "@codemirror/theme-one-dark";
  import { Compartment, EditorState } from "@codemirror/state";
  import { keymap } from "@codemirror/view";
  import { configApi, ApiError } from "../lib/api";
  import { get } from "svelte/store";
  import { configCache } from "../lib/page-stores";
  import { isAutostartEnabled, setAutostartEnabled } from "../lib/autostart";
  import { theme, type Theme } from "../lib/theme";
  import { fetchUpdate, getAppVersion, installUpdate, updateAvailable, type ProgressState } from "../lib/update";
  import Switch from "../lib/Switch.svelte";
  import { autoOpenBrowser as autoOpenBrowserIn } from "../lib/login-flow";

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
  let updateBusy = $state(false);
  let updateCheckResult: string | null = $state(null);
  let installError: string | null = $state(null);

  // One button, two phases: first click checks the manifest; once an update
  // is known to be available ($updateAvailable), the same button switches to
  // triggering the actual install instead of checking again.
  async function handleUpdateClick() {
    if (updateBusy) return;
    if ($updateAvailable) {
      updateBusy = true;
      installError = null;
      // `installUpdate` never throws — a failed download or install (no
      // pending update, network error, etc.) is only reported through the
      // progress callback, so it must be read from there.
      let progress: ProgressState = { phase: "idle", downloaded: 0, total: null, error: null };
      const ok = await installUpdate((s) => {
        progress = typeof s === "function" ? s(progress) : s;
      });
      updateBusy = false;
      if (!ok) {
        installError = progress.error ?? "Update failed";
      }
      return;
    }

    updateBusy = true;
    updateCheckResult = null;
    installError = null;
    try {
      const result = await fetchUpdate();
      updateCheckResult = result
        ? `Update available: v${result.version}`
        : `You're up to date (v${currentVersion})`;
    } finally {
      updateBusy = false;
    }
  }

  /**
   * A toggle saved a setting: show it in the JSON editor too, unless the
   * editor has unsaved edits. Otherwise a later Save would quietly write the
   * old value back.
   */
  function applySaved(next: Record<string, unknown>) {
    const unedited = view !== null && view.state.doc.toString() === JSON.stringify(config, null, 2);
    config = next;
    configCache.set(next);
    if (view && unedited) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: JSON.stringify(next, null, 2) } });
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
      applySaved(await configApi.patch({ notifications_enabled: next }));
      notificationsEnabled = config.notifications_enabled !== false;
    } catch (e) {
      notificationsError = e instanceof Error ? e.message : String(e);
    } finally {
      notificationsBusy = false;
    }
  }

  // Off: a login Devo would start by itself (at launch, for an expired
  // tunnel, for the background renewal) is offered on the "Log in" banner.
  // Clicking Connect, Start All, Refresh or Log in always opens the browser
  // when needed.
  let autoOpenBrowser = $state(autoOpenBrowserIn(initialCache ?? {}));
  let autoOpenBrowserBusy = $state(false);
  let autoOpenBrowserError: string | null = $state(null);

  async function toggleAutoOpenBrowser() {
    const next = !autoOpenBrowser;
    autoOpenBrowserBusy = true;
    autoOpenBrowserError = null;
    try {
      applySaved(await configApi.patch({ aws_login: { auto_open_browser: next } }));
      autoOpenBrowser = autoOpenBrowserIn(config);
    } catch (e) {
      autoOpenBrowserError = e instanceof Error ? e.message : String(e);
    } finally {
      autoOpenBrowserBusy = false;
    }
  }

  let debugMode = $state(false);
  let debugBusy = $state(false);
  let debugError: string | null = $state(null);

  async function toggleDebugMode() {
    const nextVal = !debugMode;
    debugBusy = true;
    debugError = null;
    try {
      applySaved(await configApi.patch({ debug_mode: nextVal }));
      debugMode = !!config.debug_mode;
    } catch (e) {
      debugError = e instanceof Error ? e.message : String(e);
    } finally {
      debugBusy = false;
    }
  }

  const configPath = navigator.userAgent.includes("Windows")
    ? "%USERPROFILE%\\.devo\\config.json"
    : "~/.devo/config.json";

  let editorEl: HTMLDivElement;
  let view: EditorView | null = null;

  // The editor follows the app theme (`data-theme` on <html>, already
  // resolved for "system"): One Dark when dark, CodeMirror's own light colors
  // when light, where One Dark's pale text is hard to read.
  const editorTheme = new Compartment();
  const editorThemeFor = () => (document.documentElement.getAttribute("data-theme") === "light" ? [] : oneDark);
  const themeObserver = new MutationObserver(() => {
    view?.dispatch({ effects: editorTheme.reconfigure(editorThemeFor()) });
  });

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
        editorTheme.of(editorThemeFor()),
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

  /** The switches show what `config` says (after loading it or saving the JSON). */
  function syncSwitches() {
    notificationsEnabled = config.notifications_enabled !== false;
    autoOpenBrowser = autoOpenBrowserIn(config);
    debugMode = !!config.debug_mode;
  }

  async function load() {
    try {
      config = await configApi.get();
      configCache.set(config);
      syncSwitches();
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
      configCache.set(config);
      syncSwitches();
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
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    createEditor("");
    load();
    isAutostartEnabled().then((v) => {
      autostart = v;
    });
    getAppVersion().then((v) => {
      currentVersion = v;
    });
  });

  onDestroy(() => {
    themeObserver.disconnect();
    view?.destroy();
  });
</script>

<div class="page settings-page">
  <div class="page-header">
    <h1>Settings</h1>
  </div>

  <section class="card" aria-labelledby="settings-general">
    <h2 id="settings-general">General</h2>

    <div class="setting">
      <div class="setting-text">
        <label for="opt-autostart">Launch Devo at system startup</label>
        <p id="opt-autostart-desc">Start Devo in the background when you sign in to your computer.</p>
        {#if autostartError}
          <p class="setting-error">{autostartError}</p>
        {/if}
      </div>
      <Switch
        id="opt-autostart"
        describedby="opt-autostart-desc"
        checked={autostart}
        disabled={autostartBusy}
        onchange={toggleAutostart}
      />
    </div>

    <div class="setting">
      <div class="setting-text">
        <label for="opt-theme">Theme</label>
        <p id="opt-theme-desc">System follows your computer's light or dark mode.</p>
      </div>
      <select
        id="opt-theme"
        class="select"
        aria-describedby="opt-theme-desc"
        value={$theme}
        onchange={(e) => theme.set(e.currentTarget.value as Theme)}
      >
        <option value="dark">Dark</option>
        <option value="light">Light</option>
        <option value="system">System</option>
      </select>
    </div>

    <div class="setting">
      <div class="setting-text">
        <label for="opt-notifications">Desktop notifications</label>
        <p id="opt-notifications-desc">
          Tell you about what happens while Devo is in the background, such as an AWS session that needs a login.
        </p>
        {#if notificationsError}
          <p class="setting-error">{notificationsError}</p>
        {/if}
      </div>
      <Switch
        id="opt-notifications"
        describedby="opt-notifications-desc"
        checked={notificationsEnabled}
        disabled={notificationsBusy}
        onchange={toggleNotifications}
      />
    </div>
  </section>

  <section class="card" aria-labelledby="settings-aws">
    <h2 id="settings-aws">AWS sign-in</h2>

    <div class="setting">
      <div class="setting-text">
        <label for="opt-auto-browser">Open the browser to sign in automatically</label>
        <p id="opt-auto-browser-desc">
          Whenever your AWS credentials need a login (when Devo starts, a tunnel's credentials expire, or a
          profile's do in the background), Devo opens your browser so you can sign in. If you leave a login
          unfinished, the next one waits up to 2 hours. Turn it off to get a notification and a Log in button
          instead. Clicking Connect, Start All, Refresh or Log in opens it either way.
        </p>
        {#if autoOpenBrowserError}
          <p class="setting-error">{autoOpenBrowserError}</p>
        {/if}
      </div>
      <Switch
        id="opt-auto-browser"
        describedby="opt-auto-browser-desc"
        checked={autoOpenBrowser}
        disabled={autoOpenBrowserBusy}
        onchange={toggleAutoOpenBrowser}
      />
    </div>
  </section>

  <section class="card" aria-labelledby="settings-updates">
    <h2 id="settings-updates">Updates</h2>

    <div class="setting">
      <div class="setting-text">
        <span class="setting-title">Devo {currentVersion ? `v${currentVersion}` : ""}</span>
        {#if installError}
          <p class="setting-error">{installError}</p>
        {:else if $updateAvailable}
          <p class="update-available">Version {$updateAvailable.version} is available.</p>
        {:else if updateCheckResult}
          <p>{updateCheckResult}</p>
        {:else}
          <p>Check whether a newer version is available.</p>
        {/if}
      </div>
      <button
        class={$updateAvailable ? "btn-primary" : "btn-secondary"}
        onclick={handleUpdateClick}
        disabled={updateBusy}
      >
        {#if updateBusy}
          <span class="spinner-sm"></span>
          {$updateAvailable ? "Installing…" : "Checking…"}
        {:else}
          {$updateAvailable ? "Install update" : "Check for updates"}
        {/if}
      </button>
    </div>
  </section>

  <section class="card" aria-labelledby="settings-advanced">
    <h2 id="settings-advanced">Advanced</h2>

    <div class="setting">
      <div class="setting-text">
        <label for="opt-debug">Backend debug logs</label>
        <p id="opt-debug-desc">
          Write detailed logs from Devo's background service. Takes effect after restarting Devo.
        </p>
        {#if debugError}
          <p class="setting-error">{debugError}</p>
        {/if}
      </div>
      <Switch
        id="opt-debug"
        describedby="opt-debug-desc"
        checked={debugMode}
        disabled={debugBusy}
        onchange={toggleDebugMode}
      />
    </div>

    <div class="setting editor-setting">
      <div class="editor-header">
        <div class="setting-text">
          <span class="setting-title">config.json</span>
          <p>
            Every setting, including the ones above. Saved to <code>{configPath}</code>.
            <span class="shortcuts">Ctrl+S save · Ctrl+Z undo · Ctrl+Y redo</span>
          </p>
        </div>
        <div class="actions">
          <button class="btn-secondary" onclick={reset} disabled={loading}>Reset</button>
          <button class="btn-primary" onclick={save} disabled={saving || loading}>
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
      {#if loading}
        <p class="muted">Loading…</p>
      {/if}
      <div class="editor-wrap" class:hidden={loading} bind:this={editorEl}></div>
    </div>
  </section>
</div>

<style>
  .settings-page {
    max-width: 880px;
  }

  .card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.25rem 1.25rem;
  }

  .card h2 {
    margin: 0;
    padding: 0.9rem 0 0.4rem;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-faint);
  }

  .setting {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 0.9rem 0;
  }

  .setting + .setting {
    border-top: 1px solid var(--border);
  }

  .setting-text {
    min-width: 0;
  }

  .setting-text label,
  .setting-title {
    display: block;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary);
  }

  .setting-text label {
    cursor: pointer;
  }

  .setting-text p {
    margin: 0.25rem 0 0;
    font-size: 0.8rem;
    line-height: 1.45;
    color: var(--text-muted);
  }

  .setting-text p.setting-error {
    color: var(--danger);
  }

  .setting-text p.update-available {
    color: var(--accent);
  }

  .select {
    flex-shrink: 0;
    background: var(--bg-surface-2);
    color: var(--text-primary);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    padding: 0.35rem 0.5rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .select:focus-visible {
    outline: none;
    border-color: var(--accent);
  }

  .setting button {
    flex-shrink: 0;
  }

  .editor-setting {
    display: block;
  }

  .editor-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.5rem;
    margin-bottom: 0.75rem;
  }

  .editor-setting .alert-error,
  .editor-setting .muted {
    margin: 0 0 0.75rem;
  }

  .shortcuts {
    display: block;
    margin-top: 0.15rem;
    color: var(--text-faint);
    font-size: 0.75rem;
  }

  .editor-wrap {
    height: min(60vh, 32rem);
    min-height: 16rem;
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

  @media (max-width: 560px) {
    .setting,
    .editor-header {
      flex-wrap: wrap;
      gap: 0.75rem;
    }
  }
</style>
