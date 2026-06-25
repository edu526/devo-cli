<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { databasesApi, type DatabaseRecord, type DatabaseIn, ApiError } from "../lib/api";
  import { databasesCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import FormField from "../lib/FormField.svelte";
  import { databaseSchema, validate, type DatabaseForm, type FieldErrors } from "../lib/forms";

  const initialDatabases = Object.entries(get(databasesCache) ?? {}) as [string, DatabaseRecord][];
  let databases: [string, DatabaseRecord][] = $state(initialDatabases);
  let loading = $state(initialDatabases.length === 0);
  let refreshing = $state(false);
  let actionError: string | null = $state(null);
  let saving = $state(false);
  let deleting: Set<string> = $state(new Set());
  let query = $state("");

  let showModal = $state(false);
  let editingName: string | null = $state(null);
  let form = $state<DatabaseForm>({
    name: "",
    bastion: "",
    host: "",
    port: 5432,
    region: "us-east-1",
    profile: "",
    local_port: undefined,
    local_address: "127.0.0.1",
  });
  let formErrors: FieldErrors<DatabaseForm> = $state({});

  const filtered = $derived(
    query.trim()
      ? databases.filter(
          ([name, rec]) =>
            name.toLowerCase().includes(query.toLowerCase()) ||
            rec.bastion.toLowerCase().includes(query.toLowerCase()) ||
            rec.host.toLowerCase().includes(query.toLowerCase()) ||
            rec.region.toLowerCase().includes(query.toLowerCase()),
        )
      : databases,
  );

  async function load() {
    refreshing = true;
    try {
      const data = await databasesApi.list();
      databases = Object.entries(data);
      databasesCache.set(data);
    } catch (e) {
      actionError = String(e);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function openCreate() {
    editingName = null;
    form = {
      name: "",
      bastion: "",
      host: "",
      port: 5432,
      region: "us-east-1",
      profile: "",
      local_port: undefined,
      local_address: "127.0.0.1",
    };
    formErrors = {};
    actionError = null;
    showModal = true;
  }

  function openEdit(name: string, rec: DatabaseRecord) {
    editingName = name;
    form = { name, ...rec, profile: rec.profile ?? "", local_port: rec.local_port };
    formErrors = {};
    actionError = null;
    showModal = true;
  }

  async function save() {
    formErrors = {};
    const v = validate(databaseSchema, form);
    if (!v.success) {
      formErrors = v.errors;
      return;
    }
    actionError = null;
    saving = true;
    const body: DatabaseIn = {
      bastion: v.data.bastion,
      host: v.data.host,
      port: v.data.port,
      region: v.data.region,
      profile: v.data.profile || undefined,
      local_port: v.data.local_port,
      local_address: v.data.local_address || "127.0.0.1",
    };
    try {
      if (editingName) {
        await databasesApi.update(editingName, body);
      } else {
        await databasesApi.create(v.data.name, body);
      }
      showModal = false;
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  async function remove(name: string) {
    if (!confirm(`Delete database "${name}"?`)) return;
    actionError = null;
    deleting = new Set([...deleting, name]);
    try {
      await databasesApi.delete(name);
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      deleting = new Set([...deleting].filter((n) => n !== name));
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
      Databases {#if refreshing && !loading}<span class="refreshing-dot"></span>{/if}
    </h1>
    <div class="header-actions">
      <SearchInput bind:value={query} placeholder="Filter databases…" />
      <button class="btn-primary" onclick={openCreate}>New Database</button>
    </div>
  </div>

  {#if actionError}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if databases.length === 0}
    <div class="empty-state">
      <p>No databases configured.</p>
      <p class="muted">Add a database to create an SSM port-forwarding tunnel.</p>
    </div>
  {:else if filtered.length === 0}
    <p class="muted">No databases match "{query}".</p>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Bastion</th>
            <th>Host</th>
            <th>Port</th>
            <th>Local Port</th>
            <th>Region</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as [name, rec] (name)}
            <tr>
              <td class="name">{name}</td>
              <td>{rec.bastion}</td>
              <td class="host-cell truncate"><code>{rec.host}</code></td>
              <td>{rec.port}</td>
              <td>{rec.local_port ?? "auto"}</td>
              <td>{rec.region}</td>
              <td class="actions-cell">
                <div class="actions-wrap">
                  <button class="btn-sm btn-secondary" onclick={() => openEdit(name, rec)}
                    >Edit</button
                  >
                  <button
                    class="btn-sm btn-danger"
                    onclick={() => remove(name)}
                    disabled={deleting.has(name)}
                  >
                    {#if deleting.has(name)}
                      <span class="spinner-sm"></span> Deleting…
                    {:else}
                      Delete
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
      <h2>{editingName ? "Edit Database" : "New Database"}</h2>

      {#if actionError}
        <div class="alert-error">{actionError}</div>
      {/if}

      <div class="form-grid">
        <FormField label="Name" required error={formErrors.name}>
          <input bind:value={form.name} disabled={!!editingName} placeholder="my-db" />
        </FormField>
        <FormField label="Bastion instance" required error={formErrors.bastion}>
          <input bind:value={form.bastion} placeholder="prod-bastion" />
        </FormField>
        <FormField label="Remote host" required error={formErrors.host}>
          <input bind:value={form.host} placeholder="mydb.cluster.us-east-1.rds.amazonaws.com" />
        </FormField>
        <FormField label="Remote port" required error={formErrors.port}>
          <input type="number" bind:value={form.port} placeholder="5432" />
        </FormField>
        <FormField label="Region" required error={formErrors.region}>
          <input bind:value={form.region} placeholder="us-east-1" />
        </FormField>
        <FormField label="Profile" hint="Optional" error={formErrors.profile}>
          <input bind:value={form.profile} placeholder="default" />
        </FormField>
        <FormField label="Local port" hint="Optional" error={formErrors.local_port}>
          <input type="number" bind:value={form.local_port} placeholder="auto" />
        </FormField>
        <FormField label="Local address" error={formErrors.local_address}>
          <input bind:value={form.local_address} placeholder="127.0.0.1" />
        </FormField>
      </div>

      <div class="modal-actions">
        <button
          class="btn-secondary"
          onclick={() => {
            showModal = false;
          }}
          disabled={saving}>Cancel</button
        >
        <button class="btn-primary" onclick={save} disabled={saving}>
          {#if saving}
            <span class="spinner-sm"></span> {editingName ? "Saving…" : "Creating…"}
          {:else}
            {editingName ? "Save" : "Create"}
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .host-cell {
    max-width: 220px;
  }
</style>
