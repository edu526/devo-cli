<script lang="ts">
  import { onMount } from "svelte";
  import { get } from "svelte/store";
  import {
    databasesApi,
    connectionsApi,
    hostsApi,
    profilesApi,
    type DatabaseRecord,
    type DatabaseIn,
    type ConnectionRecord,
    ApiError,
  } from "../lib/api";
  import { databasesCache, connectionsCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import ViewToggle from "../lib/ViewToggle.svelte";
  import FormField from "../lib/FormField.svelte";
  import { databaseSchema, validate, type DatabaseForm, type FieldErrors } from "../lib/forms";
  import { viewModes } from "../lib/stores";
  import { ws, type WsMessage } from "../lib/ws";
  import {
    isPermissionGranted,
    requestPermission,
    sendNotification,
  } from "@tauri-apps/plugin-notification";
  import { invoke } from "@tauri-apps/api/core";
  import { Settings, RefreshCw, X } from "@lucide/svelte";
  import { open as openUrl } from "@tauri-apps/plugin-shell";

  const viewMode = viewModes.databases;

  interface Row {
    name: string;
    db: DatabaseRecord;
    conn: ConnectionRecord | null;
  }

  const initialDatabases = get(databasesCache) ?? {};
  const initialConnections = (get(connectionsCache) ?? []) as ConnectionRecord[];

  let databases: Record<string, DatabaseRecord> = $state(initialDatabases);
  let connections: ConnectionRecord[] = $state(initialConnections);

  let loading = $state(Object.keys(initialDatabases).length === 0);
  let actionError: string | null = $state(null);
  let saving = $state(false);
  let deleting: Set<string> = $state(new Set());
  let busyConns: Set<string> = $state(new Set());
  let busyAll = $state(false);
  let query = $state("");
  let refreshing = $state(false);

  let ssoLoginInProgress = $state<{ profile: string; name: string } | null>(null);
  let ssoLoginError = $state<string | null>(null);
  let ssoLoginUnsubscribe: (() => void) | null = null;
  let ssoManualUrl = $state<{ url: string; code: string } | null>(null);

  function handleSsoRequired(profile: string, name: string) {
    ssoLoginInProgress = { profile, name };
    ssoLoginError = null;
    ssoManualUrl = null;
    // Subscribe once; the listener stays alive until cleared.
    // Filter by both profile and source so we don't react to SSO events
    // triggered by other features (codeartifact, etc.) — same pattern as RegistryPage.
    if (ssoLoginUnsubscribe) ssoLoginUnsubscribe();
    ssoLoginUnsubscribe = ws.on("sso.login.completed", (msg) => {
      const m = msg as { profile?: string; source?: string; success?: boolean; error?: string };
      if (m.source !== "profile" || m.profile !== profile) return;
      ssoLoginInProgress = null;
      ssoManualUrl = null;
      if (ssoLoginUnsubscribe) {
        ssoLoginUnsubscribe();
        ssoLoginUnsubscribe = null;
      }
      if (m.success) {
        // Auto-retry the original connection
        startOne(name);
      } else {
        ssoLoginError = m.error ?? "Browser SSO login failed";
      }
    });
    // Fire-and-forget: the backend runs aws sso login in a thread and emits
    // sso.login.completed when done. We only show an immediate error if the
    // API call itself fails (network error, etc.), not if SSO fails — that
    // arrives via the WS event above.
    profilesApi.refresh(profile).catch((e: unknown) => {
      // Only clear the banner if we get a hard API error (not a 202 Accepted).
      // A 202 means the login is running in the background — the WS event will arrive.
      if (e instanceof ApiError && e.status !== 202) {
        ssoLoginInProgress = null;
        ssoManualUrl = null;
        ssoLoginError = String(e);
      }
    });
  }

  // --- Hosts Sync Logic ---
  let settingUpHosts = $state(false);
  let missingHosts: string[] = $state([]);

  async function checkHosts() {
    try {
      const data = await hostsApi.setup();
      missingHosts = data.succeeded
        .filter((r: any) => r.action === "add" || r.action === "update")
        .map((r: any) => r.hostname);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        // We know hosts are missing because the backend needs elevation to fix them.
        // We set a dummy missing host to trigger the warning banner.
        missingHosts = ["_needs_elevation_"];
      } else {
        console.error("Failed to check hosts:", e);
      }
    }
  }

  async function syncHosts() {
    settingUpHosts = true;
    actionError = null;
    try {
      await hostsApi.setup();
      missingHosts = [];
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        try {
          // Optionally, if the backend sends `params: { db_names: [...] }`, we could append them:
          const detail = typeof e.detail === "string" ? JSON.parse(e.detail) : e.detail;
          const pythonBin = (detail && detail.params && detail.params.python_bin) ? detail.params.python_bin : "python";
          const configDir = (detail && detail.params && detail.params.config_dir) ? detail.params.config_dir : "";
          const useEnv = (detail && detail.params && detail.params.use_env) ? detail.params.use_env : false;

          let args = [];
          if (configDir && useEnv) {
            args.push("env", `DEVO_CONFIG_DIR=${configDir}`);
          }
          args.push(pythonBin, "-m", "cli_tool.cli", "ssm", "hosts", "setup");

          if (detail && detail.params && detail.params.db_names && detail.params.db_names.length > 0) {
            args.push(...detail.params.db_names);
          }

          await invoke("run_elevated", { args });
          // If the user approved the elevation, it successfully completed. Refresh the hosts status.
          await checkHosts();
          return;
        } catch (elevateErr) {
          actionError = elevateErr instanceof Error ? elevateErr.message : String(elevateErr);
          return;
        }
      }
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      settingUpHosts = false;
    }
  }

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

  const allRows = $derived<Row[]>(
    Object.entries(databases).map(([name, db]) => ({
      name,
      db,
      conn: connections.find((c) => c.name === name) ?? null,
    })),
  );

  const rows = $derived<Row[]>(
    query.trim()
      ? allRows.filter(
          (r) =>
            r.name.toLowerCase().includes(query.toLowerCase()) ||
            r.db.bastion.toLowerCase().includes(query.toLowerCase()) ||
            r.db.host.toLowerCase().includes(query.toLowerCase()) ||
            r.db.region.toLowerCase().includes(query.toLowerCase()),
        )
      : allRows,
  );

  const anyConnected = $derived(
    connections.some(
      (c) => c.state === "connected" || c.state === "connecting" || c.state === "starting",
    ),
  );

  async function load() {
    refreshing = true;
    try {
      const [dbData, connData] = await Promise.all([databasesApi.list(), connectionsApi.list()]);
      databases = dbData;
      connections = connData;
      databasesCache.set(dbData);
      connectionsCache.set(connData);
      await checkHosts();
    } catch (e) {
      actionError = String(e);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  // --- CRUD Logic ---
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
    form = {
      name,
      ...rec,
      profile: rec.profile ?? "",
      local_port: rec.local_port,
      local_address: rec.local_address ?? "127.0.0.1",
    };
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

  // --- Connection Logic ---
  async function startOne(name: string) {
    actionError = null;
    busyConns = new Set([...busyConns, name]);
    try {
      const result = await connectionsApi.start(name);
      if (result.state === "expired_credentials") {
        connections = [...connections.filter((c) => c.name !== name), result];
        if (result.sso_required && result.profile) {
          handleSsoRequired(result.profile, name);
        }
      }
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyConns = new Set([...busyConns].filter((n) => n !== name));
    }
  }

  async function restartOne(name: string) {
    actionError = null;
    busyConns = new Set([...busyConns, name]);
    try {
      await connectionsApi.stop(name);
      await new Promise((r) => setTimeout(r, 200));
      const result = await connectionsApi.start(name);
      if (result.state === "expired_credentials") {
        connections = [...connections.filter((c) => c.name !== name), result];
        if (result.sso_required && result.profile) {
          handleSsoRequired(result.profile, name);
        }
      }
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyConns = new Set([...busyConns].filter((n) => n !== name));
    }
  }

  async function stopOne(name: string) {
    actionError = null;
    busyConns = new Set([...busyConns, name]);
    try {
      await connectionsApi.stop(name);
      connections = connections.filter((c) => c.name !== name);
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyConns = new Set([...busyConns].filter((n) => n !== name));
    }
  }

  async function startAll() {
    actionError = null;
    busyAll = true;
    try {
      await connectionsApi.startAll();
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyAll = false;
    }
  }

  async function stopAll() {
    actionError = null;
    busyAll = true;
    try {
      await connectionsApi.stopAll();
      await load();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyAll = false;
    }
  }

  async function notifyUser(title: string, body: string) {
    try {
      let permissionGranted = await isPermissionGranted();
      if (!permissionGranted) {
        const permission = await requestPermission();
        permissionGranted = permission === "granted";
      }
      if (permissionGranted) {
        sendNotification({ title, body });
      }
    } catch (err) {
      console.error("Failed to send desktop notification:", err);
    }
  }

  onMount(() => {
    load();
    const offDb = ws.on("databases.sync", async () => {
      await load();
    });
    const offConns = ws.on("connections.sync", async () => {
      await load();
    });
    const offState = ws.on("connection.state_changed", (msg: WsMessage) => {
      const name = msg.name as string;
      const state = msg.state as ConnectionRecord["state"];
      const local_port = msg.local_port as number;
      const error = (msg.error as string) ?? null;

      if (state === "stopped") {
        connections = connections.filter((c) => c.name !== name);
      } else {
        const existing = connections.find((c) => c.name === name);
        if (existing) {
          connections = connections.map((c) =>
            c.name === name ? { ...c, state, local_port, error } : c,
          );
        } else {
          connections = [...connections, { name, state, local_port, error }];
        }

        if (
          state === "expired_credentials" &&
          (!existing || existing.state !== "expired_credentials")
        ) {
          notifyUser(
            "Connection Lost",
            `AWS SSO Token expired for ${name}. Please authenticate again.`,
          );
        } else if (state === "error" && (!existing || existing.state !== "error")) {
          notifyUser("Connection Error", error || `Connection to ${name} failed unexpectedly.`);
        }
      }
      connectionsCache.set(connections);
    });
    const offMetrics = ws.on("connection.metrics", (msg: WsMessage) => {
      const name = msg.name as string;
      const existing = connections.find((c) => c.name === name);
      if (!existing) return;
      connections = connections.map((c) =>
        c.name === name
          ? {
              ...c,
              uptime_seconds: (msg.uptime_seconds as number) ?? c.uptime_seconds,
              attempts: (msg.attempts as number) ?? c.attempts,
              last_error_at: (msg.last_error_at as number) ?? c.last_error_at,
            }
          : c,
      );
    });

    const offUrlReady = ws.on("sso.login.url_ready", (msg: WsMessage) => {
      const m = msg as { profile?: string; source?: string; url?: string; code?: string };
      if (
        m.source === "profile" &&
        ssoLoginInProgress &&
        m.profile === ssoLoginInProgress.profile
      ) {
        ssoManualUrl = { url: m.url!, code: m.code! };
      }
    });

    return () => {
      offDb();
      offConns();
      offState();
      offMetrics();
      offUrlReady();
    };
  });

  onMount(load);

  // --- Display Helpers ---
  function stateClass(state: string): string {
    if (state === "connected") return "badge-green";
    if (state === "error" || state === "expired_credentials") return "badge-red";
    if (state === "starting" || state === "connecting") return "badge-yellow";
    return "badge-gray";
  }

  function connState(row: Row): string {
    return row.conn?.state ?? "stopped";
  }

  function canStart(row: Row): boolean {
    const s = connState(row);
    return s === "stopped" || s === "error" || s === "expired_credentials";
  }

  function formatUptime(seconds: number | undefined): string {
    if (seconds === undefined || seconds === null) return "—";
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }
</script>

<div class="page">
  <div class="page-header">
    <h1>
      Databases {#if refreshing && !loading}<span class="refreshing-dot"></span>{/if}
    </h1>
    <div class="header-actions">
      <ViewToggle page="databases" />
      <SearchInput bind:value={query} placeholder="Filter databases…" />
      <div class="actions">
        {#if anyConnected}
          <button class="btn-secondary" onclick={stopAll} disabled={busyAll}>
            {#if busyAll}<span class="spinner-sm"></span>{/if}
            Stop All
          </button>
        {/if}
        <button class="btn-secondary" onclick={startAll} disabled={busyAll || allRows.length === 0}>
          {#if busyAll}<span class="spinner-sm"></span>{/if}
          Start All
        </button>
        <button class="btn-primary" onclick={openCreate}>
          <span class="btn-glyph">+</span> New Database
        </button>
      </div>
    </div>
  </div>
  {#if actionError && !actionError.startsWith("Delete database")}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if ssoLoginInProgress}
    <div class="alert-sso">
      <span class="spinner-sm spinner-sso"></span>
      <div>
        <strong>Browser SSO login in progress</strong> for <code>{ssoLoginInProgress.profile}</code>
        {#if ssoManualUrl}
          <p>
            Your browser could not be opened automatically. Please open
            <a
              href={ssoManualUrl.url}
              onclick={(e) => {
                e.preventDefault();
                if (ssoManualUrl) {
                  openUrl(ssoManualUrl.url);
                }
              }}
              class="sso-link">{ssoManualUrl.url}</a
            >
            {#if ssoManualUrl.code}
              and enter the code <strong>{ssoManualUrl.code}</strong>.
            {:else}
              to approve the request.
            {/if}
          </p>
        {:else}
          <p>
            Approve the request in the browser window that just opened. The connection to <strong
              >{ssoLoginInProgress.name}</strong
            > will retry automatically.
          </p>
        {/if}
      </div>
    </div>
  {/if}

  {#if ssoLoginError}
    <div class="alert-error">
      {ssoLoginError}
      <button class="dismiss" onclick={() => (ssoLoginError = null)}><X size={14} /></button>
    </div>
  {/if}

  {#if missingHosts.length > 0}
    <div
      class="alert-warning"
      style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"
    >
      <div>
        <strong>Missing local DNS mappings</strong>
        <br />
        <span class="muted"
          >Some connections require their hostname to be mapped to 127.0.0.X in your hosts file.</span
        >
      </div>
      <button class="btn-primary" onclick={syncHosts} disabled={settingUpHosts}>
        {#if settingUpHosts}<span class="spinner-sm"></span>{/if} Sync Hosts
      </button>
    </div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if allRows.length === 0}
    <div class="empty-state">
      <p>No databases configured.</p>
      <p class="muted">Add a database to create an SSM port-forwarding tunnel.</p>
      <button class="btn-primary" style="margin-top: 1rem" onclick={openCreate}>New Database</button
      >
    </div>
  {:else if rows.length === 0}
    <p class="muted">No databases match "{query}".</p>
  {:else if $viewMode === "table"}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>State</th>
            <th>Host</th>
            <th>Port</th>
            <th>Uptime</th>
            <th>Error</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row (row.name)}
            <tr>
              <td class="name">
                {row.name}
                <button
                  class="btn-icon"
                  onclick={() => openEdit(row.name, row.db)}
                  title="Edit configuration"><Settings size={14} /></button
                >
              </td>
              <td><span class="badge {stateClass(connState(row))}">{connState(row)}</span></td>
              <td class="host-cell truncate"><code>{row.db.host}</code></td>
              <td>{row.db.port} → {row.conn?.local_port ?? row.db.local_port ?? "auto"}</td>
              <td class="uptime-cell">{formatUptime(row.conn?.uptime_seconds)}</td>
              <td class="error-cell truncate">{row.conn?.error ?? ""}</td>
              <td class="actions-cell">
                <div class="actions-wrap">
                  {#if canStart(row)}
                    <button
                      class="btn-sm btn-primary"
                      onclick={() => startOne(row.name)}
                      disabled={busyConns.has(row.name) || busyAll}
                    >
                      {#if busyConns.has(row.name)}
                        <span class="spinner-sm"></span> Starting…
                      {:else}
                        Start
                      {/if}
                    </button>
                  {:else}
                    <button
                      class="btn-sm btn-secondary"
                      onclick={() => stopOne(row.name)}
                      disabled={busyConns.has(row.name) || busyAll}
                    >
                      {#if busyConns.has(row.name)}
                        <span class="spinner-sm"></span> Stopping…
                      {:else}
                        Stop
                      {/if}
                    </button>
                    <button
                      class="btn-sm btn-secondary"
                      onclick={() => restartOne(row.name)}
                      disabled={busyConns.has(row.name) || busyAll}
                      title="Restart"
                    >
                      <RefreshCw size={14} />
                    </button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="list-cards">
      {#each rows as row (row.name)}
        <div class="list-card">
          <div class="lc-main">
            <div class="lc-header">
              <span class="lc-title">{row.name}</span>
              <span class="badge {stateClass(connState(row))}">{connState(row)}</span>
              <button
                class="btn-icon lc-edit-btn"
                onclick={() => openEdit(row.name, row.db)}
                title="Edit configuration"><Settings size={14} /></button
              >
            </div>
            <div class="lc-meta">
              <span class="lc-meta-item">
                <span class="muted">Host:</span> <code>{row.db.host}</code>
              </span>
              <span class="lc-meta-sep">·</span>
              <span class="lc-meta-item">
                <span class="muted">Ports:</span>
                <code>{row.db.port} → {row.conn?.local_port ?? row.db.local_port ?? "auto"}</code>
              </span>
              <span class="lc-meta-sep">·</span>
              <span class="lc-meta-item">
                <span class="muted">Uptime:</span>
                {formatUptime(row.conn?.uptime_seconds)}
              </span>
            </div>
            {#if row.conn?.error}
              <div class="lc-error">{row.conn.error}</div>
            {/if}
          </div>
          <div class="lc-actions">
            {#if canStart(row)}
              <button
                class="btn-primary"
                onclick={() => startOne(row.name)}
                disabled={busyConns.has(row.name) || busyAll}
              >
                Start
              </button>
            {:else}
              <button
                class="btn-secondary"
                onclick={() => stopOne(row.name)}
                disabled={busyConns.has(row.name) || busyAll}
              >
                Stop
              </button>
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
      <h2>{editingName ? "Edit Database" : "New Database"}</h2>

      {#if actionError && !actionError.startsWith("Delete database")}
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

      <div class="modal-actions" style="justify-content: space-between;">
        {#if editingName}
          <button
            class="btn-danger"
            onclick={() => remove(editingName!)}
            disabled={saving || deleting.has(editingName)}
          >
            {#if deleting.has(editingName)}<span class="spinner-sm"></span>{/if} Delete
          </button>
        {:else}
          <div></div>
        {/if}

        <div style="display: flex; gap: 0.5rem;">
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
  </div>
{/if}

<style>
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .host-cell {
    max-width: 220px;
  }
  .error-cell {
    max-width: 200px;
    color: #f87171;
    font-size: 0.8rem;
  }
  .uptime-cell {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.78rem;
    color: #94a3b8;
    white-space: nowrap;
  }
  .btn-icon {
    background: none;
    border: none;
    cursor: pointer;
    opacity: 0.6;
    padding: 2px 4px;
    transition: opacity 0.2s;
    font-size: 0.9rem;
  }
  .btn-icon:hover {
    opacity: 1;
  }
  .lc-edit-btn {
    margin-left: 0.25rem;
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

  .lc-error {
    color: var(--danger);
    font-size: 0.85rem;
    background: color-mix(in srgb, var(--danger) 10%, transparent);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    display: inline-block;
    margin-top: 0.25rem;
  }

  .lc-actions {
    flex-shrink: 0;
    margin-left: 1rem;
    display: flex;
    gap: 0.5rem;
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
    margin-bottom: 1rem;
  }
  .alert-sso strong {
    display: block;
    margin-bottom: 0.2rem;
  }
  .alert-sso p {
    margin: 0;
    color: #a08020;
    font-size: 0.85rem;
  }
  .alert-sso code {
    color: #fde68a;
  }
  .alert-sso a {
    word-break: break-all;
    overflow-wrap: anywhere;
    color: #fbbf24;
    text-decoration: underline;
  }
  .spinner-sso {
    margin-top: 3px;
    flex-shrink: 0;
  }
</style>
