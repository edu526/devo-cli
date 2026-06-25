<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { get } from "svelte/store";
  import {
    connectionsApi,
    databasesApi,
    type ConnectionRecord,
    type DatabaseRecord,
    ApiError,
  } from "../lib/api";
  import { connectionsCache, databasesCache } from "../lib/page-stores";
  import { ws, type WsMessage } from "../lib/ws";
  import SearchInput from "../lib/SearchInput.svelte";

  interface Row {
    name: string;
    db: DatabaseRecord;
    conn: ConnectionRecord | null;
  }

  const initialDatabases = (get(databasesCache) ?? {}) as Record<string, DatabaseRecord>;
  const initialConnections = (get(connectionsCache) ?? []) as ConnectionRecord[];
  let databases: Record<string, DatabaseRecord> = $state(initialDatabases);
  let connections: ConnectionRecord[] = $state(initialConnections);
  let loading = $state(Object.keys(initialDatabases).length === 0);
  let refreshing = $state(false);
  let actionError: string | null = $state(null);
  let busyConns: Set<string> = $state(new Set());
  let busyAll = $state(false);
  let query = $state("");

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
            r.db.host.toLowerCase().includes(query.toLowerCase()),
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
    } catch (e) {
      actionError = String(e);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function startOne(name: string) {
    actionError = null;
    busyConns = new Set([...busyConns, name]);
    try {
      const result = await connectionsApi.start(name);
      // Optimistic: show "starting" immediately; WS will push the real state
      connections = [...connections.filter((c) => c.name !== name), result];
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
      // Optimistic: remove from active connections; WS will confirm
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

  // WS: update individual connection state in-place without a full reload
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
      } else if (state === "error" || state === "expired_credentials") {
        connections = [...connections, { name, state, local_port, error }];
      }
    }
    connectionsCache.set(connections);
  });

  // WS: live metrics (uptime, attempts, last error timestamp)
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

  onDestroy(() => {
    offState();
    offMetrics();
  });

  onMount(load);

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
      Connections {#if refreshing && !loading}<span class="refreshing-dot"></span>{/if}
    </h1>
    <div class="header-actions">
      <SearchInput bind:value={query} placeholder="Filter connections…" />
      <div class="actions">
        {#if anyConnected}
          <button class="btn-secondary" onclick={stopAll} disabled={busyAll}>
            {#if busyAll}<span class="spinner-sm"></span>{/if}
            Stop All
          </button>
        {/if}
        <button class="btn-primary" onclick={startAll} disabled={busyAll}>
          {#if busyAll}<span class="spinner-sm"></span>{/if}
          Start All
        </button>
      </div>
    </div>
  </div>

  {#if actionError}
    <div class="alert-error">{actionError}</div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else if allRows.length === 0}
    <div class="empty-state">
      <p>No databases configured.</p>
      <p class="muted">Add a database in the <strong>Databases</strong> section first.</p>
    </div>
  {:else if rows.length === 0}
    <p class="muted">No connections match "{query}".</p>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>State</th>
            <th>Host</th>
            <th>Local Port</th>
            <th>Uptime</th>
            <th>Error</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row (row.name)}
            <tr>
              <td class="name">{row.name}</td>
              <td><span class="badge {stateClass(connState(row))}">{connState(row)}</span></td>
              <td class="host-cell truncate"><code>{row.db.host}</code></td>
              <td>{row.conn?.local_port ?? row.db.local_port ?? "auto"}</td>
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
                      onclick={() => startOne(row.name)}
                      disabled={busyConns.has(row.name) || busyAll}
                      title="Restart"
                    >
                      ↻
                    </button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
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
</style>
