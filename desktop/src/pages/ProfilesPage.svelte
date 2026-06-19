<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { get } from "svelte/store";
  import {
    profilesApi,
    ssoSessionsApi,
    type ProfileRecord,
    type IdentityRecord,
    type SsoSessionRecord,
    type DiscoveredAccount,
    ApiError,
  } from "../lib/api";
  import { ws, type WsMessage } from "../lib/ws";
  import { profilesCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import FormField from "../lib/FormField.svelte";
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

  async function startDiscover() {
    if (!selectedSession) return;
    discoverInProgress = true;
    discoverError = null;
    discoverErrorRaw = null;
    discoveredAccounts = [];
    selectedAccountId = "";
    selectedRole = "";
    profileForm.sso_account_id = "";
    profileForm.sso_role_name = "";
    try {
      await profilesApi.discover(selectedSession);
      // Result arrives via WS `sso.discover.completed`
    } catch (e) {
      discoverError = friendlyError(e);
      discoverErrorRaw = e instanceof Error ? `${e.name}: ${e.message}` : String(e);
      discoverInProgress = false;
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
    if (e instanceof ApiError) return String(e.detail);
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
    offDiscoverStarting();
    offDiscoverCompleted();
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
              <span class="spinner-sm"></span> Approve the request in the browser window that
              just opened. This may take up to 2 minutes.
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
              <select
                bind:value={selectedAccountId}
                onchange={() => {
                  selectedRole = "";
                  applyAccountSelection();
                }}
              >
                <option value="" disabled>Select an account…</option>
                {#each discoveredAccounts as a (a.accountId)}
                  <option value={a.accountId}>
                    {a.accountName} ({a.accountId})
                  </option>
                {/each}
              </select>
            </FormField>

            {#if selectedAccountId}
              <FormField label="Role" required error={profileFormErrors.sso_role_name}>
                {#if availableRoles.length === 0}
                  <p class="muted-sm">No roles available for this account.</p>
                {:else}
                  <select
                    bind:value={selectedRole}
                    onchange={applyAccountSelection}
                    disabled={availableRoles.length === 0}
                  >
                    <option value="" disabled>Select a role…</option>
                    {#each availableRoles as r (r.roleName)}
                      <option value={r.roleName}>{r.roleName}</option>
                    {/each}
                  </select>
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
          class="btn-primary"
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
