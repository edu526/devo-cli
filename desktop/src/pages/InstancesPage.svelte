<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import { instancesApi, type InstanceRecord, type InstanceIn, ApiError } from "../lib/api";
  import { instancesCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import FormField from "../lib/FormField.svelte";
  import { instanceSchema, validate, type InstanceForm, type FieldErrors } from "../lib/forms";

  const initialInstances = Object.entries(get(instancesCache) ?? {}) as [string, InstanceRecord][];
  let instances: [string, InstanceRecord][] = $state(initialInstances);
  let loading = $state(initialInstances.length === 0);
  let refreshing = $state(false);
  let actionError: string | null = $state(null);
  let saving = $state(false);
  let deleting: Set<string> = $state(new Set());
  let query = $state("");

  // Modal state
  let showModal = $state(false);
  let editingName: string | null = $state(null);
  let form = $state<InstanceForm>({
    name: "",
    instance_id: "",
    region: "us-east-1",
    profile: "",
  });
  let formErrors: FieldErrors<InstanceForm> = $state({});

  const filtered = $derived(
    query.trim()
      ? instances.filter(
          ([name, rec]) =>
            name.toLowerCase().includes(query.toLowerCase()) ||
            rec.instance_id.toLowerCase().includes(query.toLowerCase()) ||
            rec.region.toLowerCase().includes(query.toLowerCase()) ||
            (rec.profile ?? "").toLowerCase().includes(query.toLowerCase()),
        )
      : instances,
  );

  async function load() {
    refreshing = true;
    try {
      const data = await instancesApi.list();
      instances = Object.entries(data);
      instancesCache.set(data);
    } catch (e) {
      actionError = String(e);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function openCreate() {
    editingName = null;
    form = { name: "", instance_id: "", region: "us-east-1", profile: "" };
    formErrors = {};
    actionError = null;
    showModal = true;
  }

  function openEdit(name: string, rec: InstanceRecord) {
    editingName = name;
    form = { name, instance_id: rec.instance_id, region: rec.region, profile: rec.profile ?? "" };
    formErrors = {};
    actionError = null;
    showModal = true;
  }

  async function save() {
    formErrors = {};
    const v = validate(instanceSchema, form);
    if (!v.success) {
      formErrors = v.errors;
      return;
    }
    actionError = null;
    saving = true;
    const body: InstanceIn = {
      instance_id: v.data.instance_id,
      region: v.data.region,
      profile: v.data.profile || undefined,
    };
    try {
      if (editingName) {
        await instancesApi.update(editingName, body);
      } else {
        await instancesApi.create(v.data.name, body);
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
    if (!confirm(`Delete instance "${name}"?`)) return;
    actionError = null;
    deleting = new Set([...deleting, name]);
    try {
      await instancesApi.delete(name);
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
      Instances {#if refreshing && !loading}<span class="refreshing-dot"></span>{/if}
    </h1>
    <div class="header-actions">
      <SearchInput bind:value={query} placeholder="Filter instances…" />
      <button class="btn-primary" onclick={openCreate}>New Instance</button>
    </div>
  </div>

  {#if actionError}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if instances.length === 0}
    <div class="empty-state">
      <p>No instances configured.</p>
      <p class="muted">Add an EC2 bastion instance to use for SSM tunnels.</p>
    </div>
  {:else if filtered.length === 0}
    <p class="muted">No instances match "{query}".</p>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Instance ID</th>
            <th>Region</th>
            <th>Profile</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as [name, rec] (name)}
            <tr>
              <td class="name">{name}</td>
              <td><code>{rec.instance_id}</code></td>
              <td>{rec.region}</td>
              <td>{rec.profile ?? "—"}</td>
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
      <h2>{editingName ? "Edit Instance" : "New Instance"}</h2>

      {#if actionError}
        <div class="alert-error">{actionError}</div>
      {/if}

      <FormField label="Name" required error={formErrors.name}>
        <input
          bind:value={form.name}
          disabled={!!editingName}
          placeholder="prod-bastion"
        />
      </FormField>
      <FormField label="Instance ID" required error={formErrors.instance_id}>
        <input bind:value={form.instance_id} placeholder="i-0abc123def456" />
      </FormField>
      <FormField label="Region" required error={formErrors.region}>
        <input bind:value={form.region} placeholder="us-east-1" />
      </FormField>
      <FormField label="Profile" hint="Optional" error={formErrors.profile}>
        <input bind:value={form.profile} placeholder="default" />
      </FormField>

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
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
</style>
