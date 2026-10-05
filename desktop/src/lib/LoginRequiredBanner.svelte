<script lang="ts">
  import { loginActive, loginError, loginInProgress, loginNeeded } from "./stores";
  import { startLogin } from "./login-flow";

  const listed = (items: string[]) =>
    items.length > 3 ? `${items.slice(0, 3).join(", ")} and ${items.length - 3} more` : items.join(", ");

  const active = $derived([...$loginActive]);
  // Sessions waiting for the user, minus the ones whose login is already open.
  const pendingSessions = $derived(Object.keys($loginNeeded).filter((s) => !$loginActive.has(s)));
  const pendingLabel = $derived(
    listed(
      pendingSessions.flatMap((s) => ($loginNeeded[s]?.length ? $loginNeeded[s] : [s])),
    ),
  );
</script>

{#if active.length > 0}
  <div class="banner" role="status">
    <div class="msg">
      <strong>Signing in to AWS.</strong>
      Finish the login for {listed(active)} in your browser…
    </div>
  </div>
{:else if pendingSessions.length > 0}
  <div class="banner" role="status">
    <div class="msg">
      <strong>AWS login required.</strong>
      {#if $loginInProgress}
        Finish the login in your browser…
      {:else}
        {pendingLabel} can't be renewed automatically.
      {/if}
      {#if $loginError}
        <span class="error">{$loginError}</span>
      {/if}
    </div>
    <button class="btn" onclick={() => startLogin()} disabled={$loginInProgress}>
      {$loginInProgress ? "Waiting…" : "Log in"}
    </button>
  </div>
{/if}

<style>
  .banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.55rem 1rem;
    background: color-mix(in srgb, var(--accent) 12%, var(--bg-surface));
    border-bottom: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    color: var(--text-primary);
    font-size: 0.85rem;
  }
  .msg {
    min-width: 0;
  }
  .error {
    color: var(--danger);
    margin-left: 0.5rem;
  }
  .btn {
    flex-shrink: 0;
    padding: 0.3rem 0.8rem;
    border-radius: 6px;
    border: 1px solid var(--accent);
    background: var(--accent);
    color: var(--bg-base);
    font: inherit;
    cursor: pointer;
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
