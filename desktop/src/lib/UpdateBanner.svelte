<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    fetchUpdate,
    installUpdate,
    type UpdateMetadata,
    type ProgressState,
  } from "./update";

  const DISMISS_KEY = "devo.update.dismissedAt";
  const DISMISS_HOURS = 24;
  const POLL_INTERVAL_MS = 6 * 60 * 60 * 1000;

  let available: UpdateMetadata | null = $state(null);
  let progress: ProgressState = $state({
    phase: "idle",
    downloaded: 0,
    total: null,
    error: null,
  });
  let busy = $state(false);

  let pollTimer: ReturnType<typeof setInterval> | null = null;

  async function check() {
    if (isDismissed()) return;
    const meta = await fetchUpdate();
    available = meta;
  }

  function isDismissed(): boolean {
    try {
      const raw = localStorage.getItem(DISMISS_KEY);
      if (!raw) return false;
      const ts = Number(raw);
      return Number.isFinite(ts) && Date.now() - ts < DISMISS_HOURS * 3600 * 1000;
    } catch {
      return false;
    }
  }

  function dismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      // ignore storage errors
    }
    available = null;
  }

  async function startInstall() {
    if (!available) return;
    busy = true;
    const ok = await installUpdate((p) => {
      progress = typeof p === "function" ? p(progress) : p;
    });
    busy = false;
    if (ok && progress.phase === "finished") {
      // Auto-reload so the new version is picked up immediately
      try {
        const { relaunch } = await import("@tauri-apps/plugin-process");
        await relaunch();
      } catch {
        // not running in Tauri; user will reload manually
      }
    }
  }

  onMount(() => {
    check();
    pollTimer = setInterval(check, POLL_INTERVAL_MS);
  });

  onDestroy(() => {
    if (pollTimer !== null) clearInterval(pollTimer);
  });

  const percent = $derived.by(() => {
    if (progress.total === null || progress.total === 0) return 0;
    return Math.min(100, Math.round((progress.downloaded / progress.total) * 100));
  });
</script>

{#if available}
  <div class="banner" role="alert">
    <div class="content">
      <strong>Update available</strong>
      <span class="version">v{available.currentVersion} → v{available.version}</span>
    </div>

    {#if progress.phase === "downloading" || progress.phase === "finished"}
      <div class="progress" aria-label="Download progress">
        <div class="bar" style="width: {percent}%"></div>
        <span class="pct">{percent}%</span>
      </div>
    {:else if progress.phase === "error"}
      <div class="error">Error: {progress.error}</div>
    {/if}

    <div class="actions">
      {#if progress.phase === "downloading"}
        <button class="btn-secondary" disabled>Downloading…</button>
      {:else if progress.phase === "finished"}
        <span class="ok">Installed — relaunching…</span>
      {:else}
        <button class="btn-secondary" onclick={dismiss}>Later</button>
        <button class="btn-primary" onclick={startInstall} disabled={busy}>
          {busy ? "Installing…" : "Download & Install"}
        </button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .banner {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.6rem 1.25rem;
    background: linear-gradient(90deg, rgba(79, 142, 247, 0.12), rgba(167, 139, 250, 0.12));
    border-bottom: 1px solid #1f2937;
    font-size: 0.85rem;
  }

  .content {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex: 1;
  }

  .version {
    color: #94a3b8;
    font-family: "JetBrains Mono", monospace;
  }

  .progress {
    position: relative;
    width: 140px;
    height: 6px;
    background: #1f2937;
    border-radius: 3px;
    overflow: hidden;
  }

  .bar {
    height: 100%;
    background: linear-gradient(90deg, #4f8ef7, #a78bfa);
    transition: width 0.15s;
  }

  .pct {
    position: absolute;
    right: -36px;
    top: -4px;
    color: #94a3b8;
    font-size: 0.72rem;
  }

  .error {
    color: #f87171;
    font-size: 0.78rem;
  }

  .ok {
    color: #4ade80;
  }

  .actions {
    display: flex;
    gap: 0.4rem;
  }

  .btn-primary,
  .btn-secondary {
    padding: 0.3rem 0.7rem;
    border-radius: 4px;
    border: 1px solid transparent;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .btn-primary {
    background: #4f8ef7;
    color: #fff;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: transparent;
    color: #94a3b8;
    border-color: #2a2a2a;
  }
</style>
