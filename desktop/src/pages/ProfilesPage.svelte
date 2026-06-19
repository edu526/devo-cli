<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { profilesApi, type ProfileRecord, type IdentityRecord, ApiError } from "../lib/api";
  import { ws, type WsMessage } from "../lib/ws";
  import { profilesCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";

  const initialProfiles = (get(profilesCache) ?? []) as ProfileRecord[];
  let profiles: ProfileRecord[] = $state(initialProfiles);
  let defaultProfile: string | null = $state(
    initialProfiles.find((p) => p.is_default)?.name ?? null,
  );
  let identities: Record<string, IdentityRecord> = $state({});
  let loading = $state(initialProfiles.length === 0);
  let bgRefreshing = $state(false); // silent background refresh indicator
  let refreshing = $state(false); // "Refresh All" / SSO refresh in progress
  let actionError: string | null = $state(null);
  let busySet: Set<string> = $state(new Set());
  let busyIdentity: Set<string> = $state(new Set());
  let busyRefresh: Set<string> = $state(new Set());
  let ssoInProgress: string | null = $state(null);
  let query = $state("");

  const filtered = $derived(
    query.trim()
      ? profiles.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
      : profiles,
  );

  async function load() {
    bgRefreshing = true;
    try {
      const data = await profilesApi.list();
      profiles = data;
      defaultProfile = data.find((p) => p.is_default)?.name ?? null;
      profilesCache.set(data);
    } catch (e) {
      actionError = String(e);
    } finally {
      loading = false;
      bgRefreshing = false;
    }
  }

  async function refreshAll() {
    refreshing = true;
    actionError = null;
    try {
      await profilesApi.refreshAll();
      // Result arrives via WS profile.refreshed
    } catch (e) {
      actionError = e instanceof ApiError ? String(e.detail) : String(e);
      refreshing = false;
    }
  }

  async function refreshOne(name: string) {
    actionError = null;
    busyRefresh = new Set([...busyRefresh, name]);
    try {
      await profilesApi.refresh(name);
      // Actual result arrives via WS profile.refreshed / profile.refreshing
    } catch (e) {
      actionError = e instanceof ApiError ? String(e.detail) : String(e);
      busyRefresh = new Set([...busyRefresh].filter((n) => n !== name));
    }
  }

  async function setDefault(name: string) {
    actionError = null;
    busySet = new Set([...busySet, name]);
    try {
      await profilesApi.setDefault(name);
      defaultProfile = name; // optimistic — confirmed on load()
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? String(e.detail) : String(e);
    } finally {
      busySet = new Set([...busySet].filter((n) => n !== name));
    }
  }

  async function checkIdentity(name: string) {
    actionError = null;
    busyIdentity = new Set([...busyIdentity, name]);
    try {
      const id = await profilesApi.getIdentity(name);
      identities = { ...identities, [name]: id };
    } catch (e) {
      actionError = e instanceof ApiError ? String(e.detail) : String(e);
    } finally {
      busyIdentity = new Set([...busyIdentity].filter((n) => n !== name));
    }
  }

  // WS: sidecar signals that the browser SSO flow is open for this profile
  const offRefreshing = ws.on("profile.refreshing", (msg: WsMessage) => {
    ssoInProgress = (msg.name as string) ?? null;
  });

  const offRefreshed = ws.on("profile.refreshed", (msg: WsMessage) => {
    ssoInProgress = null;
    refreshing = false;
    busyRefresh = new Set();

    if (!msg.success) {
      actionError = (msg.error as string) ?? "Refresh failed";
    }
    load();
  });

  const offExpiring = ws.on("profile.expiring", () => load());

  onDestroy(() => {
    offRefreshing();
    offRefreshed();
    offExpiring();
  });

  onMount(load);

  function stateClass(status: string): string {
    if (status === "valid") return "badge-green";
    if (status === "expiring") return "badge-yellow";
    if (status === "expired") return "badge-red";
    return "badge-gray";
  }

  function formatSeconds(s: number | null): string {
    if (s === null) return "—";
    if (s <= 0) return "Expired";
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  function needsRefresh(status: string): boolean {
    return status === "expired" || status === "expiring";
  }

  const anyBusyRefresh = $derived(busyRefresh.size > 0 || refreshing);
</script>

  <div class="page">
    <div class="page-header">
      <h1>
        AWS Profiles {#if bgRefreshing && !loading}<span class="refreshing-dot"></span>{/if}
      </h1>
      <div class="header-actions">
        <SearchInput bind:value={query} placeholder="Filter profiles…" />
        <button class="btn-primary" onclick={refreshAll} disabled={anyBusyRefresh}>
          {#if refreshing}
            <span class="spinner-sm"></span> Refreshing…
          {:else}
            Refresh All
          {/if}
        </button>
      </div>
    </div>

  {#if ssoInProgress}
    <div class="alert-sso">
      <span class="spinner-sm spinner-sso"></span>
      <div>
        <strong>Browser SSO login in progress</strong> for <code>{ssoInProgress}</code>
        <p>
          Approve the request in the browser window that just opened. This may take up to 2 minutes.
        </p>
      </div>
    </div>
  {/if}

  {#if actionError}
    <div class="alert-error">
      {actionError}
      <button class="dismiss" onclick={() => (actionError = null)}>✕</button>
    </div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if profiles.length === 0}
    <div class="empty-state">
      <p>No SSO profiles found.</p>
      <p class="muted">Configure AWS SSO profiles in <code>~/.aws/config</code>.</p>
    </div>
  {:else}
    <div class="cards">
      {#each filtered as p (p.name)}
        <div
          class="card"
          class:is-default={defaultProfile === p.name}
          class:is-expired={p.status === "expired"}
          class:is-expiring={p.status === "expiring"}
        >
          {#if defaultProfile === p.name}
            <div class="default-bar">★ default credentials</div>
          {/if}
          <div class="card-header">
            <span class="card-name">{p.name}</span>
            <span class="badge {stateClass(p.status)}">{p.status}</span>
          </div>

          <p class="card-meta" style="margin-top: 0.4rem;">
            Expires in: <strong>{formatSeconds(p.seconds_remaining)}</strong>
          </p>

          {#if identities[p.name]}
            <p class="card-meta identity">
              {identities[p.name]!.account_id} · {identities[p.name]!.arn.split("/").pop()}
            </p>
          {/if}

          {#if busyRefresh.has(p.name)}
            <p class="card-meta refresh-hint">
              <span class="spinner-sm"></span>
              {ssoInProgress === p.name ? "Waiting for browser approval…" : "Starting SSO login…"}
            </p>
          {/if}

          <div class="card-actions">
            {#if needsRefresh(p.status)}
              <button
                class="btn-sm btn-refresh"
                onclick={() => refreshOne(p.name)}
                disabled={busyRefresh.has(p.name) || anyBusyRefresh}
              >
                {#if busyRefresh.has(p.name)}
                  <span class="spinner-sm"></span> Refreshing…
                {:else}
                  ↻ Refresh
                {/if}
              </button>
            {/if}
            <button
              class="btn-sm btn-secondary"
              onclick={() => checkIdentity(p.name)}
              disabled={busyIdentity.has(p.name)}
            >
              {#if busyIdentity.has(p.name)}
                <span class="spinner-sm"></span> Checking…
              {:else}
                Identity
              {/if}
            </button>
            <button
              class="btn-sm btn-primary"
              onclick={() => setDefault(p.name)}
              disabled={busySet.has(p.name) || defaultProfile === p.name}
            >
              {#if busySet.has(p.name)}
                <span class="spinner-sm"></span> Setting…
              {:else if defaultProfile === p.name}
                ✓ Default
              {:else}
                Set Default
              {/if}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 1rem;
  }

  .card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: border-color 0.2s;
  }

  .default-bar {
    background: #0d2a4a;
    color: #60a5fa;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 0.25rem 1rem;
    border-bottom: 1px solid #1e4a7a;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem 0;
  }

  .card-name {
    font-weight: 600;
    font-size: 0.9rem;
  }

  .card-meta {
    font-size: 0.8rem;
    color: #8a8a8a;
    padding: 0 1rem;
  }
  .identity {
    color: #6b9ef7;
  }

  .is-default {
    border-color: #1e4a7a;
  }
  .is-expired {
    border-color: #3a1a1a;
  }
  .is-expiring {
    border-color: #2a1f00;
  }

  .card-actions {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem 1rem 0.75rem;
    flex-wrap: wrap;
  }

  .btn-refresh {
    background: #1a2a1a;
    color: #4ade80;
    border: 1px solid #2a4a2a;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.7rem;
    border-radius: 6px;
    font-size: 0.78rem;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.15s;
  }
  .btn-refresh:hover:not(:disabled) {
    background: #1f3a1f;
  }
  .btn-refresh:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .refresh-hint {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: #fbbf24 !important;
    font-style: italic;
    padding: 0 1rem !important;
  }

  /* SSO in-progress banner */
  .alert-sso {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    background: #1a1a00;
    border: 1px solid #fbbf24;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    color: #fbbf24;
    font-size: 0.85rem;
  }
  .alert-sso strong {
    display: block;
    margin-bottom: 0.2rem;
  }
  .alert-sso p {
    margin: 0;
    color: #a08020;
    font-size: 0.8rem;
  }
  .alert-sso code {
    color: #fde68a;
  }
  .spinner-sso {
    margin-top: 3px;
    flex-shrink: 0;
  }

  /* Dismissible error */
  .alert-error {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .dismiss {
    background: none;
    border: none;
    color: #f87171;
    cursor: pointer;
    font-size: 0.9rem;
    padding: 0 0.25rem;
    line-height: 1;
  }
  .dismiss:hover {
    color: #fff;
  }
</style>
