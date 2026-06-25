<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    codeartifactApi,
    ApiError,
    type CodeArtifactDomain,
    type CodeArtifactToken,
    type CodeArtifactLoginResult,
  } from "../lib/api";
  import { ws } from "../lib/ws";
  import FormField from "../lib/FormField.svelte";
  import { codeartifactDomainSchema, validate, type CodeArtifactDomainForm, type FieldErrors } from "../lib/forms";

  const configExample = `{ "domain": "my-domain", "repository": "npm", "namespace": "@scope", "account_id": "123456789012", "profile": "my-profile", "region": "us-east-1" }`;

  let domains: CodeArtifactDomain[] = $state([]);
  let tokens: CodeArtifactToken[] = $state([]);
  let loading = $state(true);
  let actionError: string | null = $state(null);
  let busyDomain: string | null = $state(null);
  let packagesOpen: Record<string, boolean> = $state({});
  let packagesData: Record<string, [string, string | null][]> = $state({});
  let loadingPackages: string | null = $state(null);
  let toolSelections: Record<string, string> = $state({});
  let deleting: Record<string, boolean> = $state({});

  // SSO chain state — when CodeArtifact login hits a dead SSO, the backend
  // returns 202 and we show a banner until the browser flow completes.
  let ssoLoginInProgress: { profile: string; domain: string; tool: string } | null = $state(null);
  let ssoLoginError: string | null = $state(null);
  let ssoLoginUnsubscribe: (() => void) | null = null;

  // Modal state
  let showModal = $state(false);
  let editingName: string | null = $state(null);
  let form = $state<CodeArtifactDomainForm>({
    domain: "",
    repository: "",
    namespace: "",
    account_id: "",
    profile: "",
    region: "us-east-1",
  });
  let formErrors: FieldErrors<CodeArtifactDomainForm> = $state({});
  let saving = $state(false);

  function tokenFor(domain: string, tool: string): CodeArtifactToken | null {
    return tokens.find((t) => t.domain === domain && t.tool === tool) ?? null;
  }

  function toolFor(domain: CodeArtifactDomain): string {
    return toolSelections[domain.domain] ?? "npm";
  }

  function formatExpiry(iso: string | null): string | null {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    const ms = d.getTime() - Date.now();
    if (ms < 0) return "expired";
    const h = Math.floor(ms / 3600000);
    const m = Math.floor((ms % 3600000) / 60000);
    return `${h}h ${m}m left`;
  }

  async function load() {
    loading = true;
    actionError = null;
    try {
      const [d, t] = await Promise.all([codeartifactApi.domains(), codeartifactApi.tokens()]);
      domains = d;
      tokens = t;
      for (const dom of domains) {
        if (!(dom.domain in toolSelections)) {
          toolSelections[dom.domain] = "npm";
        }
      }
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function doLogin(domain: CodeArtifactDomain) {
    actionError = null;
    busyDomain = domain.domain;
    const tool = toolFor(domain);
    try {
      const result = await codeartifactApi.login(domain.domain, tool);
      // Backend returns 202 + sso_required when the SSO session is dead
      if ("status" in result && result.status === "sso_required") {
        handleSsoRequired(result.profile, domain.domain, tool);
        return;
      }
      tokens = await codeartifactApi.tokens();
      loginCache[domain.domain] = result as CodeArtifactLoginResult;
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyDomain = null;
    }
  }

  function handleSsoRequired(profile: string, domain: string, tool: string) {
    ssoLoginInProgress = { profile, domain, tool };
    ssoLoginError = null;
    // Subscribe once; the listener stays alive across retries until cleared
    if (ssoLoginUnsubscribe) ssoLoginUnsubscribe();
    ssoLoginUnsubscribe = ws.on("sso.login.completed", (msg) => {
      const m = msg as { profile?: string; source?: string; success?: boolean; error?: string };
      if (m.source !== "codeartifact" || m.profile !== profile) return;
      ssoLoginInProgress = null;
      if (m.success) {
        // Auto-retry the original CodeArtifact login
        const dom = domains.find((d) => d.domain === domain);
        if (dom) doLogin(dom);
      } else {
        ssoLoginError = m.error ?? "Browser SSO login failed";
      }
    });
  }

  // In-memory cache of last login result (not the JWT, just metadata)
  let loginCache: Record<string, CodeArtifactLoginResult> = {};


  async function togglePackages(domain: CodeArtifactDomain) {
    if (packagesOpen[domain.domain]) {
      packagesOpen = { ...packagesOpen, [domain.domain]: false };
      return;
    }
    packagesOpen = { ...packagesOpen, [domain.domain]: true };
    loadingPackages = domain.domain;
    try {
      const pkgs = await codeartifactApi.packages(domain.domain);
      packagesData = {
        ...packagesData,
        [domain.domain]: Object.entries(pkgs).map(([k, v]) => [k, v] as [string, string | null]),
      };
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      loadingPackages = null;
    }
  }

  function openCreate() {
    editingName = null;
    form = { domain: "", repository: "", namespace: "", account_id: "", profile: "", region: "us-east-1" };
    formErrors = {};
    showModal = true;
  }

  function openEdit(domain: CodeArtifactDomain) {
    editingName = domain.domain;
    form = {
      domain: domain.domain,
      repository: domain.repository,
      namespace: domain.namespace ?? "",
      account_id: domain.account_id ?? "",
      profile: domain.profile ?? "",
      region: domain.region,
    };
    formErrors = {};
    showModal = true;
  }

  async function saveDomain() {
    formErrors = {};
    const v = validate(codeartifactDomainSchema, form);
    if (!v.success) {
      formErrors = v.errors;
      return;
    }
    saving = true;
    actionError = null;
    try {
      if (editingName) {
        await codeartifactApi.update(editingName, {
          repository: v.data.repository,
          namespace: v.data.namespace,
          account_id: v.data.account_id,
          profile: v.data.profile,
          region: v.data.region,
        });
      } else {
        await codeartifactApi.create({
          domain: v.data.domain,
          repository: v.data.repository,
          namespace: v.data.namespace,
          account_id: v.data.account_id,
          profile: v.data.profile,
          region: v.data.region,
        });
      }
      showModal = false;
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  async function removeDomain(domain: CodeArtifactDomain) {
    if (!confirm(`Delete registry "${domain.domain}"? This will not invalidate any active tokens.`)) return;
    deleting = { ...deleting, [domain.domain]: true };
    actionError = null;
    try {
      await codeartifactApi.remove(domain.domain);
      domains = domains.filter((d) => d.domain !== domain.domain);
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      deleting = { ...deleting, [domain.domain]: false };
    }
  }

  function onModalKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") showModal = false;
    e.stopPropagation();
  }

  onMount(load);
  onDestroy(() => {
    ssoLoginUnsubscribe?.();
  });
</script>

<div class="page">
  <div class="page-header">
    <h1>Registry</h1>
    <div class="header-actions">
      <button class="btn-secondary" onclick={load} disabled={loading}>Refresh</button>
      <button class="btn-primary" onclick={openCreate}>New Registry</button>
    </div>
  </div>

  {#if actionError}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if ssoLoginInProgress}
    <div class="sso-banner">
      <div class="sso-banner-main">
        <span class="spinner-sm sso-spinner"></span>
        <div>
          <strong>Browser SSO login in progress</strong> for <code>{ssoLoginInProgress.profile}</code>
          <p>Approve the request in the browser window that just opened. The CodeArtifact login will retry automatically.</p>
        </div>
      </div>
    </div>
  {/if}

  {#if ssoLoginError}
    <div class="alert-error">
      {ssoLoginError}
      <button class="dismiss" onclick={() => (ssoLoginError = null)}>✕</button>
    </div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if domains.length === 0}
    <div class="empty-state">
      <p>No registry domains configured.</p>
      <p class="muted">
        Click <strong>New Registry</strong> to add one. Example config:
        <br /><code>{configExample}</code>
      </p>
    </div>
  {:else}
    <div class="domain-list">
      {#each domains as domain (domain.domain)}
        {@const tool = toolFor(domain)}
        {@const token = tokenFor(domain.domain, tool)}
        {@const isLoggedIn = !!token}
        <div class="domain-card" class:logged-in={isLoggedIn}>
          <div class="card-header">
            <div class="domain-title">
              <strong>{domain.domain}</strong>
              <span class="badge">{domain.repository}</span>
              {#if domain.namespace}
                <code class="namespace">{domain.namespace}</code>
              {/if}
            </div>
            <div class="card-meta">
              <span class="muted">Account: {domain.account_id || "—"}</span>
              <span class="muted">Profile: {domain.profile || "auto"}</span>
              <span class="muted">Region: {domain.region}</span>
            </div>
            <div class="card-status">
              {#if isLoggedIn}
                <span class="status-dot" aria-hidden="true">●</span>
                <span class="muted">Connected via {tool}</span>
                {#if formatExpiry(token!.expires_at)}
                  <span class="muted">· {formatExpiry(token!.expires_at)}</span>
                {/if}
              {:else}
                <span class="status-dot dim" aria-hidden="true">○</span>
                <span class="muted">Not connected</span>
              {/if}
            </div>
            <div class="card-actions">
              <button class="btn-sm btn-secondary" onclick={() => openEdit(domain)}>Edit</button>
              <button
                class="btn-sm btn-danger"
                onclick={() => removeDomain(domain)}
                disabled={deleting[domain.domain]}
              >
                {deleting[domain.domain] ? "…" : "Delete"}
              </button>
            </div>
          </div>

          <div class="section">
            <div class="section-title">Authentication</div>
            <div class="auth-row">
              <select bind:value={toolSelections[domain.domain]}>
                <option value="npm">npm</option>
                <option value="pip">pip</option>
                <option value="twine">twine</option>
              </select>
              <button
                class="btn-primary"
                onclick={() => doLogin(domain)}
                disabled={busyDomain === domain.domain}
              >
                {#if busyDomain === domain.domain}
                  <span class="spinner-sm"></span> Logging in…
                {:else}
                  {isLoggedIn ? "Refresh Token" : "Login"}
                {/if}
              </button>
              {#if token}
                <span class="muted">Registry: <code class="registry-url">{token.registry_url}</code></span>
              {/if}
            </div>
          </div>

          <div class="section">
            <div class="section-title">
              <span>Packages</span>
              <button
                class="btn-sm btn-secondary"
                onclick={() => togglePackages(domain)}
                disabled={loadingPackages === domain.domain}
              >
                {#if loadingPackages === domain.domain}
                  <span class="spinner-sm"></span>
                {:else if packagesOpen[domain.domain]}
                  Hide
                {:else}
                  Show
                {/if}
              </button>
            </div>
            {#if packagesOpen[domain.domain]}
              {#if packagesData[domain.domain]?.length}
                <div class="packages-list">
                  {#each packagesData[domain.domain] as [name, version] (name)}
                    <div class="pkg-row">
                      <code>{name}</code>
                      {#if version}
                        <span class="muted">@{version}</span>
                      {:else}
                        <span class="muted">—</span>
                      {/if}
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="muted">No packages found.</p>
              {/if}
            {/if}
          </div>
        </div>
      {/each}
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
      <h2>{editingName ? "Edit Registry" : "New Registry"}</h2>
      <FormField label="Domain" required error={formErrors.domain}>
        <input bind:value={form.domain} disabled={!!editingName} placeholder="my-domain" />
      </FormField>
      <FormField label="Repository" required error={formErrors.repository}>
        <input bind:value={form.repository} placeholder="npm" />
      </FormField>
      <FormField label="Namespace" hint="Optional, e.g. @scope" error={formErrors.namespace}>
        <input bind:value={form.namespace} placeholder="@my-org" />
      </FormField>
      <FormField label="Account ID" hint="12-digit AWS account" error={formErrors.account_id}>
        <input bind:value={form.account_id} placeholder="123456789012" maxlength="12" />
      </FormField>
      <FormField label="Profile" hint="Optional SSO profile name" error={formErrors.profile}>
        <input bind:value={form.profile} placeholder="my-profile" />
      </FormField>
      <FormField label="Region" required error={formErrors.region}>
        <input bind:value={form.region} placeholder="us-east-1" />
      </FormField>
      <div class="modal-actions">
        <button class="btn-secondary" onclick={() => (showModal = false)} disabled={saving}>Cancel</button>
        <button class="btn-primary" onclick={saveDomain} disabled={saving}>
          {#if saving}
            <span class="spinner-sm"></span> Saving…
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
    gap: 0.5rem;
  }
  .domain-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .domain-card {
    background: var(--bg-card, #1e1e1e);
    border: 1px solid var(--border-color, #333);
    border-radius: 8px;
    padding: 1rem;
  }
  .card-header {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-areas:
      "title actions"
      "meta status";
    gap: 0.5rem 1rem;
    align-items: center;
    margin-bottom: 0.75rem;
  }
  .domain-title {
    grid-area: title;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .card-meta {
    grid-area: meta;
    display: flex;
    gap: 1rem;
    font-size: 0.82rem;
  }
  .card-status {
    grid-area: status;
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-size: 0.82rem;
    justify-content: flex-end;
  }
  .card-actions {
    grid-area: actions;
    display: flex;
    gap: 0.3rem;
  }
  .badge {
    background: var(--accent, #2563eb);
    color: #fff;
    padding: 0.1rem 0.5rem;
    border-radius: 4px;
    font-size: 0.78rem;
  }
  .namespace {
    font-size: 0.85rem;
    color: var(--muted, #888);
  }
  .status-dot {
    color: #22c55e;
    font-size: 0.7rem;
  }
  .status-dot.dim {
    color: var(--muted, #888);
  }
  .section {
    border-top: 1px solid var(--border-color, #2a2a2a);
    padding-top: 0.6rem;
    margin-top: 0.6rem;
  }
  .section-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted, #888);
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .auth-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .auth-row select {
    background: var(--bg-input, #2a2a2a);
    color: var(--fg, #ddd);
    border: 1px solid var(--border-color, #333);
    border-radius: 4px;
    padding: 0.3rem 0.5rem;
    font-size: 0.85rem;
  }
  .registry-url {
    font-size: 0.75rem;
    color: var(--muted, #888);
    word-break: break-all;
  }
  .packages-list {
    padding: 0.5rem;
    background: var(--bg-input, #2a2a2a);
    border-radius: 4px;
    max-height: 200px;
    overflow-y: auto;
  }
  .pkg-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.15rem 0;
    font-size: 0.83rem;
  }
  .spinner-sm {
    width: 12px;
    height: 12px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    display: inline-block;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  .sso-banner {
    background: rgba(251, 191, 36, 0.1);
    border: 1px solid rgba(251, 191, 36, 0.4);
    border-radius: 6px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
  }
  .sso-banner-main {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
  }
  .sso-banner p {
    margin: 0.25rem 0 0 0;
    color: var(--text-muted, #888);
    font-size: 0.85rem;
  }
  .sso-spinner {
    margin-top: 0.2rem;
    color: #fbbf24;
  }
</style>
