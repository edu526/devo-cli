<script lang="ts">
  import { onMount } from "svelte";
  import {
    codeartifactApi,
    ApiError,
    type CodeArtifactDomain,
    type CodeArtifactToken,
    type CodeArtifactLoginResult,
  } from "../lib/api";
  import { askConfirm } from "../lib/confirm";
  import FormField from "../lib/FormField.svelte";
  import ViewToggle from "../lib/ViewToggle.svelte";
  import SearchInput from "../lib/SearchInput.svelte";
  import RowMenu, { type RowMenuItem } from "../lib/RowMenu.svelte";
  import { viewModes } from "../lib/stores";
  import {
    codeartifactDomainSchema,
    validate,
    type CodeArtifactDomainForm,
    type FieldErrors,
  } from "../lib/forms";
  import { CircleDot, Circle } from "@lucide/svelte";
  import { get } from "svelte/store";
  import { registryCache } from "../lib/page-stores";
  import { defaultTool } from "../lib/codeartifact";
  import { ensureLogin } from "../lib/login-flow";


  const viewMode = viewModes.registry;

  const configExample = `{ "domain": "my-domain", "repository": "npm", "namespace": "@scope", "account_id": "123456789012", "profile": "my-profile", "region": "us-east-1" }`;

  const initialCache = get(registryCache);
  let domains: CodeArtifactDomain[] = $state(initialCache?.domains ?? []);
  let tokens: CodeArtifactToken[] = $state(initialCache?.tokens ?? []);
  let query = $state("");

  const filteredDomains = $derived(
    domains.filter(
      (d) =>
        d.domain.toLowerCase().includes(query.toLowerCase()) ||
        (d.namespace && d.namespace.toLowerCase().includes(query.toLowerCase())) ||
        d.repository.toLowerCase().includes(query.toLowerCase()),
    ),
  );
  let loading = $state(!initialCache);
  let actionError: string | null = $state(null);
  let busyDomains: Record<string, boolean> = $state({});
  let busyAll = $state(false);
  let packagesOpen: Record<string, boolean> = $state({});
  let packagesData: Record<string, [string, string | null][]> = $state({});
  let loadingPackages: string | null = $state(null);
  // Set before the first render: a <select> bound to a missing key writes its
  // first option (npm) back, which `load()` would then keep.
  let toolSelections: Record<string, string> = $state(
    Object.fromEntries((initialCache?.domains ?? []).map((d) => [d.domain, defaultTool(d, initialCache?.tokens ?? [])])),
  );
  let deleting: Record<string, boolean> = $state({});

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

  function domainMenu(domain: CodeArtifactDomain): RowMenuItem[] {
    return [
      { label: "Edit", onselect: () => openEdit(domain) },
      {
        label: "Delete registry…",
        onselect: () => removeDomain(domain),
        danger: true,
        disabled: deleting[domain.domain],
      },
    ];
  }

  function toolFor(domain: CodeArtifactDomain): string {
    return toolSelections[domain.domain] ?? defaultTool(domain, tokens);
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
      registryCache.set({ domains: d, tokens: t });
      for (const dom of domains) {
        if (!(dom.domain in toolSelections)) {
          toolSelections[dom.domain] = defaultTool(dom, t);
        }
      }
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function doLogin(domain: CodeArtifactDomain, { afterLogin = false } = {}) {
    actionError = null;
    busyDomains = { ...busyDomains, [domain.domain]: true };
    const tool = toolFor(domain);
    try {
      const result = await codeartifactApi.login(domain.domain, tool);
      // No AWS credentials for its profile: get them through the shared login
      // (the banner shows it; domains of one profile share it), then retry once.
      if ("status" in result && result.status === "sso_required") {
        if (afterLogin) {
          actionError = `${domain.domain} still has no AWS credentials after logging in.`;
        } else if ((await ensureLogin([result.profile])).has(result.profile)) {
          await doLogin(domain, { afterLogin: true });
        }
        return;
      }
      tokens = await codeartifactApi.tokens();
      loginCache[domain.domain] = result as CodeArtifactLoginResult;
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyDomains = { ...busyDomains, [domain.domain]: false };
    }
  }

  async function loginAll() {
    busyAll = true;
    actionError = null;
    try {
      await Promise.allSettled(domains.map((d) => doLogin(d)));
    } finally {
      busyAll = false;
    }
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
    form = {
      domain: "",
      repository: "",
      namespace: "",
      account_id: "",
      profile: "",
      region: "us-east-1",
    };
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
    const confirmed = await askConfirm({
      title: "Delete registry?",
      message: `"${domain.domain}" is removed from Devo. Active tokens are not invalidated.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!confirmed) return;
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

  onMount(() => {
    load();
  });
</script>

<div class="page">
  <div class="page-header">
    <h1>Registry</h1>
    <div class="header-actions">
      <ViewToggle page="registry" />
      <SearchInput bind:value={query} placeholder="Filter registries…" />
      <div class="actions">
        <button
          class="btn-secondary"
          onclick={loginAll}
          disabled={loading || busyAll || domains.length === 0}
        >
          {#if busyAll}<span class="spinner-sm"></span>{/if} Refresh All
        </button>
        <button class="btn-primary" onclick={openCreate}>
          <span class="btn-glyph">+</span> New Registry
        </button>
      </div>
    </div>
  </div>

  {#if actionError}
    <div class="alert-error">{actionError}</div>
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
  {:else if $viewMode === "table"}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Domain</th>
            <th>Repository</th>
            <th>Status</th>
            <th>Account / Region</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredDomains as domain (domain.domain)}
            {@const tool = toolFor(domain)}
            {@const token = tokenFor(domain.domain, tool)}
            {@const isLoggedIn = !!token}
            <tr>
              <td class="name">
                {domain.domain}
                {#if domain.namespace}<code class="namespace" style="margin-left:8px"
                    >{domain.namespace}</code
                  >{/if}
              </td>
              <td><span class="badge badge-gray">{domain.repository}</span></td>
              <td>
                {#if isLoggedIn}
                  <span class="status-dot" aria-hidden="true" style="display:inline-flex"
                    ><CircleDot size={10} strokeWidth={3} /></span
                  >
                  <span class="status-text">Connected</span>
                {:else}
                  <span class="status-dot dim" aria-hidden="true" style="display:inline-flex"
                    ><Circle size={10} strokeWidth={3} /></span
                  >
                  <span class="status-text muted">Not connected</span>
                {/if}
              </td>
              <td><span class="muted">{domain.account_id || "auto"} · {domain.region}</span></td>
              <td class="actions-cell">
                <div class="actions-wrap">
                  <select bind:value={toolSelections[domain.domain]} class="select-tool">
                    <option value="npm">npm</option>
                    <option value="pip">pip</option>
                    <option value="twine">twine</option>
                  </select>
                  <button
                    class="btn-sm btn-primary"
                    onclick={() => doLogin(domain)}
                    disabled={busyDomains[domain.domain] || busyAll}
                  >
                    {#if busyDomains[domain.domain]}
                      <span class="spinner-sm"></span>
                    {/if}
                    {isLoggedIn ? "Refresh Token" : "Login"}
                  </button>
                  <RowMenu label="More actions for {domain.domain}" items={domainMenu(domain)} />
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="domain-list">
      {#each filteredDomains as domain (domain.domain)}
        {@const tool = toolFor(domain)}
        {@const token = tokenFor(domain.domain, tool)}
        {@const isLoggedIn = !!token}
        <div class="domain-card" class:logged-in={isLoggedIn}>
          <div class="card-header">
            <div class="domain-title">
              <strong>{domain.domain}</strong>
              <span class="badge badge-gray">{domain.repository}</span>
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
                <span class="status-dot" aria-hidden="true" style="display:inline-flex"
                  ><CircleDot size={10} strokeWidth={3} /></span
                >
                <span class="muted">Connected via {tool}</span>
                {#if formatExpiry(token!.expires_at)}
                  <span class="muted">· {formatExpiry(token!.expires_at)}</span>
                {/if}
              {:else}
                <span class="status-dot dim" aria-hidden="true" style="display:inline-flex"
                  ><Circle size={10} strokeWidth={3} /></span
                >
                <span class="muted">Not connected</span>
              {/if}
            </div>
            <div class="card-actions">
              <RowMenu label="More actions for {domain.domain}" items={domainMenu(domain)} />
            </div>
          </div>

          <div class="section">
            <div class="section-title">Authentication</div>
            <div class="auth-row">
              <select bind:value={toolSelections[domain.domain]} class="select-tool">
                <option value="npm">npm</option>
                <option value="pip">pip</option>
                <option value="twine">twine</option>
              </select>
              <button
                class="btn-primary"
                onclick={() => doLogin(domain)}
                disabled={busyDomains[domain.domain] || busyAll}
              >
                {#if busyDomains[domain.domain]}
                  <span class="spinner-sm"></span>
                {/if}
                {isLoggedIn ? "Refresh Token" : "Login"}
              </button>
              {#if token}
                <span class="muted"
                  >Registry: <code class="registry-url">{token.registry_url}</code></span
                >
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
  <div class="modal-backdrop" role="presentation">
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
        <button class="btn-secondary" onclick={() => (showModal = false)} disabled={saving}
          >Cancel</button
        >
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
  .domain-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .domain-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    transition: all 0.2s ease;
  }
  .domain-card:hover {
    background: var(--bg-surface-2);
    border-color: var(--border-strong);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
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
    justify-content: flex-end;
  }
  .namespace {
    font-size: 0.85rem;
    color: var(--text-muted);
  }
  .status-dot {
    color: var(--success);
    font-size: 0.7rem;
  }
  .status-dot.dim {
    color: var(--text-faint);
  }
  .section {
    border-top: 1px solid var(--border);
    padding-top: 0.6rem;
    margin-top: 0.6rem;
  }
  .section-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
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
    background: var(--bg-surface-2);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.3rem 0.5rem;
    font-size: 0.85rem;
  }
  .registry-url {
    font-size: 0.75rem;
    color: var(--text-muted);
    word-break: break-all;
  }
  .packages-list {
    padding: 0.5rem;
    background: var(--bg-surface-2);
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
  .select-tool {
    background: var(--bg-surface-2);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
  }
  .select-tool option {
    background: var(--bg-surface-2);
    color: var(--text-primary);
  }
</style>
