<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { updateAvailable, installUpdate, getAppVersion } from "./update";

  let maximized = $state(false);
  let unlisten: (() => void) | null = null;
  let updateInstalling = $state(false);
  let updateError: string | null = $state(null);
  let appVersion: string | null = $state(null);

  async function getWin() {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    return getCurrentWindow();
  }

  async function startDrag(e: MouseEvent) {
    if (e.button !== 0) return; // left button only
    try {
      (await getWin()).startDragging();
    } catch {
      /* browser dev mode */
    }
  }

  async function minimize() {
    (await getWin()).minimize();
  }

  async function close() {
    (await getWin()).close();
  }

  async function toggleMaximize() {
    const win = await getWin();
    await win.toggleMaximize();
    maximized = await win.isMaximized();
  }

  async function handleUpdateClick() {
    if (!$updateAvailable) return;
    updateInstalling = true;
    updateError = null;
    try {
      await installUpdate(() => {});
    } catch (e) {
      updateError = String(e);
    } finally {
      updateInstalling = false;
    }
  }

  onMount(async () => {
    try {
      const win = await getWin();
      maximized = await win.isMaximized();
      const { listen } = await import("@tauri-apps/api/event");
      unlisten = await listen("tauri://resize", async () => {
        maximized = await win.isMaximized();
      });
    } catch {
      // not running inside Tauri (browser dev mode)
    }
    appVersion = await getAppVersion();
  });

  onDestroy(() => unlisten?.());
</script>

<div class="titlebar" role="banner">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="tb-brand" onmousedown={startDrag}>
    <svg class="tb-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M4 6C4 4.895 4.895 4 6 4H10C13.314 4 16 6.686 16 10V14C16 17.314 13.314 20 10 20H6C4.895 20 4 19.105 4 18V6Z"
        fill="url(#grad)"
      />
      <rect x="14" y="9" width="6" height="2.5" rx="1.25" fill="url(#grad2)" />
      <rect x="14" y="12.5" width="4" height="2.5" rx="1.25" fill="url(#grad2)" opacity="0.6" />
      <defs>
        <linearGradient id="grad" x1="4" y1="4" x2="16" y2="20" gradientUnits="userSpaceOnUse">
          <stop stop-color="#4f8ef7" />
          <stop offset="1" stop-color="#a78bfa" />
        </linearGradient>
        <linearGradient id="grad2" x1="14" y1="9" x2="20" y2="15" gradientUnits="userSpaceOnUse">
          <stop stop-color="#4f8ef7" />
          <stop offset="1" stop-color="#a78bfa" />
        </linearGradient>
      </defs>
    </svg>
    <span class="tb-name">Devo</span>
    {#if appVersion}
      <span class="tb-version" title="App version">v{appVersion}</span>
    {/if}
    {#if $updateAvailable}
      <button
        class="update-badge"
        onclick={handleUpdateClick}
        disabled={updateInstalling}
        title={updateError ?? "Update available — click to install"}
      >
        {updateInstalling ? "…" : "↑ update"}
      </button>
    {/if}
  </div>

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="tb-drag" onmousedown={startDrag}></div>

  <div class="tb-controls">
    <button class="ctrl-btn" onclick={minimize} title="Minimize" aria-label="Minimize">
      <svg viewBox="0 0 10 1" fill="currentColor"><rect width="10" height="1" /></svg>
    </button>
    <button
      class="ctrl-btn"
      onclick={toggleMaximize}
      title={maximized ? "Restore" : "Maximize"}
      aria-label={maximized ? "Restore" : "Maximize"}
    >
      {#if maximized}
        <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1">
          <rect x="2" y="0" width="8" height="8" />
          <polyline points="0,2 0,10 8,10" />
        </svg>
      {:else}
        <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1">
          <rect x="0" y="0" width="10" height="10" />
        </svg>
      {/if}
    </button>
    <button class="ctrl-btn ctrl-close" onclick={close} title="Close" aria-label="Close">
      <svg viewBox="0 0 10 10" stroke="currentColor" stroke-width="1.2">
        <line x1="0" y1="0" x2="10" y2="10" />
        <line x1="10" y1="0" x2="0" y2="10" />
      </svg>
    </button>
  </div>
</div>

<style>
  .titlebar {
    height: 36px;
    background: #0d0d0d;
    border-bottom: 1px solid #1a1a1a;
    display: flex;
    align-items: center;
    flex-shrink: 0;
    user-select: none;
    -webkit-user-select: none;
  }

  .tb-brand {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    padding: 0 0.75rem 0 0.9rem;
    width: 230px;
    flex-shrink: 0;
    cursor: grab;
  }

  .tb-icon {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    align-self: center;
  }

  .tb-name {
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: -0.3px;
    background: linear-gradient(135deg, #4f8ef7, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .tb-version {
    font-size: 0.7rem;
    color: #666;
    font-family: "JetBrains Mono", monospace;
    font-weight: 500;
    white-space: nowrap;
  }

  .tb-drag {
    flex: 1;
    height: 100%;
    cursor: grab;
  }

  .tb-controls {
    display: flex;
    height: 100%;
  }

  .ctrl-btn {
    width: 46px;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    color: #666;
    cursor: pointer;
    transition:
      background 0.1s,
      color 0.1s;
  }

  .ctrl-btn svg {
    width: 10px;
    height: 10px;
  }

  .ctrl-btn:hover {
    background: #2a2a2a;
    color: #e0e0e0;
  }

  .ctrl-close:hover {
    background: #c0392b;
    color: #fff;
  }

  .update-badge {
    background: #fbbf24;
    color: #1a1a1a;
    border: none;
    border-radius: 10px;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    cursor: pointer;
    margin-left: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .update-badge:hover {
    background: #fcd34d;
  }
  .update-badge:disabled {
    opacity: 0.6;
    cursor: progress;
  }
</style>
