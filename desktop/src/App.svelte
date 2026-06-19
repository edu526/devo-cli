<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { initApi, configApi } from "./lib/api";
  import { ws } from "./lib/ws";
  import { sidecar, appStatus, appError, currentPage, wsConnected, type Page } from "./lib/stores";
  import { theme, applyTheme } from "./lib/theme";
  import TitleBar from "./lib/TitleBar.svelte";
  import UpdateBanner from "./lib/UpdateBanner.svelte";
  import LogsPage from "./pages/LogsPage.svelte";

  import ConnectionsPage from "./pages/ConnectionsPage.svelte";
  import InstancesPage from "./pages/InstancesPage.svelte";
  import DatabasesPage from "./pages/DatabasesPage.svelte";
  import ProfilesPage from "./pages/ProfilesPage.svelte";
  import HostsPage from "./pages/HostsPage.svelte";
  import ConfigPage from "./pages/ConfigPage.svelte";
  import OnboardingPage from "./pages/OnboardingPage.svelte";

  const NAV: { id: Page; label: string; icon: string }[] = [
    { id: "connections", label: "Connections", icon: "⚡" },
    { id: "instances", label: "Instances", icon: "🖥️" },
    { id: "databases", label: "Databases", icon: "🗄️" },
    { id: "profiles", label: "AWS Profiles", icon: "🔑" },
    { id: "hosts", label: "Hosts", icon: "🌐" },
    { id: "config", label: "Config", icon: "⚙️" },
    { id: "logs", label: "Logs", icon: "📋" },
  ];

  // Subscribe once so the page re-renders when the theme toggles.
  $effect(() => {
    applyTheme($theme);
  });

  let showOnboarding = $state(false);
  let onboardingChecked = $state(false);

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

  onMount(async () => {
    window.addEventListener("keydown", handleKeydown, true);
    window.addEventListener("keydown", handleGlobalShortcut, true);
    window.addEventListener("focusin", recordFocus, true);
    window.addEventListener("input", recordInput, true);
    window.addEventListener("onboarding-complete", leaveOnboarding);
    // Poll until Tauri has the sidecar info (spawned async in Rust setup())
    let info = null;
    for (let i = 0; i < 60; i++) {
      try {
        info = await initApi();
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 500));
      }
    }
    if (!info) {
      appStatus.set("error");
      appError.set("Sidecar failed to start after 30 seconds.");
      return;
    }

    sidecar.set(info);
    ws.on("$connected", () => wsConnected.set(true));
    ws.on("$disconnected", () => wsConnected.set(false));
    ws.connect(info.port);
    appStatus.set("ready");

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
  });

  onDestroy(() => {
    window.removeEventListener("keydown", handleKeydown, true);
    window.removeEventListener("keydown", handleGlobalShortcut, true);
    window.removeEventListener("focusin", recordFocus, true);
    window.removeEventListener("input", recordInput, true);
    window.removeEventListener("onboarding-complete", leaveOnboarding);
  });
</script>

<TitleBar />
<UpdateBanner />

{#if $appStatus === "loading"}
  <div class="splash">
    <div class="spinner"></div>
    <p>Starting Devo…</p>
  </div>
{:else if $appStatus === "error"}
  <div class="splash error">
    <p>⚠️ {$appError}</p>
  </div>
{:else if showOnboarding && onboardingChecked}
  <OnboardingPage />
{:else}
  <div class="layout">
    <!-- Sidebar -->
    <nav class="sidebar">
      <ul>
        {#each NAV as item}
          <li>
            <button
              class="nav-btn"
              class:active={$currentPage === item.id}
              onclick={() => currentPage.set(item.id)}
            >
              <span class="nav-icon">{item.icon}</span>
              <span class="nav-label">{item.label}</span>
            </button>
          </li>
        {/each}
      </ul>
      <div class="ws-status" class:connected={$wsConnected}>
        {$wsConnected ? "● Live" : "○ Offline"}
      </div>
    </nav>

    <!-- Main content -->
    <main class="content">
      {#if $currentPage === "connections"}
        <ConnectionsPage />
      {:else if $currentPage === "instances"}
        <InstancesPage />
      {:else if $currentPage === "databases"}
        <DatabasesPage />
      {:else if $currentPage === "profiles"}
        <ProfilesPage />
      {:else if $currentPage === "hosts"}
        <HostsPage />
      {:else if $currentPage === "config"}
        <ConfigPage />
      {:else if $currentPage === "logs"}
        <LogsPage />
      {/if}
    </main>
  </div>
{/if}

<style>
  /* ── Theme tokens ────────────────────────────────────────────────────── */
  :global(:root[data-theme="dark"]) {
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
  .splash.error {
    color: var(--danger);
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
    flex: 1;
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
    font-size: 1rem;
  }

  .ws-status {
    padding: 0.6rem 1.2rem;
    font-size: 0.75rem;
    color: #555;
  }
  .ws-status.connected {
    color: var(--success);
  }

  .content {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 2rem;
  }
</style>
