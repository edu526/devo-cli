<script lang="ts">
  // First-run wizard. Shown when ~/.devo/config.json has no
  // `onboarded: true`.
  // Runs preflight checks (aws + session-manager-plugin + socat).
  // On finish, PATCH /api/v1/config to set onboarded=true.

  import { preflightApi, configApi, ApiError } from "../lib/api";
  import { fade, slide } from "svelte/transition";
  import { quintOut } from "svelte/easing";
  import { Check, X, RefreshCw, ArrowRight } from "@lucide/svelte";

  interface PreflightResult {
    aws_cli?: { ok: boolean; version?: string | null };
    session_manager_plugin?: { ok: boolean; install_url?: string };
    socat?: { ok: boolean; version?: string | null };
  }

  interface PreflightCheck {
    name: string;
    present: boolean;
    detail?: string;
  }

  let preflight = $state<PreflightResult | null>(null);
  let preflightLoading = $state(false);
  let actionError: string | null = $state(null);
  let finishing = $state(false);

  function checksFrom(p: PreflightResult | null): PreflightCheck[] {
    if (!p) return [];
    const out: PreflightCheck[] = [];
    if (p.aws_cli) {
      out.push({
        name: "aws",
        present: p.aws_cli.ok,
        detail: p.aws_cli.version ?? undefined,
      });
    }
    if (p.session_manager_plugin) {
      out.push({
        name: "session-manager-plugin",
        present: p.session_manager_plugin.ok,
        detail: p.session_manager_plugin.ok ? "installed" : "missing",
      });
    }
    if (p.socat) {
      out.push({
        name: "socat",
        present: p.socat.ok,
        detail: p.socat.version ?? undefined,
      });
    }
    return out;
  }

  async function runPreflight() {
    preflightLoading = true;
    try {
      const raw = await preflightApi.run();
      // Backend returns the dict directly (no wrapping).
      preflight = raw as unknown as PreflightResult;
    } catch (e) {
      actionError = String(e);
    } finally {
      preflightLoading = false;
    }
  }

  async function finish() {
    actionError = null;
    finishing = true;
    try {
      // Mark the user as onboarded.
      await configApi.patch({ onboarded: true });
      // Wait a tiny bit for UI update if needed, but the CustomEvent triggers the App re-render
      window.dispatchEvent(new CustomEvent("onboarding-complete"));
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      finishing = false;
    }
  }

  // Auto-run preflight on mount
  $effect(() => {
    if (preflight === null && !preflightLoading) {
      runPreflight();
    }
  });
</script>

<div class="onboarding-wrapper" out:fade={{ duration: 700, easing: quintOut }}>
  <div class="onboarding-card" in:fade={{ duration: 400 }}>
    <header>
      <img class="ob-logo" src="/app-icon.png" alt="Devo" />
      <h1>Welcome to Devo</h1>
      <p class="muted">Let's get your developer environment set up.</p>
    </header>

    {#if actionError}
      <div class="alert-error" in:slide>{actionError}</div>
    {/if}

    <div class="step-content">
      <section in:fade={{ duration: 300, delay: 100 }}>
        <div class="section-header">
          <h2>Preflight check</h2>
          <p class="muted">Verifying required CLI tools are installed.</p>
        </div>
        <ul class="checks">
          {#if preflightLoading}
            {#each ["aws", "session-manager-plugin", "socat"] as tool}
              <li class="check-item loading">
                <div class="check-icon spinner-container"><div class="spinner-small"></div></div>
                <div class="check-info">
                  <span class="name">{tool}</span>
                  <span class="detail muted">Verifying installation...</span>
                </div>
              </li>
            {/each}
          {:else if preflight}
            {@const checks = checksFrom(preflight)}
            {#each checks as check (check.name)}
              <li class="check-item" class:fail={!check.present}>
                <div class="check-icon" style="display:inline-flex">
                  {#if check.present}<Check size={18} strokeWidth={3} />{:else}<X
                      size={18}
                      strokeWidth={3}
                    />{/if}
                </div>
                <div class="check-info">
                  <span class="name">{check.name}</span>
                  {#if check.detail}<span class="detail muted">{check.detail}</span>{/if}
                </div>
              </li>
            {/each}
          {/if}
        </ul>

        {#if preflight && !checksFrom(preflight).every((c) => c.present)}
          <div class="alert-warn" in:slide>
            <span class="warn-icon">!</span>
            <p>
              One or more tools are missing. Devo will still launch but some features will not work
              until you install them.
            </p>
          </div>
        {/if}
        <div class="actions">
          <button
            class="btn-secondary"
            style="display:inline-flex; align-items:center; gap:0.4rem;"
            onclick={runPreflight}
            disabled={preflightLoading}
          >
            <RefreshCw size={16} /> Re-check
          </button>
          <button
            class="btn-primary"
            style="display:inline-flex; align-items:center; gap:0.4rem;"
            onclick={finish}
            disabled={finishing || preflightLoading}
          >
            {#if finishing}Starting...{:else}Start using Devo <ArrowRight size={16} />{/if}
          </button>
        </div>
      </section>
    </div>
  </div>
</div>

<style>
  .onboarding-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 36px;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 50;
    background: radial-gradient(
      circle at 50% -20%,
      color-mix(in srgb, var(--accent) 15%, transparent),
      transparent 60%
    );
    background-color: var(--bg-base);
  }

  .onboarding-card {
    width: 100%;
    max-width: 580px;
    background: color-mix(in srgb, var(--bg-elevated) 40%, transparent);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    border-radius: 16px;
    padding: 2.5rem;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
  }

  header {
    text-align: center;
    margin-bottom: 2rem;
  }

  .ob-logo {
    width: 54px;
    height: 54px;
    margin-bottom: 1rem;
    border-radius: 14px;
    box-shadow: 0 4px 15px color-mix(in srgb, var(--accent) 20%, transparent);
  }

  header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
    color: var(--accent);
    letter-spacing: -0.5px;
  }

  header p {
    font-size: 0.95rem;
    margin: 0;
  }

  .step-content {
    display: flex;
    flex-direction: column;
  }

  section {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .section-header {
    margin-bottom: 1.5rem;
  }

  .section-header h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0 0 0.25rem 0;
    color: var(--text-primary);
  }

  .checks {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .check-item {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 1rem;
    background: color-mix(in srgb, var(--bg-base) 20%, transparent);
    border: 1px solid color-mix(in srgb, var(--text-primary) 5%, transparent);
    border-radius: 8px;
    transition: border-color 0.2s;
  }

  .check-item:hover {
    border-color: color-mix(in srgb, var(--text-primary) 10%, transparent);
  }

  .check-icon {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--success) 12%, transparent);
    color: var(--success);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    font-weight: bold;
    flex-shrink: 0;
  }

  .check-item.fail .check-icon {
    background: color-mix(in srgb, var(--danger) 12%, transparent);
    color: var(--danger);
  }

  .check-info {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .check-info .name {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary);
  }

  .check-info .detail {
    font-size: 0.8rem;
  }

  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid color-mix(in srgb, var(--accent) 20%, transparent);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .check-item.loading .check-icon {
    background: color-mix(in srgb, var(--text-primary) 5%, transparent);
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .alert-warn {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    background: color-mix(in srgb, var(--warning) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--warning) 25%, transparent);
    border-radius: 8px;
    padding: 1rem;
    margin-top: 1.5rem;
  }

  .warn-icon {
    width: 20px;
    height: 20px;
    background: var(--warning);
    color: #000;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 0.8rem;
    flex-shrink: 0;
  }

  .alert-warn p {
    margin: 0;
    color: var(--warning);
    font-size: 0.85rem;
    line-height: 1.4;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.5rem;
    justify-content: flex-end;
  }

  .btn-primary {
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 0.5rem 1.25rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: color-mix(in srgb, var(--text-primary) 5%, transparent);
    color: var(--text-primary);
    border: 1px solid color-mix(in srgb, var(--text-primary) 10%, transparent);
    border-radius: 6px;
    padding: 0.5rem 1.25rem;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-secondary:hover:not(:disabled) {
    background: color-mix(in srgb, var(--text-primary) 10%, transparent);
    border-color: color-mix(in srgb, var(--text-primary) 20%, transparent);
  }
</style>
