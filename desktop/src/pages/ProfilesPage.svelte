<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { get } from "svelte/store";
  import {
    profilesApi,
    ssoSessionsApi,
    getLastErrorDiagnostics,
    type ProfileRecord,
    type IdentityRecord,
    type SsoSessionRecord,
    type SsoSessionInfo,
    type DiscoveredAccount,
    ApiError,
  } from "../lib/api";
  import { ws, type WsMessage } from "../lib/ws";
  import { profilesCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import ViewToggle from "../lib/ViewToggle.svelte";
  import { viewModes } from "../lib/stores";
  import FormField from "../lib/FormField.svelte";
  import SearchableSelect from "../lib/SearchableSelect.svelte";
  import { retryNetworkErrors } from "../lib/retry";
  
  const viewMode = viewModes.profiles;
  import {
    profileSchema,
    ssoSessionSchema,
    validate,
    type ProfileForm,
    type SsoSessionForm,
    type FieldErrors,
  } from "../lib/forms";

  const initialProfiles = (get(profilesCache) ?? []) as ProfileRecord[];
  let profiles: ProfileRecord[] = $state(initialProfiles);
  let ssoSessionsInfo: SsoSessionInfo[] = $state([]);
  let defaultProfile: string | null = $state(
    initialProfiles.find((p) => p.is_default)?.name ?? null,
  );
  let loading = $state(initialProfiles.length === 0);
  let bgRefreshing = $state(false); // silent background refresh indicator
  let refreshing = $state(false); // "Refresh All" / SSO refresh in progress
  let actionError: string | null = $state(null);
  let busySet: Set<string> = $state(new Set());
  let busyRefresh: Set<string> = $state(new Set());
  let busyRefreshSso: Set<string> = $state(new Set());
  let ssoInProgress: string | null = $state(null);
  let ssoManualUrl: { url: string; code: string } | null = $state(null);
  let query = $state("");

  // ── Add Profile wizard state ───────────────────────────────────────────
  let showCreateModal = $state(false);
  let ssoSessions: SsoSessionRecord[] = $state([]);
  let ssoSessionsLoading = $state(false);
  let ssoSessionsError: string | null = $state(null);
  let selectedSession = $state<string>("");
  let newSessionMode = $state(false);
  let newSessionForm = $state<SsoSessionForm>({
    name: "",
    sso_start_url: "",
    sso_region: "us-east-1",
  });
  let newSessionErrors: FieldErrors<SsoSessionForm> = $state({});
  let creatingSession = $state(false);
  let discoverInProgress = $state(false);
  let discoverError: string | null = $state(null);
  let discoverAttempt = $state(0); // 0 = no retry, 1..3 = current attempt
  let discoveredAccounts: DiscoveredAccount[] = $state([]);
  let selectedAccountId = $state<string>("");
  let selectedRole = $state<string>("");
  let profileForm = $state<ProfileForm>({
    name: "",
    sso_session: "",
    sso_account_id: "",
    sso_role_name: "",
    region: "us-east-1",
    output: "json",
  });
  let profileFormErrors: FieldErrors<ProfileForm> = $state({});
  let creatingProfile = $state(false);

  const selectedAccount = $derived(
    discoveredAccounts.find((a) => a.accountId === selectedAccountId) ?? null,
  );
  const availableRoles = $derived(selectedAccount?.roles ?? []);

  async function openCreate() {
    showCreateModal = true;
    resetWizard();
    await loadSsoSessions();
  }

  function resetWizard() {
    selectedSession = ssoSessions[0]?.name ?? "";
    newSessionMode = false;
    newSessionForm = { name: "", sso_start_url: "", sso_region: "us-east-1" };
    newSessionErrors = {};
    discoverInProgress = false;
    discoverError = null;
    discoverErrorRaw = null;
    discoveredAccounts = [];
    selectedAccountId = "";
    selectedRole = "";
    profileForm = {
      name: "",
      sso_session: selectedSession,
      sso_account_id: "",
      sso_role_name: "",
      region: "us-east-1",
      output: "json",
    };
    profileFormErrors = {};
    actionError = null;
  }

  async function loadSsoSessions() {
    ssoSessionsLoading = true;
    ssoSessionsError = null;
    try {
      ssoSessions = await ssoSessionsApi.list();
      if (!selectedSession && ssoSessions[0]) {
        selectedSession = ssoSessions[0].name;
        profileForm.sso_session = selectedSession;
      }
    } catch (e) {
      ssoSessionsError = friendlyError(e);
    } finally {
      ssoSessionsLoading = false;
    }
  }

  // Raw error string for the "Technical details" expander in the modal.
  // Kept separate from the friendly message so the user can always see
  // the underlying TypeError / status text when debugging.
  let discoverErrorRaw = $state<string | null>(null);

  async function startDiscover() {
    if (!selectedSession) return;
    discoverInProgress = true;
    discoverError = null;
    discoverErrorRaw = null;
    discoverAttempt = 1;
    discoveredAccounts = [];
    selectedAccountId = "";
    selectedRole = "";
    profileForm.sso_account_id = "";
    profileForm.sso_role_name = "";
    try {
      await retryNetworkErrors(
        async () => {
          discoverAttempt = Math.max(discoverAttempt, 1);
          await profilesApi.discover(selectedSession);
        },
        {
          attempts: 3,
          baseMs: 600,
          onRetry: (n) => (discoverAttempt = n + 1),
        },
      );
      // Result arrives via WS `sso.discover.completed`
    } catch (e) {
      discoverError = friendlyError(e);
      // Show the raw error plus the network diagnostics captured by
      // api.ts (resource timing, time since last success, webview UA).
      // The user can copy this in a bug report; we can also see at a
      // glance whether the request was killed before starting
      // (resourceEntryCount: 0 → Tauri webview race condition) or
      // actually attempted and failed.
      const raw = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
      const diag = getLastErrorDiagnostics();
      discoverErrorRaw = diag ? `${raw}\n\n${diag}` : raw;
      discoverInProgress = false;
      discoverAttempt = 0;
    }
  }

  async function createSession() {
    newSessionErrors = {};
    const v = validate(ssoSessionSchema, newSessionForm);
    if (!v.success) {
      newSessionErrors = v.errors;
      return;
    }
    creatingSession = true;
    ssoSessionsError = null;
    try {
      const created = await ssoSessionsApi.create({
        name: v.data.name,
        sso_start_url: v.data.sso_start_url,
        sso_region: v.data.sso_region,
      });
      ssoSessions = [...ssoSessions, created].sort((a, b) =>
        a.name.localeCompare(b.name),
      );
      selectedSession = created.name;
      newSessionMode = false;
      profileForm.sso_session = created.name;
    } catch (e) {
      newSessionErrors = { name: friendlyError(e) };
    } finally {
      creatingSession = false;
    }
  }

  function applyAccountSelection() {
    profileForm.sso_account_id = selectedAccountId;
    profileForm.sso_role_name = selectedRole;
    if (selectedAccount) {
      profileForm.sso_role_name = selectedRole;
      // Auto-suggest a profile name if the user hasn't typed one yet.
      if (!profileForm.name || profileForm.name === suggestedName) {
        profileForm.name = suggestedName;
      }
    }
  }

  const suggestedName = $derived.by(() => {
    if (!selectedAccount || !selectedRole) return profileForm.name;
    const slug = selectedRole
      .replace(/[^a-zA-Z0-9-]/g, "-")
      .replace(/-+/g, "-")
      .toLowerCase();
    return `${selectedSession}-${selectedAccount.accountId.slice(0, 4)}-${slug}`;
  });

  async function submitProfile() {
    profileFormErrors = {};
    profileForm.sso_session = selectedSession;
    profileForm.sso_account_id = selectedAccountId;
    profileForm.sso_role_name = selectedRole;
    const v = validate(profileSchema, profileForm);
    if (!v.success) {
      profileFormErrors = v.errors;
      return;
    }
    creatingProfile = true;
    actionError = null;
    try {
      await profilesApi.create({
        name: v.data.name,
        sso_session: v.data.sso_session,
        sso_account_id: v.data.sso_account_id,
        sso_role_name: v.data.sso_role_name,
        region: v.data.region,
        output: v.data.output,
      });
      showCreateModal = false;
      await load();
    } catch (e) {
      actionError = friendlyError(e);
    } finally {
      creatingProfile = false;
    }
  }

  function onModalKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") showCreateModal = false;
    e.stopPropagation();
  }

  const statusPriority: Record<string, number> = { expired: 0, expiring: 1, valid: 2, unknown: 3 };

  // Surface network errors as actionable messages instead of the raw
  // "TypeError: Load failed" that fetch throws when the sidecar is
  // unreachable, the CORS preflight is blocked, or the request is
  // aborted. ApiError (the sidecar's JSON error envelope) is passed
  // through unchanged so 409/422 messages still appear as-is.
  function friendlyError(e: unknown): string {
    if (e instanceof ApiError) return e.message;
    if (
      e instanceof TypeError &&
      (e.message === "Load failed" || e.message === "Failed to fetch")
    ) {
      return "Cannot reach Devo's sidecar — it may have stopped. Restart Devo Desktop and try again.";
    }
    return e instanceof Error ? e.message : String(e);
  }

  const filtered = $derived.by(() => {
    const base = query.trim()
      ? profiles.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
      : profiles;
    return [...base].sort((a, b) => {
      const diff = (statusPriority[a.status] ?? 9) - (statusPriority[b.status] ?? 9);
      if (diff !== 0) return diff;
      return a.name.localeCompare(b.name);
    });
  });

  async function load() {
    bgRefreshing = true;
    try {
      const [data, sessions] = await Promise.all([profilesApi.list(), ssoSessionsApi.info()]);
      profiles = data;
      ssoSessionsInfo = sessions;
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
      actionError = e instanceof ApiError ? e.message : String(e);
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
      actionError = e instanceof ApiError ? e.message : String(e);
      busyRefresh = new Set([...busyRefresh].filter((n) => n !== name));
    }
  }

  async function refreshSsoToken(name: string) {
    actionError = null;
    busyRefreshSso = new Set([...busyRefreshSso, name]);
    try {
      await profilesApi.refreshSsoToken(name);
      const [data, sessions] = await Promise.all([profilesApi.list(), ssoSessionsApi.info()]);
      profiles = data;
      ssoSessionsInfo = sessions;
      profilesCache.set(data);
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyRefreshSso = new Set([...busyRefreshSso].filter((n) => n !== name));
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
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busySet = new Set([...busySet].filter((n) => n !== name));
    }
  }



  let busyDelete: Set<string> = $state(new Set());
  let confirmDelete: string | null = $state(null);

  function askDelete(name: string) {
    confirmDelete = name;
  }
  function cancelDelete() {
    confirmDelete = null;
  }
  async function confirmDeleteNow() {
    const name = confirmDelete;
    if (!name) return;
    confirmDelete = null;
    actionError = null;
    busyDelete = new Set([...busyDelete, name]);
    try {
      await profilesApi.delete(name);
      // Optimistic: drop from local list immediately, then reload to
      // confirm the sidecar agrees.
      profiles = profiles.filter((p) => p.name !== name);
      if (defaultProfile === name) defaultProfile = null;
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyDelete = new Set([...busyDelete].filter((n) => n !== name));
    }
  }

  // WS: sidecar signals that the browser SSO flow is open for this profile
  const offRefreshing = ws.on("profile.refreshing", (msg: WsMessage) => {
    ssoInProgress = (msg.name as string) ?? null;
  });

  const offRefreshed = ws.on("profile.refreshed", (msg: WsMessage) => {
    ssoInProgress = null;
    ssoManualUrl = null;
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

  const offUrlReady = ws.on("sso.login.url_ready", (msg: WsMessage) => {
    const m = msg as { profile?: string; source?: string; url?: string; code?: string };
    if (m.source === "profile" && m.profile === ssoInProgress) {
      ssoManualUrl = { url: m.url!, code: m.code! };
    }
  });

  // WS: sidecar signals completion of the discovery pipeline started by
  // the Add Profile wizard. Only acts when the modal is open so a stale
  // late event from a previous attempt cannot mutate the form.
  const offDiscoverStarting = ws.on("sso.discover.starting", () => {
    if (showCreateModal) discoverInProgress = true;
  });

  const offDiscoverCompleted = ws.on("sso.discover.completed", (msg: WsMessage) => {
    if (!showCreateModal) return;
    discoverInProgress = false;
    if (!msg.success) {
      discoverError = (msg.error as string) ?? "SSO discovery failed";
      return;
    }
    discoverError = null;
    discoveredAccounts = (msg.accounts as DiscoveredAccount[]) ?? [];
  });

  onDestroy(() => {
    offRefreshing();
    offRefreshed();
    offExpiring();
    offUrlReady();
    offDiscoverStarting();
    offDiscoverCompleted();
  });

  onMount(load);

  function formatSeconds(s: number | null): string {
    if (s === null) return "—";
    if (s <= 0) return "0m";
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
        <ViewToggle page="profiles" />
        <SearchInput bind:value={query} placeholder="Filter profiles…" />
        <button class="btn-secondary" onclick={openCreate}>
          <span class="btn-glyph">+</span>
          <span>Add Profile</span>
        </button>
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
        {#if ssoManualUrl}
          <p>
            Your browser could not be opened automatically. Please open 
            <a href={ssoManualUrl.url} target="_blank" rel="noreferrer">{ssoManualUrl.url}</a> 
            and enter the code <strong>{ssoManualUrl.code}</strong>.
          </p>
        {:else}
          <p>
            Approve the request in the browser window that just opened. This may take up to 2 minutes.
          </p>
        {/if}
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


    {#if $viewMode === 'table'}
      <div class="table-wrap" style="margin-top: 1rem">
        <table>
          <thead>
            <tr>
              <th>Profile</th>
              <th>Status</th>
              <th>Time Left</th>
              <th class="actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each filtered as p (p.name)}
              <tr>
                <td class="name">
                  {p.name}
                  {#if defaultProfile === p.name}
                    <span class="badge badge-green" style="margin-left: 8px">Default</span>
                  {/if}
                </td>
                <td>
                  <span class="status-dot status-{p.status}"></span>
                  <span class="status-text">{p.status}</span>
                </td>
                <td>{formatSeconds(p.seconds_remaining)}</td>

                <td class="actions-cell">
                  <div class="actions-wrap">
                    {#if defaultProfile !== p.name}
                      <button
                        class="btn-sm btn-secondary"
                        onclick={() => setDefault(p.name)}
                        disabled={busySet.has(p.name)}
                      >
                        {busySet.has(p.name) ? "Setting…" : "Set Default"}
                      </button>
                    {/if}
                    <button
                      class="btn-sm btn-primary"
                      disabled={busyRefresh.has(p.name) || anyBusyRefresh}
                      onclick={() => refreshOne(p.name)}
                    >
                      {#if busyRefresh.has(p.name)}
                        {ssoInProgress === p.name ? "Approving…" : "Refreshing…"}
                      {:else}
                        Refresh
                      {/if}
                    </button>

                    <button
                      class="btn-sm btn-danger"
                      disabled={busyDelete.has(p.name)}
                      onclick={() => removeProfile(p.name)}
                      title="Delete profile from ~/.aws/config"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
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

              <span class="footer-sep" aria-hidden="true"></span>
              <button
                class="action-icon action-danger"
                aria-label="Delete profile"
                disabled={busyDelete.has(p.name)}
                onclick={() => askDelete(p.name)}
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
                  <path d="M3 6h18" />
                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <line x1="10" y1="11" x2="10" y2="17" />
                  <line x1="14" y1="11" x2="14" y2="17" />
                </svg>
                <span class="action-label">
                  {busyDelete.has(p.name) ? "Deleting…" : "Delete"}
                </span>
              </button>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
  {/if}
</div>

{#if showCreateModal}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={() => (showCreateModal = false)}
    onkeydown={() => (showCreateModal = false)}
  >
    <div
      class="modal modal-wizard"
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-profile-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={onModalKeydown}
    >
      <h2 id="add-profile-title">New AWS Profile</h2>

      {#if actionError}
        <div class="alert-error">{actionError}</div>
      {/if}

      <!-- Step 1: SSO session -->
      <section class="wizard-step">
        <h3>
          <span class="step-num">1</span> SSO session
        </h3>
        {#if ssoSessionsLoading}
          <p class="muted-sm">Loading sessions…</p>
        {:else if ssoSessionsError}
          <div class="alert-error">{ssoSessionsError}</div>
        {:else if ssoSessions.length === 0}
          <p class="muted-sm">
            No <code>[sso-session]</code> blocks in <code>~/.aws/config</code>. Create one to
            continue, or run <code>aws configure sso</code> in a terminal.
          </p>
          <button class="btn-secondary btn-sm" onclick={() => (newSessionMode = true)}>
            + New SSO session
          </button>
        {:else}
          <FormField label="Session" required>
            <select bind:value={selectedSession} onchange={() => (discoveredAccounts = [])}>
              {#each ssoSessions as s (s.name)}
                <option value={s.name}>
                  {s.name} — {s.sso_start_url}
                </option>
              {/each}
            </select>
          </FormField>
          <button
            class="link-btn"
            onclick={() => (newSessionMode = !newSessionMode)}
            type="button"
          >
            {newSessionMode ? "Cancel" : "+ New SSO session"}
          </button>
        {/if}

        {#if newSessionMode}
          <div class="new-session">
            <FormField label="Session name" required error={newSessionErrors.name}>
              <input
                bind:value={newSessionForm.name}
                placeholder="my-company"
                spellcheck="false"
                autocomplete="off"
              />
            </FormField>
            <FormField
              label="SSO start URL"
              required
              hint="From your AWS SSO portal (https://…awsapps.com/start)"
              error={newSessionErrors.sso_start_url}
            >
              <input
                bind:value={newSessionForm.sso_start_url}
                placeholder="https://example.awsapps.com/start"
                spellcheck="false"
                autocomplete="off"
              />
            </FormField>
            <FormField label="SSO region" required error={newSessionErrors.sso_region}>
              <input
                bind:value={newSessionForm.sso_region}
                placeholder="us-east-1"
                spellcheck="false"
              />
            </FormField>
            <button
              class="btn-secondary btn-sm"
              onclick={createSession}
              disabled={creatingSession}
            >
              {#if creatingSession}
                <span class="spinner-sm"></span> Creating…
              {:else}
                Create session
              {/if}
            </button>
          </div>
        {/if}
      </section>

      <!-- Step 2: Account discovery -->
      {#if !ssoSessionsLoading && ssoSessions.length > 0}
        <section class="wizard-step">
          <h3>
            <span class="step-num">2</span> Account &amp; role
          </h3>
          {#if discoverInProgress}
            <p class="muted-sm">
              <span class="spinner-sm"></span>
              {#if discoverAttempt > 1}
                Retrying… (attempt {discoverAttempt} of 3)
              {:else}
                Approve the request in the browser window that just opened. This may take up to 2 minutes.
              {/if}
            </p>
          {:else if discoverError}
            <div class="alert-error">
              {discoverError}
              {#if discoverErrorRaw && discoverErrorRaw !== discoverError}
                <details class="error-details">
                  <summary>Technical details</summary>
                  <code>{discoverErrorRaw}</code>
                </details>
              {/if}
            </div>
            <button class="btn-secondary btn-sm" onclick={startDiscover}>Retry</button>
          {:else if discoveredAccounts.length === 0}
            <p class="muted-sm">
              Sign in to <code>{selectedSession}</code> and fetch available accounts and roles.
            </p>
            <button class="btn-secondary btn-sm" onclick={startDiscover}>
              Sign in &amp; discover
            </button>
          {:else}
            <FormField label="Account" required>
              <SearchableSelect
                options={discoveredAccounts.map((a) => ({
                  value: a.accountId,
                  label: `${a.accountName} (${a.accountId})`,
                }))}
                bind:value={selectedAccountId}
                placeholder="Search accounts…"
                onchange={() => {
                  selectedRole = "";
                  applyAccountSelection();
                }}
              />
            </FormField>

            {#if selectedAccountId}
              <FormField label="Role" required error={profileFormErrors.sso_role_name}>
                {#if availableRoles.length === 0}
                  <p class="muted-sm">No roles available for this account.</p>
                {:else}
                  <SearchableSelect
                    options={availableRoles.map((r) => ({
                      value: r.roleName,
                      label: r.roleName,
                    }))}
                    bind:value={selectedRole}
                    placeholder="Search roles…"
                    onchange={applyAccountSelection}
                  />
                {/if}
              </FormField>
            {/if}
          {/if}
        </section>
      {/if}

      <!-- Step 3: Profile details -->
      {#if selectedAccountId && selectedRole}
        <section class="wizard-step">
          <h3>
            <span class="step-num">3</span> Profile
          </h3>
          <div class="form-grid">
            <FormField label="Profile name" required error={profileFormErrors.name}>
              <input
                bind:value={profileForm.name}
                placeholder="dev-readonly"
                spellcheck="false"
                autocomplete="off"
              />
            </FormField>
            <FormField
              label="AWS region"
              required
              hint="Default region for this profile"
              error={profileFormErrors.region}
            >
              <input
                bind:value={profileForm.region}
                placeholder="us-east-1"
                spellcheck="false"
              />
            </FormField>
          </div>
        </section>
      {/if}

      <div class="modal-actions">
        <button
          class="btn-secondary"
          onclick={() => (showCreateModal = false)}
          disabled={creatingProfile}>Cancel</button
        >
        <button
          class="btn-primary btn-create-profile"
          onclick={submitProfile}
          disabled={creatingProfile ||
            !selectedAccountId ||
            !selectedRole ||
            discoveredAccounts.length === 0}
        >
          {#if creatingProfile}
            <span class="spinner-sm"></span> Creating…
          {:else}
            Create profile
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if confirmDelete}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={cancelDelete}
    onkeydown={cancelDelete}
  >
    <div
      class="modal modal-confirm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="delete-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={onModalKeydown}
    >
      <h2 id="delete-title">Delete profile?</h2>
      <p class="modal-hint">
        This removes the <code>[profile {confirmDelete}]</code> block from
        <code>~/.aws/config</code>. Cached credentials in
        <code>~/.aws/credentials</code> are left untouched.
      </p>
      <div class="modal-actions">
        <button class="btn-secondary" onclick={cancelDelete} disabled={busyDelete.size > 0}
          >Cancel</button
        >
        <button class="btn-danger" onclick={confirmDeleteNow} disabled={busyDelete.size > 0}>
          {#if busyDelete.size > 0}
            <span class="spinner-sm"></span> Deleting…
          {:else}
            Delete
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

  .btn-glyph {
    font-size: 1rem;
    line-height: 1;
    margin-right: 0.2rem;
    font-weight: 500;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem 1rem;
  }

  .modal-hint {
    margin: 0;
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  /* Wizard layout */
  .modal-wizard {
    gap: 1.1rem;
  }
  .wizard-step {
    border-top: 1px solid var(--border);
    padding-top: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }
  .wizard-step h3 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin: 0 0 0.2rem 0;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--bg-surface-2);
    color: var(--text-muted);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0;
  }
  .muted-sm {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin: 0;
  }
  .muted-sm code {
    background: var(--bg-surface-2);
    padding: 0.05rem 0.3rem;
    border-radius: 3px;
    font-size: 0.75rem;
  }
  .new-session {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    padding: 0.7rem 0.85rem;
    background: var(--bg-surface-2);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .new-session :global(.form-field) {
    margin-bottom: 0.4rem;
  }
  .link-btn {
    background: none;
    border: none;
    color: #6b9ef7;
    font-size: 0.78rem;
    cursor: pointer;
    padding: 0.15rem 0;
    text-align: left;
    font-family: inherit;
  }
  .link-btn:hover {
    color: #9bbcff;
    text-decoration: underline;
  }
  .btn-sm {
    padding: 0.35rem 0.7rem;
    font-size: 0.78rem;
  }

  /* Keep the Create-profile button width stable so the inline spinner
     doesn't push the label to the side. min-width is sized to fit the
     longer of the two labels (with spinner) so the layout doesn't
     jump when toggling loading state. */
  .btn-create-profile {
    min-width: 7.2rem;
    justify-content: center;
  }

  .footer-sep {
    width: 1px;
    height: 18px;
    background: var(--border, #2a2a2a);
    margin: 0 0.15rem;
  }
  .action-danger {
    color: #f87171;
  }
  .action-danger:hover:not(:disabled) {
    color: #fff;
    background: rgba(248, 113, 113, 0.12);
    border-color: rgba(248, 113, 113, 0.4);
  }
  .modal-confirm {
    min-width: 380px;
  }

  .error-details {
    margin-top: 0.4rem;
    font-size: 0.75rem;
  }
  .error-details summary {
    cursor: pointer;
    color: #fca5a5;
    font-size: 0.72rem;
    user-select: none;
  }
  .error-details summary:hover {
    color: #fff;
  }
  .error-details code {
    display: block;
    margin-top: 0.3rem;
    padding: 0.4rem 0.5rem;
    background: rgba(0, 0, 0, 0.35);
    border-radius: 4px;
    color: #fca5a5;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .cards {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .card {
    width: 300px;
    flex-shrink: 0;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    transition: border-color 0.2s, background 0.2s;
  }
  .card:hover {
    background: var(--bg-surface-2);
    border-color: var(--border-strong);
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
  .action-icon.icon-only {
    padding: 0.15rem 0.3rem;
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
  .sso-sessions {
    margin-bottom: 1.25rem;
  }
  .sso-header {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted, #888);
    margin-bottom: 0.5rem;
  }
  .sso-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .sso-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
  }
  .sso-card-main {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    min-width: 0;
  }
  .sso-name-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .sso-name {
    font-size: 0.95rem;
  }
  .badge-count {
    background: var(--bg-input, #2a2a2a);
    color: var(--text-muted, #888);
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    font-size: 0.7rem;
  }
  .sso-meta {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.8rem;
  }
  .sso-meta .status-dot {
    width: 6px;
    height: 6px;
  }
</style>
