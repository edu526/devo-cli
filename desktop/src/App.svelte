<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    initApi,
    bootApi,
    type BootStatus,
    type VersionInfo,
    profilesApi,
    codeartifactApi,
    configApi,
  } from "./lib/api";
  import { ws } from "./lib/ws";
  import { sidecar, appStatus, appError, currentPage, wsConnected, type Page } from "./lib/stores";
  import { profilesCache, registryCache, configCache } from "./lib/page-stores";
  import { logError } from "./lib/error-log";
  import { theme, applyTheme } from "./lib/theme";
  import { getCurrentWindow } from "@tauri-apps/api/window";
  import { fade } from "svelte/transition";
  import { quintOut } from "svelte/easing";
  import TitleBar from "./lib/TitleBar.svelte";
  import LogsPage from "./pages/LogsPage.svelte";

  import DatabasesPage from "./pages/DatabasesPage.svelte";
  import ProfilesPage from "./pages/ProfilesPage.svelte";
  import ConfigPage from "./pages/ConfigPage.svelte";
  import OnboardingPage from "./pages/OnboardingPage.svelte";
  import RegistryPage from "./pages/RegistryPage.svelte";

  import { Database, KeyRound, Package, Settings, FileText } from "@lucide/svelte";

  const MAIN_NAV: { id: Page; label: string; icon: any }[] = [
    { id: "databases", label: "Databases", icon: Database },
    { id: "profiles", label: "Profiles", icon: KeyRound },
    { id: "registry", label: "Registry", icon: Package },
  ];

  const BOTTOM_NAV: { id: Page; label: string; icon: any }[] = [
    { id: "config", label: "Settings", icon: Settings },
    { id: "logs", label: "Logs", icon: FileText },
  ];

  // Subscribe once so the page re-renders when the theme toggles.
  $effect(() => {
    applyTheme($theme);
  });

  let showOnboarding = $state(false);
  let onboardingChecked = $state(false);
  let sidecarInfo: VersionInfo | null = $state(null);
  let versionCheck: { required: string; found: string } | null = $state(null);
  let copyLabel = $state("Copy");

  const UPGRADE_CMD = "devo upgrade";

  async function copyUpgrade() {
    try {
      await navigator.clipboard.writeText(UPGRADE_CMD);
      copyLabel = "Copied";
      setTimeout(() => (copyLabel = "Copy"), 1500);
    } catch {
      copyLabel = "Press Ctrl+C";
      setTimeout(() => (copyLabel = "Copy"), 2000);
    }
  }

  function formatSidecarVersion(v: string): string {
    const cleaned = v.split("+")[0] ?? v;
    const isDev = cleaned.includes(".dev");
    const base = cleaned.split(".dev")[0] ?? cleaned;
    return isDev ? `CLI v${base}-dev` : `CLI v${base}`;
  }

  function leaveOnboarding() {
    showOnboarding = false;
  }

  // ── Per-input undo/redo history (webkit2gtk doesn't support execCommand for inputs) ──

  type HistoryEntry = { value: string; start: number; end: number };
  type InputHistory = { stack: HistoryEntry[]; index: number };

  const inputHistory = new WeakMap<HTMLInputElement | HTMLTextAreaElement, InputHistory>();
  let _suppressRecord = false;

  function isEditableInput(el: Element | null): el is HTMLInputElement | HTMLTextAreaElement {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA";
  }

  function getHistory(el: HTMLInputElement | HTMLTextAreaElement): InputHistory {
    if (!inputHistory.has(el)) {
      inputHistory.set(el, {
        stack: [{ value: el.value, start: el.selectionStart ?? 0, end: el.selectionEnd ?? 0 }],
        index: 0,
      });
    }
    return inputHistory.get(el)!;
  }

  function recordFocus(e: FocusEvent) {
    const el = e.target as Element;
    if (!isEditableInput(el)) return;
    getHistory(el); // snapshot value before any edits
  }

  function recordInput(e: Event) {
    if (_suppressRecord) return;
    const el = e.target as Element;
    if (!isEditableInput(el)) return;
    const h = getHistory(el);
    h.stack = h.stack.slice(0, h.index + 1);
    h.stack.push({ value: el.value, start: el.selectionStart ?? 0, end: el.selectionEnd ?? 0 });
    h.index = h.stack.length - 1;
  }

  function applyEntry(el: HTMLInputElement | HTMLTextAreaElement, entry: HistoryEntry) {
    _suppressRecord = true;
    el.value = entry.value;
    el.setSelectionRange(entry.start, entry.end);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    _suppressRecord = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!e.ctrlKey) return;
    const el = document.activeElement;
    if (!isEditableInput(el)) return;
    if (e.key === "z" && !e.shiftKey) {
      e.preventDefault();
      const h = getHistory(el);
      if (h.index > 0) {
        h.index--;
        const entry = h.stack[h.index];
        if (entry) applyEntry(el, entry);
      }
    } else if (e.key === "y" || (e.key === "z" && e.shiftKey)) {
      e.preventDefault();
      const h = getHistory(el);
      if (h.index < h.stack.length - 1) {
        h.index++;
        const entry = h.stack[h.index];
        if (entry) applyEntry(el, entry);
      }
    }
  }

  // Ctrl/Cmd+K focuses the first SearchInput in the active page (if any).
  function handleGlobalShortcut(e: KeyboardEvent) {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "k") return;
    const target = document.querySelector<HTMLInputElement>('input[type="search"]');
    if (target) {
      e.preventDefault();
      target.focus();
      target.select();
    }
  }

  function blockBrowserShortcuts(e: KeyboardEvent) {
    if (e.key === "F5" || e.key === "F3") {
      e.preventDefault();
      return;
    }
    if (e.ctrlKey || e.metaKey) {
      const k = e.key.toLowerCase();
      // Bloquear Recargar (r), Buscar (f, g), Imprimir (p), Guardar (s), Abrir (o), Ver código (u)
      // Nota: e.preventDefault() cancela la acción del navegador pero el evento JS sigue fluyendo,
      // permitiendo atajos internos como Ctrl+S en CodeMirror de ConfigPage.
      if (["r", "f", "g", "p", "s", "o", "u"].includes(k)) {
        e.preventDefault();
      }
    }
    // Bloquear navegación hacia atrás/adelante (Alt + flechas)
    if (e.altKey && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
      e.preventDefault();
    }
  }

  function blockContextMenu(e: Event) {
    e.preventDefault();
  }

  onMount(async () => {
    window.addEventListener("keydown", handleKeydown, true);
    window.addEventListener("keydown", handleGlobalShortcut, true);
    window.addEventListener("keydown", blockBrowserShortcuts, true);
    window.addEventListener("contextmenu", blockContextMenu, true);
    window.addEventListener("focusin", recordFocus, true);
    window.addEventListener("input", recordInput, true);
    window.addEventListener("onboarding-complete", leaveOnboarding);
    window.addEventListener("error", (e) => {
      logError("window", e.message || "Uncaught error", e.error?.stack);
    });
    window.addEventListener("unhandledrejection", (e) => {
      const reason = e.reason instanceof Error ? e.reason.message : String(e.reason);
      logError(
        "unhandledrejection",
        reason,
        e.reason instanceof Error ? e.reason.stack : undefined,
      );
    });
    // Poll the Rust boot status. The version check happens in setup()
    // before the sidecar is spawned, so a stale bundle never produces
    // a half-running app.
    let boot: BootStatus | null = null;
    for (let i = 0; i < 60; i++) {
      try {
        boot = await bootApi.get();
        if (boot.status !== "loading") break;
      } catch {
        // invoke failed transiently; keep polling
      }
      await new Promise((r) => setTimeout(r, 500));
    }

    if (!boot || boot.status === "loading") {
      appStatus.set("error");
      appError.set("Sidecar failed to start after 30 seconds.");
      setTimeout(() => getCurrentWindow().show(), 50);
      return;
    }

    if (boot.status === "version_error") {
      versionCheck = { required: boot.required, found: boot.found };
      appStatus.set("error");
      appError.set(
        `Devo Desktop requires devo-cli ${boot.required} or newer (found ${boot.found}).`,
      );
      setTimeout(() => getCurrentWindow().show(), 50);
      return;
    }

    const info = boot.sidecar_info;
    sidecar.set(info);
    await initApi();
    ws.on("$connected", () => wsConnected.set(true));
    ws.on("$disconnected", () => wsConnected.set(false));
    ws.connect(info.port);
    appStatus.set("ready");

    sidecarInfo = {
      sidecar_version: boot.version,
      server_version: boot.version,
      build_date: null,
      update_available: false,
    };

    // Check if the user has been onboarded; if not, show the wizard.
    try {
      const cfg = await configApi.get();
      if (cfg.onboarded !== true) {
        showOnboarding = true;
      }
      onboardingChecked = true;
    } catch {
      // If the config endpoint is unreachable we silently skip; the
      // user can still use the app via the regular pages.
      onboardingChecked = true;
    }

    // Unhide the window now that the UI is fully set up
    setTimeout(() => getCurrentWindow().show(), 50);

    // Prefetch data in the background so tabs are instantly ready
    profilesApi
      .list()
      .then((p) => profilesCache.set(p))
      .catch(() => {});
    Promise.all([codeartifactApi.domains(), codeartifactApi.tokens()])
      .then(([d, t]) => registryCache.set({ domains: d, tokens: t }))
      .catch(() => {});
    configApi
      .get()
      .then((c) => configCache.set(c))
      .catch(() => {});
  });

  onDestroy(() => {
    window.removeEventListener("keydown", handleKeydown, true);
    window.removeEventListener("keydown", handleGlobalShortcut, true);
    window.removeEventListener("keydown", blockBrowserShortcuts, true);
    window.removeEventListener("contextmenu", blockContextMenu, true);
    window.removeEventListener("focusin", recordFocus, true);
    window.removeEventListener("input", recordInput, true);
    window.removeEventListener("onboarding-complete", leaveOnboarding);
  });
</script>

<TitleBar />

{#if $appStatus === "loading"}
  <div class="splash">
    <div class="spinner"></div>
    <p>Starting Devo…</p>
  </div>
{:else if $appStatus === "error"}
  <div class="splash err-splash">
    <div class="err-card" role="alert">
      <div class="err-icon" aria-hidden="true">!</div>
      <div class="err-text">
        <h1 class="err-title">
          {versionCheck ? "Devo Desktop needs an update" : "Devo Desktop couldn't start"}
        </h1>
        {#if versionCheck}
          <p class="err-body">
            You have <code class="err-ver">{versionCheck.found}</code>; the desktop requires
            <code class="err-ver">{versionCheck.required}</code> or newer.
          </p>
          <p class="err-hint">Run this in your terminal, then relaunch:</p>
          <div class="err-code-row">
            <pre class="err-code">$ {UPGRADE_CMD}</pre>
            <button
              class="err-copy"
              type="button"
              onclick={copyUpgrade}
              aria-label="Copy upgrade command">{copyLabel}</button
            >
          </div>
          <p class="err-tray">Or quit via the system tray menu.</p>
        {:else}
          <p class="err-body">{$appError}</p>
        {/if}
      </div>
    </div>
  </div>
{:else if showOnboarding && onboardingChecked}
  <OnboardingPage />
{:else}
  <div class="layout" in:fade={{ duration: 600, delay: 300, easing: quintOut }}>
    <!-- Sidebar -->
    <nav class="sidebar">
      <!-- Main Nav -->
      <div class="nav-section" style="padding-top: 1rem;">
        <ul>
          {#each MAIN_NAV as item}
            {@const Icon = item.icon}
            <li>
              <button
                class="nav-btn"
                class:active={$currentPage === item.id}
                onclick={() => currentPage.set(item.id)}
              >
                <span class="nav-icon"><Icon size={16} strokeWidth={2} /></span>
                <span class="nav-label">{item.label}</span>
              </button>
            </li>
          {/each}
        </ul>
      </div>

      <!-- Spacer -->
      <div class="nav-spacer" style="flex: 1;"></div>

      <!-- Bottom Nav -->
      <div class="nav-section">
        <ul>
          {#each BOTTOM_NAV as item}
            {@const Icon = item.icon}
            <li>
              <button
                class="nav-btn"
                class:active={$currentPage === item.id}
                onclick={() => currentPage.set(item.id)}
              >
                <span class="nav-icon"><Icon size={16} strokeWidth={2} /></span>
                <span class="nav-label">{item.label}</span>
              </button>
            </li>
          {/each}
        </ul>
      </div>
      <div class="ws-status" class:connected={$wsConnected}>
        <span class="ws-state">{$wsConnected ? "● Live" : "○ Offline"}</span>
        {#if sidecarInfo}
          <span class="ws-version" title="devo CLI v{sidecarInfo.sidecar_version}">
            {formatSidecarVersion(sidecarInfo.sidecar_version)}
            {#if sidecarInfo.update_available}
              <span class="ws-update" title="A newer version is available — run: devo upgrade"
                >↑</span
              >
            {/if}
          </span>
        {/if}
      </div>
    </nav>

    <!-- Main content -->
    <main class="content">
      {#if $currentPage === "connections" || $currentPage === "databases"}
        <DatabasesPage />
      {:else if $currentPage === "profiles"}
        <ProfilesPage />
      {:else if $currentPage === "config"}
        <ConfigPage />
      {:else if $currentPage === "registry"}
        <RegistryPage />
      {:else if $currentPage === "logs"}
        <LogsPage />
      {/if}
    </main>
  </div>
{/if}

<style>
  /* ── Theme tokens ────────────────────────────────────────────────────── */
  :global(:root[data-theme="dark"]) {
    color-scheme: dark;
    --bg-base: #0f0f0f;
    --bg-sidebar: #141414;
    --bg-surface: #1a1a1a;
    --bg-surface-2: #1e1e1e;
    --bg-elevated: #1e1e2e;
    --text-primary: #e0e0e0;
    --text-secondary: #94a3b8;
    --text-muted: #8a8a8a;
    --text-faint: #6a6a6a;
    --border: #2a2a2a;
    --border-strong: #3a3a3a;
    --accent: #4f8ef7;
    --accent-soft: #1e1e2e;
    --success: #4ade80;
    --warning: #fbbf24;
    --danger: #f87171;
    --info: #94a3b8;
  }
  :global(:root[data-theme="light"]) {
    color-scheme: light;
    --bg-base: #fafafa;
    --bg-sidebar: #f0f0f0;
    --bg-surface: #ffffff;
    --bg-surface-2: #f6f6f6;
    --bg-elevated: #e9efff;
    --text-primary: #1a1a1a;
    --text-secondary: #475569;
    --text-muted: #64748b;
    --text-faint: #94a3b8;
    --border: #e2e8f0;
    --border-strong: #cbd5e1;
    --accent: #2563eb;
    --accent-soft: #dbeafe;
    --success: #16a34a;
    --warning: #d97706;
    --danger: #dc2626;
    --info: #475569;
  }
  /* The default is dark; this keeps the legacy look for any element that
     somehow runs before App.svelte mounts. */
  :global(:root) {
    color-scheme: dark;
    --bg-base: #0f0f0f;
    --bg-sidebar: #141414;
    --bg-surface: #1a1a1a;
    --bg-surface-2: #1e1e1e;
    --bg-elevated: #1e1e2e;
    --text-primary: #e0e0e0;
    --text-secondary: #94a3b8;
    --text-muted: #8a8a8a;
    --text-faint: #6a6a6a;
    --border: #2a2a2a;
    --border-strong: #3a3a3a;
    --accent: #4f8ef7;
    --accent-soft: #1e1e2e;
    --success: #4ade80;
    --warning: #fbbf24;
    --danger: #f87171;
    --info: #94a3b8;
  }

  :global(*, *::before, *::after) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  :global(body) {
    background: var(--bg-base);
    color: var(--text-primary);
    font-family:
      "Inter",
      system-ui,
      -apple-system,
      sans-serif;
    font-size: 14px;
    height: 100vh;
    overflow: hidden;
  }
  :global(#app) {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }

  .splash {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: calc(100vh - 36px);
    gap: 1rem;
    color: var(--text-secondary);
  }

  .err-splash {
    padding: 2rem;
  }

  .err-card {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    max-width: 520px;
    width: 100%;
    padding: 1.25rem 1.5rem;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--danger);
    border-radius: 8px;
    box-shadow: 0 4px 20px rgb(0 0 0 / 0.25);
    text-align: left;
  }

  .err-icon {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: color-mix(in srgb, var(--danger) 18%, transparent);
    color: var(--danger);
    font-weight: 700;
    font-size: 1.1rem;
    font-family: "JetBrains Mono", monospace;
  }

  .err-text {
    flex: 1;
    min-width: 0;
  }

  .err-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.4rem;
  }

  .err-body {
    color: var(--text-secondary);
    font-size: 0.875rem;
    line-height: 1.5;
    margin-bottom: 0.6rem;
  }

  .err-ver {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.8rem;
    padding: 0.05rem 0.35rem;
    background: var(--bg-surface-2);
    border: 1px solid var(--border);
    border-radius: 3px;
    color: var(--text-primary);
  }

  .err-hint {
    color: var(--text-muted);
    font-size: 0.8rem;
    margin: 0.75rem 0 0.4rem;
  }

  .err-code-row {
    display: flex;
    align-items: stretch;
    gap: 0.4rem;
    margin-bottom: 0.75rem;
  }

  .err-code {
    flex: 1;
    min-width: 0;
    margin: 0;
    padding: 0.55rem 0.75rem;
    background: var(--bg-base);
    border: 1px solid var(--border);
    border-radius: 5px;
    color: var(--accent);
    font-family: "JetBrains Mono", monospace;
    font-size: 0.825rem;
    overflow-x: auto;
    white-space: nowrap;
  }

  .err-copy {
    flex-shrink: 0;
    padding: 0 0.85rem;
    background: var(--bg-elevated);
    color: var(--text-primary);
    border: 1px solid var(--border-strong);
    border-radius: 5px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition:
      background 0.12s,
      border-color 0.12s;
  }
  .err-copy:hover {
    background: var(--accent-soft);
    border-color: var(--accent);
  }
  .err-copy:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .err-tray {
    color: var(--text-faint);
    font-size: 0.75rem;
    margin: 0;
  }

  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .layout {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    height: calc(100vh - 36px);
  }

  .sidebar {
    width: 180px;
    flex-shrink: 0;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 0.5rem 0;
  }

  ul {
    list-style: none;
  }

  .nav-section {
    padding: 0.2rem 0;
  }

  .nav-btn {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 1.2rem;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.85rem;
    transition:
      color 0.15s,
      background 0.15s;
    text-align: left;
  }
  .nav-btn:hover {
    color: var(--text-primary);
    background: var(--bg-surface-2);
  }
  .nav-btn.active {
    color: var(--text-primary);
    background: var(--bg-elevated);
  }
  .nav-btn.active .nav-label {
    color: var(--accent);
  }
  .nav-icon {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 20px;
    flex-shrink: 0;
  }

  .ws-status {
    margin-top: auto;
    padding: 0.6rem 1.2rem;
    font-size: 0.75rem;
    color: #555;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-width: 0;
  }
  .ws-state,
  .ws-version {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ws-state {
    flex-shrink: 0;
  }
  .ws-status.connected {
    color: var(--success);
  }
  .ws-version {
    flex-shrink: 1;
    min-width: 0;
    margin-left: auto;
    color: var(--text-faint);
    font-family: "JetBrains Mono", monospace;
    font-size: 0.7rem;
    font-weight: 500;
  }
  .ws-update {
    color: var(--warning);
    margin-left: 0.15rem;
    font-weight: 700;
    cursor: help;
  }

  .content {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 2rem;
  }
</style>
