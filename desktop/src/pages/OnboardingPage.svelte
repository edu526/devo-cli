<script lang="ts">
  // First-run wizard. Shown when ~/.devo/config.json has no
  // `onboarded: true`. Three steps:
  //   1. Welcome + preflight (aws + session-manager-plugin + socat)
  //   2. SSO login (uses /profiles/refresh)
  //   3. Add first instance + first database
  // On finish, PATCH /api/v1/config to set onboarded=true.

  import { preflightApi, profilesApi, instancesApi, databasesApi, configApi, ApiError } from "../lib/api";

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

  let step = $state<1 | 2 | 3>(1);
  let preflight = $state<PreflightResult | null>(null);
  let preflightLoading = $state(false);
  let ssoInProgress = $state(false);
  let ssoDone = $state(false);
  let ssoError: string | null = $state(null);

  let newInstance = $state({ name: "", instance_id: "", region: "us-east-1" });
  let newDatabase = $state({
    name: "",
    bastion: "",
    host: "",
    port: 5432,
    region: "us-east-1",
  });

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
      preflight = (raw as unknown) as PreflightResult;
    } catch (e) {
      actionError = String(e);
    } finally {
      preflightLoading = false;
    }
  }

  async function doSso() {
    ssoInProgress = true;
    ssoError = null;
    try {
      await profilesApi.refreshAll();
      // The actual completion is async — the sidecar opens a browser
      // window and the user has to approve. We optimistically advance;
      // the WS event `profile.refreshed` will report success.
      ssoDone = true;
    } catch (e) {
      ssoError = e instanceof ApiError ? String(e.detail) : String(e);
    } finally {
      ssoInProgress = false;
    }
  }

  async function finish() {
    actionError = null;
    finishing = true;
    try {
      // Create instance + database if both names were provided.
      if (newInstance.name && newInstance.instance_id) {
        await instancesApi.create(newInstance.name, {
          instance_id: newInstance.instance_id,
          region: newInstance.region,
        });
      }
      if (newDatabase.name && newDatabase.host && newDatabase.bastion) {
        await databasesApi.create(newDatabase.name, {
          bastion: newDatabase.bastion,
          host: newDatabase.host,
          port: Number(newDatabase.port),
          region: newDatabase.region,
        });
      }
      // Mark the user as onboarded.
      await configApi.patch({ onboarded: true });
      // Tell App.svelte to leave the wizard.
      window.dispatchEvent(new CustomEvent("onboarding-complete"));
    } catch (e) {
      actionError = e instanceof ApiError ? String(e.detail) : String(e);
    } finally {
      finishing = false;
    }
  }

  function skip() {
    window.dispatchEvent(new CustomEvent("onboarding-complete"));
  }

  // Auto-run preflight on mount
  $effect(() => {
    if (step === 1 && preflight === null && !preflightLoading) {
      runPreflight();
    }
  });
</script>

<div class="onboarding">
  <header>
    <h1>Welcome to Devo</h1>
    <p class="muted">Let's get your developer environment set up.</p>
  </header>

  <ol class="steps">
    <li class:active={step === 1} class:done={step > 1}>1 · Preflight</li>
    <li class:active={step === 2} class:done={step > 2}>2 · SSO</li>
    <li class:active={step === 3} class:done={false}>3 · First instance</li>
  </ol>

  {#if actionError}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if step === 1}
    <section>
      <h2>Preflight check</h2>
      <p class="muted">Verifying required CLI tools are installed.</p>
      {#if preflightLoading}
        <p class="muted">Running checks…</p>
      {:else if preflight}
        {@const checks = checksFrom(preflight)}
        {@const allOk = checks.every((c) => c.present)}
        <ul class="checks">
          {#each checks as check (check.name)}
            <li class:fail={!check.present}>
              <span class="icon">{check.present ? "✓" : "✗"}</span>
              <span class="name">{check.name}</span>
              {#if check.detail}<span class="detail muted">{check.detail}</span>{/if}
            </li>
          {/each}
        </ul>
        {#if !allOk}
          <div class="alert-warn">
            One or more tools are missing. Devo will still launch but
            some features will not work until you install them.
          </div>
        {/if}
      {/if}
      <div class="actions">
        <button class="btn-secondary" onclick={runPreflight} disabled={preflightLoading}>
          ↺ Re-check
        </button>
        <button class="btn-primary" onclick={() => (step = 2)}>Next: SSO login →</button>
      </div>
    </section>
  {:else if step === 2}
    <section>
      <h2>AWS SSO login</h2>
      <p class="muted">
        Refresh your SSO profiles. A browser window will open for each
        profile that needs a fresh token.
      </p>
      {#if ssoError}
        <div class="alert-error">{ssoError}</div>
      {/if}
      <div class="actions">
        <button class="btn-secondary" onclick={() => (step = 1)}>← Back</button>
        <button class="btn-primary" onclick={doSso} disabled={ssoInProgress}>
          {ssoInProgress ? "Refreshing…" : ssoDone ? "Refresh again" : "Refresh SSO profiles"}
        </button>
        <button class="btn-primary" onclick={() => (step = 3)}>Next: First instance →</button>
      </div>
    </section>
  {:else if step === 3}
    <section>
      <h2>Add your first bastion and database</h2>
      <p class="muted">You can skip this and configure later from the side panel.</p>

      <div class="form-grid">
        <fieldset>
          <legend>Bastion instance</legend>
          <label>
            Name
            <input bind:value={newInstance.name} placeholder="prod-bastion" />
          </label>
          <label>
            Instance ID
            <input bind:value={newInstance.instance_id} placeholder="i-0abc123def456" />
          </label>
          <label>
            Region
            <input bind:value={newInstance.region} placeholder="us-east-1" />
          </label>
        </fieldset>

        <fieldset>
          <legend>Database (optional)</legend>
          <label>
            Name
            <input bind:value={newDatabase.name} placeholder="mydb" />
          </label>
          <label>
            Bastion
            <input bind:value={newDatabase.bastion} placeholder="prod-bastion" />
          </label>
          <label>
            Host
            <input bind:value={newDatabase.host} placeholder="mydb.cluster.us-east-1.rds.amazonaws.com" />
          </label>
          <label>
            Port
            <input type="number" bind:value={newDatabase.port} />
          </label>
        </fieldset>
      </div>

      <div class="actions">
        <button class="btn-secondary" onclick={() => (step = 2)}>← Back</button>
        <button class="btn-secondary" onclick={skip} disabled={finishing}>Skip for now</button>
        <button class="btn-primary" onclick={finish} disabled={finishing}>
          {finishing ? "Finishing…" : "Finish setup"}
        </button>
      </div>
    </section>
  {/if}
</div>

<style>
  .onboarding {
    max-width: 720px;
    margin: 1rem auto;
    padding: 2rem;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  header h1 {
    font-size: 1.5rem;
    margin-bottom: 0.25rem;
  }

  .steps {
    list-style: none;
    display: flex;
    gap: 1.5rem;
    padding: 0;
    margin: 1.5rem 0;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.75rem;
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  .steps li.active {
    color: var(--accent);
    font-weight: 600;
  }
  .steps li.done {
    color: var(--success);
  }

  section h2 {
    font-size: 1.1rem;
    margin-bottom: 0.4rem;
  }

  .checks {
    list-style: none;
    padding: 0;
    margin: 1rem 0;
  }
  .checks li {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.4rem 0;
    font-size: 0.9rem;
  }
  .checks .icon {
    width: 1.2rem;
    text-align: center;
    color: var(--success);
  }
  .checks li.fail .icon {
    color: var(--danger);
  }
  .checks .name {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.85rem;
  }
  .checks .detail {
    font-size: 0.8rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin: 1rem 0;
  }
  fieldset {
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.75rem;
  }
  legend {
    color: var(--text-secondary);
    font-size: 0.8rem;
    padding: 0 0.4rem;
  }
  fieldset label {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.78rem;
    color: var(--text-secondary);
  }
  fieldset input {
    width: 100%;
    background: var(--bg-surface-2);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-primary);
    padding: 0.35rem 0.5rem;
    font-size: 0.85rem;
    margin-top: 0.2rem;
  }
  fieldset input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 1.25rem;
    justify-content: flex-end;
  }

  .alert-warn {
    background: #2a1a00;
    border: 1px solid var(--warning);
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
    color: var(--warning);
    font-size: 0.85rem;
    margin: 0.75rem 0;
  }
</style>
