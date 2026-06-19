<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { hostsApi, type HostRecord, ApiError } from "../lib/api";
  import { hostsCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import FormField from "../lib/FormField.svelte";
  import { hostSchema, validate, type HostForm, type FieldErrors } from "../lib/forms";

  const initialHosts = (get(hostsCache) ?? []) as HostRecord[];
  let hosts: HostRecord[] = $state(initialHosts);
  let loading = $state(initialHosts.length === 0);
  let refreshing = $state(false);
  let actionError: string | null = $state(null);
  let elevationCommand: string | null = $state(null);
  let adding = $state(false);
  let deleting: Set<string> = $state(new Set());

  let showModal = $state(false);
  let query = $state("");
  let form = $state<HostForm>({ ip: "", hostname: "" });
  let formErrors: FieldErrors<HostForm> = $state({});

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
    elevationCommand = null;
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
    elevationCommand = null;
    adding = true;
    try {
      await hostsApi.add(v.data.ip, v.data.hostname);
      showModal = false;
      resetForm();
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        const detail = e.detail as { command?: string; message?: string };
        elevationCommand = detail?.command ?? null;
        actionError = detail?.message ?? "Elevated privileges required";
      } else {
        actionError = String(e);
      }
    } finally {
      adding = false;
    }
  }

  async function remove(hostname: string) {
    if (!confirm(`Remove "${hostname}" from /etc/hosts?`)) return;
    actionError = null;
    elevationCommand = null;
    deleting = new Set([...deleting, hostname]);
    try {
      await hostsApi.remove(hostname);
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        const detail = e.detail as { command?: string; message?: string };
        elevationCommand = detail?.command ?? null;
        actionError = detail?.message ?? "Elevated privileges required";
      } else {
        actionError = String(e);
      }
    } finally {
      deleting = new Set([...deleting].filter((n) => n !== hostname));
    }
  }

  async function copyCommand() {
    if (elevationCommand) {
      await navigator.clipboard.writeText(elevationCommand);
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
      <SearchInput bind:value={query} placeholder="Filter hosts…" />
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

  {#if elevationCommand}
    <div class="alert-elevation">
      <p>⚠️ {actionError} — run this command in your terminal:</p>
      <div class="elevation-cmd">
        <code>{elevationCommand}</code>
        <button class="btn-sm btn-secondary" onclick={copyCommand}>Copy</button>
      </div>
    </div>
  {:else if actionError}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if hosts.length === 0}
    <div class="empty-state">
      <p>No managed /etc/hosts entries.</p>
      <p class="muted">Add entries to enable hostname-based port forwarding.</p>
    </div>
  {:else if filtered.length === 0}
    <p class="muted">No hosts match "{query}".</p>
  {:else}
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
              <td><code>{h.ip}</code></td>
              <td><code>{h.hostname}</code></td>
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

      {#if actionError && !elevationCommand}
        <div class="alert-error">{actionError}</div>
      {/if}

      <FormField label="IP Address" required error={formErrors.ip} hint="IPv4 address, e.g. 127.0.0.1">
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

<style>
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
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
</style>
