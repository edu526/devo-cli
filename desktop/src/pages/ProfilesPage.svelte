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

  const statusPriority: Record<string, number> = { expired: 0, expiring: 1, valid: 2, unknown: 3 };

  const filtered = $derived.by(() => {
    const base = query.trim()
      ? profiles.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
      : profiles;
    return [...base].sort(
      (a, b) => (statusPriority[a.status] ?? 9) - (statusPriority[b.status] ?? 9),
    );
  });

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

  async function updateProfiles(names: string[]) {
    const updated = await Promise.all(names.map((n) => profilesApi.get(n)));
    const byName = new Map(updated.map((p) => [p.name, p]));
    profiles = profiles.map((p) => byName.get(p.name) ?? p);
    profilesCache.set(profiles);
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
      load();
      return;
    }

    const names = (msg.names as string[]) ?? [];
    if (names.length === 0) {
      load();
      return;
    }
    updateProfiles(names);
  });

  const offExpiring = ws.on("profile.expiring", () => load());

  onDestroy(() => {
    offRefreshing();
    offRefreshed();
    offExpiring();
  });

  onMount(load);

  function formatSeconds(s: number | null): string {
    if (s === null) return "—";
    if (s <= 0) return "Expired";
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
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
          </div>

          <p class="card-meta">
            <span class="status-dot status-{p.status}"></span>
            <span class="status-text">{p.status}</span>
            <span class="meta-sep">·</span>
            <span class="expiry">{formatSeconds(p.seconds_remaining)}</span>
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

          <div class="card-footer">
            {#if defaultProfile === p.name}
              <span class="default-label"><span class="default-star">★</span> Default</span>
            {:else}
              <button
                class="set-default-btn"
                onclick={() => setDefault(p.name)}
                disabled={busySet.has(p.name)}
              >
                <span class="default-star">{busySet.has(p.name) ? "…" : "☆"}</span>
                <span class="set-default-label">
                  {busySet.has(p.name) ? "Setting…" : "Set as default"}
                </span>
              </button>
            {/if}
            <div class="footer-utils">
              <button
                class="action-icon"
                aria-label="Refresh"
                disabled={busyRefresh.has(p.name) || anyBusyRefresh}
                onclick={() => refreshOne(p.name)}
              >
                <span class="action-glyph">↻</span>
                <span class="action-label">
                  {#if busyRefresh.has(p.name)}
                    {ssoInProgress === p.name ? "Approving…" : "Refreshing…"}
                  {:else}
                    Refresh
                  {/if}
                </span>
              </button>
              <button
                class="action-icon"
                aria-label="Check identity"
                disabled={busyIdentity.has(p.name)}
                onclick={() => checkIdentity(p.name)}
              >
                <svg
                  class="action-glyph"
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  aria-hidden="true"
                >
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <span class="action-label">
                  {busyIdentity.has(p.name) ? "Checking…" : "Identity"}
                </span>
              </button>
            </div>
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
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .card {
    width: 300px;
    flex-shrink: 0;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
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
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.85rem 1rem 0.25rem;
  }

  .card-name {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-primary);
  }

  .footer-utils {
    display: flex;
    align-items: center;
    gap: 0.15rem;
    margin-left: auto;
  }

  .action-icon {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    gap: 0;
    padding: 0.3rem 0.4rem;
    border-radius: 6px;
    cursor: pointer;
    font: inherit;
    font-size: 0.78rem;
    line-height: 1;
    transition:
      gap 0.18s ease,
      padding 0.18s ease,
      background 0.12s,
      border-color 0.12s,
      color 0.12s;
  }
  .action-icon:hover:not(:disabled) {
    gap: 0.4rem;
    padding: 0.3rem 0.55rem;
    background: var(--bg-surface-2);
    border-color: var(--border);
    color: var(--text-primary);
  }
  .action-icon:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .action-glyph {
    font-size: 0.95rem;
    line-height: 1;
    display: inline-flex;
    align-items: center;
  }
  .action-label {
    max-width: 0;
    overflow: hidden;
    white-space: nowrap;
    opacity: 0;
    transition:
      max-width 0.2s ease,
      opacity 0.15s ease;
  }
  .action-icon:hover:not(:disabled) .action-label {
    max-width: 120px;
    opacity: 1;
  }

  .card-meta {
    font-size: 0.75rem;
    color: var(--text-muted);
    padding: 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-family: "JetBrains Mono", "Cascadia Code", monospace;
  }
  .card-meta.identity {
    font-family: inherit;
    color: #6b9ef7;
  }
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    display: inline-block;
  }
  .status-dot.status-valid {
    background: #4ade80;
  }
  .status-dot.status-expiring {
    background: #fbbf24;
  }
  .status-dot.status-expired {
    background: #f87171;
  }
  .status-dot.status-unknown {
    background: #6a6a6a;
  }
  .status-text {
    text-transform: capitalize;
  }
  .meta-sep {
    color: var(--text-faint);
  }
  .expiry {
    color: var(--text-secondary);
  }

  .is-default {
    border-color: #1e4a7a;
  }
  .is-expired {
    border-left: 3px solid #f87171;
  }
  .is-expiring {
    border-left: 3px solid #fbbf24;
  }

  .card-footer {
    padding: 0.55rem 1rem 0.8rem;
    margin-top: auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }
  .default-label {
    font-size: 0.72rem;
    color: #60a5fa;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
  .default-star {
    font-size: 0.95rem;
    line-height: 1;
    margin-left: -0.2em;
  }
  .set-default-btn {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    gap: 0;
    padding: 0.3rem 0;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.78rem;
    font-family: inherit;
    transition:
      gap 0.18s ease,
      background 0.12s,
      border-color 0.12s,
      color 0.12s;
  }
  .set-default-btn:hover:not(:disabled) {
    gap: 0.4rem;
    background: var(--bg-surface-2);
    border-color: var(--border);
    color: var(--text-primary);
  }
  .set-default-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .set-default-label {
    max-width: 0;
    overflow: hidden;
    white-space: nowrap;
    opacity: 0;
    transition:
      max-width 0.2s ease,
      opacity 0.15s ease;
  }
  .set-default-btn:hover:not(:disabled) .set-default-label {
    max-width: 120px;
    opacity: 1;
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
