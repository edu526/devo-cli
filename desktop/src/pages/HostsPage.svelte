<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { invoke } from "@tauri-apps/api/core";
  import {
    hostsApi,
    type HostRecord,
    type HostSetupEntry,
    type ElevationHint,
    ApiError,
  } from "../lib/api";
  import { hostsCache } from "../lib/page-stores";
  import { viewModes } from "../lib/stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import ViewToggle from "../lib/ViewToggle.svelte";
  import FormField from "../lib/FormField.svelte";
  import { hostSchema, validate, type HostForm, type FieldErrors } from "../lib/forms";
  
  const viewMode = viewModes.hosts;

  const initialHosts = (get(hostsCache) ?? []) as HostRecord[];
  // ponytail: Windows is the only platform with a different hosts path. All
  // Unix-like (Linux/macOS) share /etc/hosts.
  const isWindows =
    typeof navigator !== "undefined" && /Windows/i.test(navigator.userAgent);
  const hostsPath = isWindows ? "C:\\Windows\\System32\\drivers\\etc\\hosts" : "/etc/hosts";
  const adminAction = isWindows ? "admin approval (UAC prompt)" : "admin password (sudo prompt)";
  let hosts: HostRecord[] = $state(initialHosts);
  let loading = $state(initialHosts.length === 0);
  let refreshing = $state(false);
  let actionError: string | null = $state(null);
  let elevationHint: ElevationHint | null = $state(null);
  let adding = $state(false);
  let deleting: Set<string> = $state(new Set());

  let showModal = $state(false);
  let query = $state("");
  let form = $state<HostForm>({ ip: "", hostname: "" });
  let formErrors: FieldErrors<HostForm> = $state({});
  let settingUp = $state(false);
  let setupResult: HostSetupEntry[] | null = $state(null);
  // ponytail: custom modal for the remove confirmation — window.confirm() renders
  // as a native WebView dialog ("localhost:5173 dice…") and breaks the visual.
  let confirmRemove: string | null = $state(null);

  const filtered = $derived(
    query.trim()
      ? hosts.filter(
          (h) =>
            h.ip.toLowerCase().includes(query.toLowerCase()) ||
            h.hostname.toLowerCase().includes(query.toLowerCase()),
        )
      : hosts,
  );

  function resetForm() {
    form = { ip: "", hostname: "" };
    formErrors = {};
    actionError = null;
    elevationHint = null;
  }

  function argsFor(hint: ElevationHint): string[] {
    const a = hint.action;
    const p = hint.params as Record<string, string | string[] | undefined>;
    if (a === "hosts-add") {
      // Manual add: no db name, use the bypass-config subcommand.
      return ["ssm", "hosts", "add-manual", String(p.ip ?? ""), String(p.hostname ?? "")];
    }
    if (a === "hosts-remove") {
      // If the host came from a configured db, pass the db name (the CLI
      // resolves <name> against ~/.devo/config.json, not /etc/hosts).
      // Otherwise fall back to the bypass-config remove by hostname.
      const dbName = String(p.db_name ?? "");
      if (dbName) {
        return ["ssm", "hosts", "remove", dbName];
      }
      return ["ssm", "hosts", "remove-manual", String(p.hostname ?? "")];
    }
    if (a === "hosts-setup") {
      const dbs = Array.isArray(p.db_names) ? p.db_names : [];
      return dbs.length > 0 ? ["ssm", "hosts", "setup", "--db-name", ...dbs] : ["ssm", "hosts", "setup"];
    }
    return [];
  }

  // ponytail: trigger the UAC prompt via Tauri, then refresh the list.
  // The elevated devo already performed the mutation, so we MUST NOT
  // re-call the sidecar mutating endpoint — the sidecar has no admin
  // rights and would re-fail with 401 (and in the old code, the retry
  // also re-triggered the confirm() in a loop). `load()` is a read
  // and works fine non-elevated.
  async function elevateAndRefresh(hint: ElevationHint): Promise<void> {
    if (!hint.action) {
      elevationHint = hint;
      return;
    }
    actionError = null;
    elevationHint = null;
    try {
      const exit = await invoke<number>("run_elevated", { args: argsFor(hint) });
      if (exit === 0) {
        await load();
      } else {
        actionError = `Elevated command failed (exit ${exit})`;
      }
    } catch (e) {
      const msg = String(e);
      if (msg.toLowerCase().includes("cancel") || msg.toLowerCase().includes("access")) {
        actionError = "Elevation cancelled. Try again or right-click Devo and 'Run as administrator'.";
      } else {
        actionError = msg;
      }
    }
  }

  async function load() {
    refreshing = true;
    try {
      const data = await hostsApi.list();
      hosts = data;
      hostsCache.set(data);
    } catch (e) {
      actionError = String(e);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function add() {
    formErrors = {};
    const v = validate(hostSchema, form);
    if (!v.success) {
      formErrors = v.errors;
      return;
    }
    actionError = null;
    elevationHint = null;
    adding = true;
    try {
      await hostsApi.add(v.data.ip, v.data.hostname);
      showModal = false;
      resetForm();
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        const detail = e.detail as Partial<ElevationHint>;
        const hint: ElevationHint = {
          message: detail.message ?? "Elevated privileges required",
          command: detail.command ?? "",
          action: detail.action ?? "",
          params: (detail.params ?? {}) as Record<string, unknown>,
        };
        await elevateAndRefresh(hint);
      } else {
        actionError = String(e);
      }
    } finally {
      adding = false;
    }
  }

  async function doRemove(hostname: string) {
    actionError = null;
    elevationHint = null;
    deleting = new Set([...deleting, hostname]);
    try {
      await hostsApi.remove(hostname);
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        const detail = e.detail as Partial<ElevationHint>;
        const hint: ElevationHint = {
          message: detail.message ?? "Elevated privileges required",
          command: detail.command ?? "",
          action: detail.action ?? "",
          params: (detail.params ?? {}) as Record<string, unknown>,
        };
        await elevateAndRefresh(hint);
      } else {
        actionError = String(e);
      }
    } finally {
      deleting = new Set([...deleting].filter((n) => n !== hostname));
    }
  }

  async function remove(hostname: string) {
    confirmRemove = hostname;
  }

  async function cancelConfirmRemove() {
    confirmRemove = null;
  }

  async function confirmConfirmRemove() {
    const hostname = confirmRemove;
    confirmRemove = null;
    if (hostname) await doRemove(hostname);
  }

  async function copyCommand() {
    if (elevationHint?.command) {
      await navigator.clipboard.writeText(elevationHint.command);
    }
  }

  async function runSetup() {
    actionError = null;
    elevationHint = null;
    setupResult = null;
    settingUp = true;
    try {
      const result = await hostsApi.setup();
      if (result.failed.length > 0) {
        const msgs = result.failed.map((f) => `${f.name}: ${f.error}`).join("\n");
        actionError = `Setup partially failed:\n${msgs}`;
      }
      if (result.succeeded.length > 0) {
        setupResult = result.succeeded;
      }
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        const detail = e.detail as Partial<ElevationHint>;
        const hint: ElevationHint = {
          message: detail.message ?? "Elevated privileges required",
          command: detail.command ?? "",
          action: detail.action ?? "",
          params: (detail.params ?? {}) as Record<string, unknown>,
        };
        await elevateAndRefresh(hint);
      } else {
        actionError = String(e);
      }
    } finally {
      settingUp = false;
    }
  }

  function onModalKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") showModal = false;
    e.stopPropagation();
  }

  onMount(load);
</script>

<div class="page">
  <div class="page-header">
    <h1>
      Hosts {#if refreshing && !loading}<span class="refreshing-dot"></span>{/if}
    </h1>
    <div class="header-actions">
      <ViewToggle page="hosts" />
      <SearchInput bind:value={query} placeholder="Filter hosts…" />
      <button class="btn-secondary" onclick={runSetup} disabled={settingUp}>
        {#if settingUp}<span class="spinner-sm"></span>{/if}
        Auto Setup
      </button>
      <button
        class="btn-primary"
        onclick={() => {
          resetForm();
          showModal = true;
        }}
      >
        Add Host
      </button>
    </div>
  </div>

  {#if elevationHint && elevationHint.action}
    <div class="alert-elevation">
      <p>⚠️ {elevationHint.message}</p>
      <p class="muted">Devo tried to elevate automatically but the action hint was missing. Run this in an admin terminal:</p>
      <div class="elevation-cmd">
        <code>{elevationHint.command}</code>
        <button class="btn-sm btn-secondary" onclick={copyCommand}>Copy</button>
      </div>
    </div>
  {:else if elevationHint}
    <div class="alert-elevation">
      <p>⚠️ {elevationHint.message} — run this command in your terminal:</p>
      <div class="elevation-cmd">
        <code>{elevationHint.command}</code>
        <button class="btn-sm btn-secondary" onclick={copyCommand}>Copy</button>
      </div>
    </div>
  {:else if actionError}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if setupResult && setupResult.length > 0}
    <div class="alert-success">
      <p>
        ✓ Setup complete — {setupResult.length} host{setupResult.length > 1 ? "s" : ""} configured:
      </p>
      <ul>
        {#each setupResult as r (r.name)}
          <li>
            <code>{r.host}</code> → <code>{r.ip}</code>:<code>{r.local_port}</code>
            {#if r.port_reassigned}<span class="muted"> (port reassigned)</span>{/if}
          </li>
        {/each}
      </ul>
      <button class="btn-sm btn-secondary" onclick={() => (setupResult = null)}>Dismiss</button>
    </div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if hosts.length === 0}
    <div class="empty-state">
      <p>No managed {hostsPath} entries.</p>
      <p class="muted">Add entries to enable hostname-based port forwarding.</p>
    </div>
  {:else if filtered.length === 0}
    <p class="muted">No hosts match "{query}".</p>
  {:else}
    {#if $viewMode === 'table'}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>IP</th>
              <th>Hostname</th>
              <th class="actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each filtered as h (h.hostname)}
              <tr>
                <td class="ip-cell truncate"><code>{h.ip}</code></td>
                <td class="hostname-cell truncate"><code>{h.hostname}</code></td>
                <td class="actions-cell">
                  <div class="actions-wrap">
                    <button
                      class="btn-sm btn-danger"
                      onclick={() => remove(h.hostname)}
                      disabled={deleting.has(h.hostname)}
                    >
                      {#if deleting.has(h.hostname)}
                        <span class="spinner-sm"></span> Removing…
                      {:else}
                        Remove
                      {/if}
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <div class="list-cards">
        {#each filtered as h (h.hostname)}
          <div class="list-card">
            <div class="lc-main">
              <div class="lc-header">
                <span class="lc-title"><code>{h.ip}</code></span>
              </div>
              <div class="lc-meta">
                <span class="lc-meta-item">
                  <span class="muted">Hostname:</span> <code>{h.hostname}</code>
                </span>
              </div>
            </div>
            <div class="lc-actions">
              <button
                class="btn-danger"
                onclick={() => remove(h.hostname)}
                disabled={deleting.has(h.hostname)}
              >
                Remove
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

{#if showModal}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={() => (showModal = false)}
    onkeydown={() => (showModal = false)}
  >
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={onModalKeydown}
    >
      <h2>Add Host Entry</h2>

      {#if actionError && !elevationHint}
        <div class="alert-error">{actionError}</div>
      {/if}

      <FormField
        label="IP Address"
        required
        error={formErrors.ip}
        hint="IPv4 address, e.g. 127.0.0.1"
      >
        <input bind:value={form.ip} placeholder="127.0.0.1" />
      </FormField>
      <FormField label="Hostname" required error={formErrors.hostname}>
        <input bind:value={form.hostname} placeholder="mydb.internal" />
      </FormField>

      <div class="modal-actions">
        <button
          class="btn-secondary"
          onclick={() => {
            showModal = false;
          }}
          disabled={adding}>Cancel</button
        >
        <button class="btn-primary" onclick={add} disabled={adding}>
          {#if adding}
            <span class="spinner-sm"></span> Adding…
          {:else}
            Add
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if confirmRemove}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={cancelConfirmRemove}
    onkeydown={cancelConfirmRemove}
  >
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-remove-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => {
        if (e.key === "Escape") cancelConfirmRemove();
        e.stopPropagation();
      }}
    >
      <div class="confirm-header">
        <span class="confirm-icon" aria-hidden="true">⚠️</span>
        <h2 id="confirm-remove-title">Remove host entry</h2>
      </div>
      <p class="confirm-lead">This will remove the following entry:</p>
      <div class="confirm-host">
        <code>{confirmRemove}</code>
      </div>
      <p class="confirm-path muted">from <code>{hostsPath}</code></p>
      <div class="confirm-notice">
        <span class="confirm-lock" aria-hidden="true">🔐</span>
        <span>This action requires {adminAction}.</span>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick={cancelConfirmRemove}>Cancel</button>
        <button class="btn-danger" onclick={confirmConfirmRemove}>Remove</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .ip-cell {
    max-width: 140px;
  }
  .hostname-cell {
    max-width: 200px;
  }

  /* Remove-confirmation modal */
  .confirm-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.1rem;
  }
  .confirm-icon {
    font-size: 1.4rem;
    line-height: 1;
  }
  .confirm-lead {
    color: #b0b0b0;
    font-size: 0.88rem;
    margin: 0;
  }
  .confirm-host {
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 0.6rem 0.85rem;
    word-break: break-all;
    overflow-wrap: anywhere;
  }
  .confirm-host code {
    color: #f87171;
    font-size: 0.85rem;
  }
  .confirm-path {
    margin: 0;
    font-size: 0.8rem;
  }
  .confirm-notice {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    background: #2a1a00;
    border: 1px solid #5a3a10;
    border-radius: 6px;
    padding: 0.55rem 0.8rem;
    color: #fbbf24;
    font-size: 0.82rem;
  }
  .confirm-lock {
    font-size: 1rem;
    line-height: 1;
  }

  .alert-elevation {
    background: #2a1a00;
    border: 1px solid #f59e0b;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    color: #fbbf24;
    font-size: 0.85rem;
  }

  .elevation-cmd {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.5rem;
    background: #1a1a1a;
    border-radius: 4px;
    padding: 0.5rem 0.75rem;
  }

  .elevation-cmd code {
    flex: 1;
    word-break: break-all;
    font-size: 0.8rem;
    color: #e0e0e0;
  }

  .alert-success {
    background: #0f2a1a;
    border: 1px solid #22c55e;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    color: #86efac;
    font-size: 0.85rem;
  }

  .alert-success ul {
    margin: 0.5rem 0;
    padding-left: 1.25rem;
    list-style: none;
  }

  .alert-success li {
    margin: 0.25rem 0;
    font-size: 0.8rem;
  }

  .alert-success .muted {
    color: #6b7280;
  }

  /* List Cards */
  .list-cards {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .list-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    transition: all 0.2s ease;
  }
  
  .list-card:hover {
    background: var(--bg-surface-2);
    border-color: var(--border-strong);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
  
  .lc-main {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    overflow: hidden;
  }
  
  .lc-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  
  .lc-title {
    font-weight: 600;
    font-size: 1.05rem;
    color: var(--text-primary);
  }
  
  .lc-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    flex-wrap: wrap;
    color: var(--text-secondary);
  }
  
  .lc-meta-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }
  
  .lc-meta-sep {
    color: var(--border-strong);
  }
  
  .lc-actions {
    flex-shrink: 0;
    margin-left: 1rem;
    display: flex;
    gap: 0.5rem;
  }
</style>
