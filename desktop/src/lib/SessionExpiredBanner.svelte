<script lang="ts">
  import { onDestroy } from "svelte";
  import { authLost } from "./stores";
  import { canAutoRestart, markAutoRestart, restartApp } from "./restart";

  const COUNTDOWN_SECONDS = 10;

  let remaining = $state<number | null>(null);
  let cancelled = $state(false);
  let restarting = $state(false);
  let timer: ReturnType<typeof setInterval> | null = null;

  function stopTimer() {
    if (timer !== null) clearInterval(timer);
    timer = null;
  }

  async function doRestart() {
    if (restarting) return;
    restarting = true;
    stopTimer();
    try {
      await restartApp();
    } catch {
      // The process normally exits before this resolves; if it fails, let
      // the user retry with the button.
      restarting = false;
    }
  }

  function startCountdown() {
    stopTimer();
    remaining = COUNTDOWN_SECONDS;
    timer = setInterval(() => {
      if (remaining === null) return;
      remaining -= 1;
      if (remaining <= 0) {
        stopTimer();
        markAutoRestart();
        void doRestart();
      }
    }, 1000);
  }

  function cancelAuto() {
    cancelled = true;
    remaining = null;
    stopTimer();
  }

  $effect(() => {
    if ($authLost && timer === null && !cancelled && !restarting) {
      if (canAutoRestart()) startCountdown();
    }
  });

  onDestroy(stopTimer);
</script>

{#if $authLost}
  <div class="banner" role="alert">
    <div class="msg">
      <strong>Devo's session expired.</strong>
      {#if restarting}
        Restarting…
      {:else if remaining !== null}
        It was idle for a long time. Restarting automatically in {remaining}s.
      {:else}
        Restart Devo to continue.
      {/if}
    </div>
    <div class="actions">
      {#if remaining !== null && !restarting}
        <button class="btn ghost" onclick={cancelAuto}>Cancel</button>
      {/if}
      <button class="btn" onclick={doRestart} disabled={restarting}>Restart now</button>
    </div>
  </div>
{/if}

<style>
  .banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.55rem 1rem;
    background: color-mix(in srgb, var(--warning) 16%, var(--bg-surface));
    border-bottom: 1px solid var(--border);
    border-left: 3px solid var(--warning);
    color: var(--text-primary);
    font-size: 0.85rem;
  }
  .msg {
    min-width: 0;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
  }
  .btn {
    padding: 0.3rem 0.8rem;
    border-radius: 6px;
    border: 1px solid var(--accent);
    background: var(--accent);
    color: var(--bg-base);
    font: inherit;
    cursor: pointer;
  }
  .btn.ghost {
    background: transparent;
    color: var(--text-secondary);
    border-color: var(--border);
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
