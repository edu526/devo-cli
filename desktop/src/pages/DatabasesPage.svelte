<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { get } from "svelte/store";
  import {
    databasesApi,
    connectionsApi,
    hostsApi,
    profilesApi,
    type DatabaseRecord,
    type DatabaseIn,
    type ConnectionRecord,
    type ProfileRecord,
    type HostnameForwardingStatus,
    type InstanceRecord,
    type DiscoveredDatabase,
    instancesApi,
    ApiError,
  } from "../lib/api";
  import { withHostsElevation } from "../lib/hosts-elevation";
  import { askConfirm } from "../lib/confirm";
  import { databasesCache, connectionsCache, profilesCache, instancesCache } from "../lib/page-stores";
  import SearchInput from "../lib/SearchInput.svelte";
  import ViewToggle from "../lib/ViewToggle.svelte";
  import FormField from "../lib/FormField.svelte";
  import SearchableSelect from "../lib/SearchableSelect.svelte";
  import RowMenu, { type RowMenuItem } from "../lib/RowMenu.svelte";
  import { databaseSchema, regionFromHost, validate, type DatabaseForm, type FieldErrors } from "../lib/forms";
  import { viewModes } from "../lib/stores";
  import { ws, type WsMessage } from "../lib/ws";
  import { notifyUser } from "../lib/notifications";
  import { explainError, stateLabel } from "../lib/connection-status";
  import { copyToClipboard } from "../lib/clipboard";
  import { X, Link2, Link2Off, Copy, Check } from "@lucide/svelte";
  import { open as openUrl } from "@tauri-apps/plugin-shell";

  const viewMode = viewModes.databases;

  interface Row {
    name: string;
    db: DatabaseRecord;
    conn: ConnectionRecord | null;
  }

  const initialDatabases = get(databasesCache) ?? {};
  const initialConnections = (get(connectionsCache) ?? []) as ConnectionRecord[];
  const initialProfiles = (get(profilesCache) ?? []) as ProfileRecord[];

  let databases: Record<string, DatabaseRecord> = $state(initialDatabases);
  let connections: ConnectionRecord[] = $state(initialConnections);
  let profiles: ProfileRecord[] = $state(initialProfiles);

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

  // --- Hostname forwarding (hosts file) ---
  let forwarding = $state<HostnameForwardingStatus | null>(null);
  let settingUpHosts = $state(false);
  // "*" while the switch for all databases changes, else the database's name
  let changingForwarding = $state<string | null>(null);
  const missingHosts = $derived(forwarding?.missing ?? []);
  // Hostnames Devo still maps but no forwarded database uses (deleted, host changed…)
  const staleHosts = $derived(forwarding?.stale ?? []);
  // Databases on the same 127.0.0.X:port: one hostname can reach the other's tunnel
  const sharedAddresses = $derived(forwarding?.shared ?? []);

  function errorText(e: unknown): string {
    return e instanceof Error ? e.message : String(e);
  }

  async function refreshForwarding() {
    try {
      forwarding = await hostsApi.status();
    } catch (e) {
      console.error("Failed to check hosts:", e);
    }
  }

  async function syncHosts() {
    // Tunnels of databases sharing an IP and port are restarted: one of them
    // moves to its own IP, and the forwarder rule they shared may point at
    // either tunnel.
    const running = sharedAddresses.flatMap((s) => s.databases).filter(isRunning);
    settingUpHosts = true;
    actionError = null;
    try {
      await Promise.all(running.map((n) => connectionsApi.stop(n).catch(() => {})));
      await withHostsElevation(() => hostsApi.sync());
    } catch (e) {
      actionError = errorText(e);
    } finally {
      await refreshForwarding();
      for (const name of running) await startOne(name);
      settingUpHosts = false;
    }
  }

  function isRunning(name: string): boolean {
    const conn = connections.find((c) => c.name === name);
    return conn !== undefined && !isStopped(conn.state);
  }

  /**
   * Apply a hostname-forwarding change. Running tunnels of `affected` are
   * restarted so they listen where the new setting says (the hostname's
   * loopback IP, or 127.0.0.1); they are stopped before the hosts file changes,
   * so mapping a hostname back doesn't find its old port taken.
   */
  async function changeForwarding(
    key: string,
    affected: string[],
    apply: () => Promise<HostnameForwardingStatus>,
  ) {
    const running = affected.filter(isRunning);
    changingForwarding = key;
    actionError = null;
    try {
      await Promise.all(running.map((n) => connectionsApi.stop(n).catch(() => {})));
      forwarding = await withHostsElevation(apply);
    } catch (e) {
      actionError = errorText(e);
      await refreshForwarding();
    } finally {
      // also when it failed or the admin prompt was cancelled: leave them as they were
      for (const name of running) await startOne(name);
      changingForwarding = null;
    }
  }

  async function toggleAllForwarding() {
    if (!forwarding) return;
    const enable = !forwarding.enabled;
    if (
      !enable &&
      !(await askConfirm({
        title: "Pause hostname forwarding?",
        message:
          "Devo removes its entries from your hosts file, so database hostnames resolve " +
          "through normal DNS again (e.g. over a VPN). Tunnels keep working on 127.0.0.1.\n\n" +
          "Needs administrator rights.",
        confirmLabel: "Pause",
      }))
    ) {
      return;
    }
    // "All" means all: the ones that were an exception change too.
    const changing = Object.keys(databases).filter((n) => forwarded(n) !== enable);
    await changeForwarding("*", changing, () => hostsApi.setForwarding(enable));
  }

  async function toggleDbForwarding(name: string) {
    // Works whatever the setting for all is: e.g. just this one while the rest is paused.
    await changeForwarding(name, [name], () => hostsApi.setDatabaseForwarding(name, !forwarded(name)));
  }

  function forwardingTitle(name: string): string {
    return forwarded(name)
      ? "Hostname forwarding on: its hostname points at the tunnel. Click to pause it for this database"
      : "Hostname forwarding paused: its hostname resolves through normal DNS and the tunnel runs on 127.0.0.1. Click to forward it";
  }

  /** Whether the hostname points at the tunnel (assumed while loading). */
  function forwarded(name: string): boolean {
    return forwarding?.databases[name]?.enabled !== false;
  }

  /** Databases forwarded while forwarding is paused for all. */
  const forwardedExceptions = $derived(
    forwarding && !forwarding.enabled
      ? Object.keys(databases).filter((n) => forwarding?.databases[n]?.enabled)
      : [],
  );

  function localEndpoint(row: Row): string {
    const port = row.conn?.local_port ?? row.db.local_port ?? "auto";
    return forwarded(row.name) ? String(port) : `127.0.0.1:${port}`;
  }

  /**
   * Where a SQL client connects: the database's own host and port while its
   * hostname is forwarded, else the local tunnel.
   */
  function connectAddress(row: Row): string {
    return forwarded(row.name) ? `${row.db.host}:${row.db.port}` : localEndpoint(row);
  }

  let copiedName: string | null = $state(null);
  let copiedTimer: ReturnType<typeof setTimeout> | null = null;

  async function copyAddress(row: Row) {
    await copyToClipboard(connectAddress(row));
    copiedName = row.name;
    if (copiedTimer !== null) clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => (copiedName = null), 1500);
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
  });
  let formErrors: FieldErrors<DatabaseForm> = $state({});
  // Assigned by Devo when it maps the hostname: shown, never edited.
  let editingLocalAddress = $state("127.0.0.1");

  // --- Bastion: the instances saved in Instances, or a typed instance ID ---
  let instances: Record<string, InstanceRecord> = $state(get(instancesCache) ?? {});
  const bastionOptions = $derived(
    Object.entries(instances).map(([name, i]) => ({ value: i.instance_id, label: `${name} (${i.instance_id})` })),
  );

  async function loadInstances() {
    try {
      instances = await instancesApi.list();
      instancesCache.set(instances);
    } catch {
      // best effort: the instance ID can still be typed
    }
  }

  function pickBastion(id: string) {
    form.bastion = id;
    // A saved bastion knows its account: use its profile and region.
    const saved = Object.values(instances).find((i) => i.instance_id === id);
    if (saved?.profile) form.profile = saved.profile;
    if (saved?.region && !regionFromHost(form.host)) form.region = saved.region;
  }

  // --- Remote host: the RDS databases the profile can see, or a typed host ---
  let discovered: DiscoveredDatabase[] = $state([]);
  let discoveryLoading = $state(false);
  let discoveryError: string | null = $state(null);
  const discoveryCache = new Map<string, { databases: DiscoveredDatabase[]; error: string | null }>();
  let discoverySeq = 0;
  const hostOptions = $derived(discovered.map((d) => ({ value: d.host, label: d.host })));

  async function discover(region: string, profile: string) {
    const key = `${profile}|${region}`;
    const seq = ++discoverySeq;
    const cached = discoveryCache.get(key);
    if (cached) {
      discovered = cached.databases;
      discoveryError = cached.error;
      return;
    }
    discoveryLoading = true;
    discoveryError = null;
    try {
      const result = await databasesApi.discover(region, profile);
      if (!result.error) discoveryCache.set(key, result); // retry errors (e.g. after logging in)
      if (seq !== discoverySeq) return;
      discovered = result.databases;
      discoveryError = result.error;
    } catch (e) {
      if (seq !== discoverySeq) return;
      discovered = [];
      discoveryError = errorText(e);
    } finally {
      if (seq === discoverySeq) discoveryLoading = false;
    }
  }

  // List the databases once a profile and a region are known (typing debounced).
  $effect(() => {
    const region = form.region.trim();
    const profile = form.profile ?? "";
    if (!showModal || !region || !profile) {
      discovered = [];
      discoveryError = null;
      return;
    }
    const timer = setTimeout(() => void discover(region, profile), 400);
    return () => clearTimeout(timer);
  });

  function pickHost(host: string) {
    form.host = host;
    const found = discovered.find((d) => d.host === host);
    if (found?.port) form.port = found.port;
    const region = regionFromHost(host);
    if (region) form.region = region;
  }

  const hostHint = $derived.by(() => {
    if (!form.profile) return "Pick a profile (or a saved bastion) to list its databases";
    if (discoveryLoading) return `Looking for databases (${form.profile} · ${form.region})…`;
    if (discoveryError) return discoveryError;
    const n = discovered.length;
    return `${n} database${n === 1 ? "" : "s"} found (${form.profile} · ${form.region}), or type the host`;
  });

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
      // Profiles list is best-effort — a failure here must not block the
      // page or block opening the DB edit modal.
      const profilePromise = profilesApi.list()
        .then((p) => {
          profiles = p;
          profilesCache.set(p);
        })
        .catch(() => {});
      const [dbData, connData] = await Promise.all([databasesApi.list(), connectionsApi.list()]);
      databases = dbData;
      connections = connData;
      databasesCache.set(dbData);
      connectionsCache.set(connData);
      await profilePromise;
      await refreshForwarding();
    } catch (e) {
      actionError = String(e);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  // Options for the AWS profile autocomplete in the DB edit modal.
  // Includes any value currently in the form (e.g. a profile loaded from
  // disk that no longer appears in the live profiles list) so existing
  // configs don't visually lose their value when the modal opens.
  const profileOptions = $derived.by(() => {
    const opts = profiles.map((p) => ({ value: p.name, label: p.name }));
    if (form.profile && !opts.some((o) => o.value === form.profile)) {
      opts.unshift({ value: form.profile, label: form.profile });
    }
    return opts;
  });

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
    };
    editingLocalAddress = "127.0.0.1";
    formErrors = {};
    actionError = null;
    showModal = true;
    void loadInstances();
  }

  function openEdit(name: string, rec: DatabaseRecord) {
    editingName = name;
    form = {
      name,
      bastion: rec.bastion,
      host: rec.host,
      port: rec.port,
      region: rec.region,
      profile: rec.profile ?? "",
      local_port: rec.local_port,
    };
    editingLocalAddress = rec.local_address ?? "127.0.0.1";
    formErrors = {};
    actionError = null;
    showModal = true;
    void loadInstances();
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
    // No local_address: Devo keeps the one it assigned (or assigns one).
    const body: DatabaseIn = {
      bastion: v.data.bastion,
      host: v.data.host,
      port: v.data.port,
      region: v.data.region,
      profile: v.data.profile || undefined,
      local_port: v.data.local_port,
    };
    const oldName = editingName;
    const renamed = oldName !== null && v.data.name !== oldName;
    // Its tunnel is tracked by name: stop it to rename, start it again after.
    const restart = renamed && isRunning(oldName);
    try {
      if (restart) await connectionsApi.stop(oldName);
      if (oldName) {
        await databasesApi.update(oldName, renamed ? { ...body, name: v.data.name } : body);
      } else {
        await databasesApi.create(v.data.name, body);
      }
      showModal = false;
      await load();
      if (restart) await startOne(v.data.name);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : String(e);
      if (restart && oldName) await startOne(oldName); // the rename failed: leave it as it was
      actionError = message; // after startOne, which clears it
    } finally {
      saving = false;
    }
  }

  async function remove(name: string) {
    const confirmed = await askConfirm({
      title: "Delete database?",
      message: `"${name}" is removed from Devo's configuration.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!confirmed) return;
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
      const results = await connectionsApi.startAll();
      await load();
      const waiting = results.filter((r) => r.sso_required && r.profile);
      if (waiting.length > 0) loginThenStart(waiting.map((r) => [r.name, r.profile!]));
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : String(e);
    } finally {
      busyAll = false;
    }
  }

  let offStartAllLogin: (() => void) | null = null;

  /**
   * Start All found tunnels whose credentials expired: one login for their
   * profiles (each SSO session logs in once, however many tunnels share it),
   * then start the ones whose profile got new credentials. Before, they were
   * left on "Login needed" although the user had asked to start them.
   */
  function loginThenStart(tunnels: [name: string, profile: string][]) {
    offStartAllLogin?.();
    offStartAllLogin = ws.on("profile.refreshed", (msg: WsMessage) => {
      offStartAllLogin?.();
      offStartAllLogin = null;
      if (!msg.success) return;
      const renewed = new Set((msg.names as string[] | undefined) ?? []);
      for (const [name, profile] of tunnels) if (renewed.has(profile)) void startOne(name);
    });
    const profiles = [...new Set(tunnels.map(([, profile]) => profile))];
    profilesApi.refreshAll(false, { allowBrowser: true, targets: { profiles, sessions: [] } }).catch((e: unknown) => {
      offStartAllLogin?.();
      offStartAllLogin = null;
      actionError = e instanceof ApiError ? e.message : String(e);
    });
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

        // Expired credentials are not announced here: the sidecar's login
        // handler renews silently when it can and, only when a browser login
        // is really needed, the app-wide login watcher shows one notification
        // per SSO session (no matter how many tunnels share it).
        if (state === "error" && (!existing || existing.state !== "error")) {
          notifyUser("Connection Error", error || `Connection to ${name} failed unexpectedly.`);
        } else if (state === "connected" && existing?.state === "expired_credentials") {
          // The credentials were renewed (silently or after a login) and the
          // tunnel is back up without the user having to do anything here.
          notifyUser("Reconnected", `${name} is back online after the SSO refresh.`);
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

    // Backend-triggered auto-refresh for a connection whose tokens expired
    // mid-session (see connection_service._ensure_single_connection_sso_login).
    // Unlike handleSsoRequired's one-shot listener, this must stay subscribed
    // for the page's whole lifetime since the backend can fire it at any time
    // without the user having clicked anything.
    const offConnSsoCompleted = ws.on("sso.login.completed", (msg: WsMessage) => {
      const m = msg as { profile?: string; source?: string; success?: boolean; error?: string };
      if (m.source !== "connection" || !m.profile) return;
      if (!m.success) {
        notifyUser(
          "AWS SSO Refresh Failed",
          m.error || `Automatic SSO refresh for '${m.profile}' failed. Reconnect manually once you've logged in.`,
        );
      }
    });

    return () => {
      offDb();
      offConns();
      offState();
      offMetrics();
      offUrlReady();
      offConnSsoCompleted();
    };
  });

  // Without this, navigating away while an SSO login is in flight would
  // leave the listener registered in ws.handlers — a late sso.login.completed
  // event would then call startOne(name) on a component that's no longer
  // mounted (or one the user already left).
  onDestroy(() => {
    ssoLoginUnsubscribe?.();
    offStartAllLogin?.();
  });

  // --- Display Helpers ---
  function stateClass(state: string): string {
    if (state === "connected") return "badge-green";
    if (state === "error") return "badge-red";
    if (state === "expired_credentials") return "badge-yellow";
    if (state === "reconnecting") return "badge-blue";
    if (state === "starting" || state === "connecting") return "badge-yellow";
    return "badge-gray";
  }

  function connState(row: Row): string {
    return row.conn?.state ?? "stopped";
  }

  function isStopped(state: string): boolean {
    return state === "stopped" || state === "error" || state === "expired_credentials";
  }

  function canStart(row: Row): boolean {
    return isStopped(connState(row));
  }

  /** A database's less frequent actions, labeled, in its "⋯" menu. */
  function dbMenu(row: Row): RowMenuItem[] {
    const busy = busyConns.has(row.name) || busyAll;
    return [
      { label: "Edit…", onselect: () => openEdit(row.name, row.db) },
      ...(canStart(row) ? [] : [{ label: "Restart tunnel", onselect: () => restartOne(row.name), disabled: busy }]),
      { label: "Delete database…", onselect: () => remove(row.name), danger: true, disabled: deleting.has(row.name) },
    ];
  }

  /** Starting a tunnel whose credentials expired opens the login first. */
  function startLabel(row: Row, compact = false): string {
    if (connState(row) !== "expired_credentials") return "Start";
    return compact ? "Log in" : "Log in & connect";
  }

  /** What to tell the user under a tunnel: its error explained, or why it's waiting. */
  function problemOf(row: Row): { summary: string; detail: string | null } | null {
    const state = connState(row);
    if (state === "expired_credentials") {
      const profile = row.db.profile ?? "default";
      return { summary: `The AWS credentials of profile "${profile}" expired. Log in to connect.`, detail: null };
    }
    const explained = explainError(row.conn?.error);
    if (!explained) return null;
    if (state === "reconnecting") return { ...explained, summary: `Reconnecting: ${explained.summary}` };
    return explained;
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

{#snippet problemNote(state: string, problem: { summary: string; detail: string | null })}
  <div class="lc-error" class:warning={state === "expired_credentials"} class:info={state === "reconnecting"}>
    {problem.summary}
    {#if problem.detail}
      <details class="lc-error-detail">
        <summary>Details</summary>
        <code>{problem.detail}</code>
      </details>
    {/if}
  </div>
{/snippet}

{#snippet copyAddressButton(row: Row)}
  <button
    class="btn-icon copy-btn"
    class:copied={copiedName === row.name}
    onclick={() => copyAddress(row)}
    title="Copy {connectAddress(row)}"
    aria-label="Copy {connectAddress(row)}"
  >
    {#if copiedName === row.name}<Check size={13} />{:else}<Copy size={13} />{/if}
  </button>
{/snippet}

{#snippet forwardingToggle(name: string, cls: string)}
  {#if forwarding}
    <button
      class={cls}
      onclick={() => toggleDbForwarding(name)}
      disabled={changingForwarding !== null || busyConns.has(name) || busyAll}
      title={forwardingTitle(name)}
      aria-label={forwardingTitle(name)}
    >
      {#if changingForwarding === name}
        <span class="spinner-sm"></span>
      {:else if forwarding.databases[name]?.enabled === false}
        <Link2Off size={14} />
      {:else}
        <Link2 size={14} />
      {/if}
    </button>
  {/if}
{/snippet}

<div class="page">
  <div class="page-header">
    <h1>
      Databases {#if refreshing && !loading}<span class="refreshing-dot"></span>{/if}
    </h1>
    <div class="header-actions">
      <ViewToggle page="databases" />
      <SearchInput bind:value={query} placeholder="Filter databases…" />
      <div class="actions">
        {#if forwarding?.enabled && allRows.length > 0}
          <button
            class="btn-secondary"
            onclick={toggleAllForwarding}
            disabled={changingForwarding !== null || busyAll}
            title="Stop mapping database hostnames to their tunnels in the hosts file, so they resolve through normal DNS"
          >
            {#if changingForwarding === "*"}<span class="spinner-sm"></span>{:else}<Link2Off size={14} />{/if}
            Pause hostnames
          </button>
        {/if}
        {#if anyConnected}
          <button class="btn-secondary" onclick={stopAll} disabled={busyAll}>
            {#if busyAll}<span class="spinner-sm"></span>{/if}
            Stop All
          </button>
        {/if}
        {#if allRows.some(canStart)}
          <button class="btn-secondary" onclick={startAll} disabled={busyAll}>
            {#if busyAll}<span class="spinner-sm"></span>{/if}
            Start All
          </button>
        {/if}
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

  {#if missingHosts.length > 0 || staleHosts.length > 0 || sharedAddresses.length > 0}
    <div
      class="alert-warning"
      style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"
    >
      <div>
        <strong>Hosts file out of sync</strong>
        {#each sharedAddresses as shared (shared.ip + ":" + shared.port)}
          <br />
          <span class="muted"
            >{shared.databases.join(" and ")} share {shared.ip}:{shared.port}: one hostname can reach
            the other's tunnel.</span
          >
        {/each}
        {#if missingHosts.length > 0}
          <br />
          <span class="muted"
            >Not mapped to their tunnel yet: {missingHosts.join(", ")}.</span
          >
        {/if}
        {#if staleHosts.length > 0}
          <br />
          <span class="muted"
            >Still mapped, but no database uses them (they won't reach the real database):
            {staleHosts.join(", ")}.</span
          >
        {/if}
      </div>
      <button class="btn-primary" onclick={syncHosts} disabled={settingUpHosts}>
        {#if settingUpHosts}<span class="spinner-sm"></span>{/if} Sync Hosts
      </button>
    </div>
  {/if}

  {#if forwarding && !forwarding.enabled}
    <div
      class="alert-warning"
      style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"
    >
      <div>
        <strong>Hostname forwarding is paused</strong>
        {#if forwardedExceptions.length > 0}
          <span class="muted">(except {forwardedExceptions.join(", ")})</span>
        {/if}
        <br />
        <span class="muted"
          >Database hostnames resolve through normal DNS (e.g. over a VPN). Tunnels still work on
          127.0.0.1. Forward a single database with the link button on its row.</span
        >
      </div>
      <button class="btn-primary" onclick={toggleAllForwarding} disabled={changingForwarding !== null || busyAll}>
        {#if changingForwarding === "*"}<span class="spinner-sm"></span>{/if} Resume all
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
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row (row.name)}
            {@const problem = problemOf(row)}
            <tr class:has-problem={problem !== null}>
              <td class="name">{row.name}</td>
              <td><span class="badge {stateClass(connState(row))}">{stateLabel(connState(row))}</span></td>
              <td class="host-cell">
                <!-- Only the hostname is cut short: the copy button and the badge stay visible. -->
                <div class="host-wrap">
                  <code class="host-text" title={row.db.host}>{row.db.host}</code>
                  {@render copyAddressButton(row)}
                  {#if !forwarded(row.name)}
                    <span class="badge badge-gray" title="Resolves through normal DNS: hostname forwarding is paused"
                      >DNS</span
                    >
                  {/if}
                </div>
              </td>
              <td>{row.db.port} → {localEndpoint(row)}</td>
              <td class="uptime-cell">{formatUptime(row.conn?.uptime_seconds)}</td>
              <td class="actions-cell">
                <div class="actions-wrap">
                  {@render forwardingToggle(row.name, "btn-sm btn-secondary")}
                  {#if canStart(row)}
                    <button
                      class="btn-sm btn-primary"
                      onclick={() => startOne(row.name)}
                      disabled={busyConns.has(row.name) || busyAll}
                    >
                      {#if busyConns.has(row.name)}
                        <span class="spinner-sm"></span> Starting…
                      {:else}
                        {startLabel(row, true)}
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
                  {/if}
                  <RowMenu label="More actions for {row.name}" items={dbMenu(row)} />
                </div>
              </td>
            </tr>
            {#if problem}
              <tr class="problem-row">
                <td colspan="6">{@render problemNote(connState(row), problem)}</td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="list-cards">
      {#each rows as row (row.name)}
        {@const problem = problemOf(row)}
        <div class="list-card">
          <div class="lc-main">
            <div class="lc-header">
              <span class="lc-title">{row.name}</span>
              <span class="badge {stateClass(connState(row))}">{stateLabel(connState(row))}</span>
            </div>
            <div class="lc-meta">
              <span class="lc-meta-item">
                <span class="muted">Host:</span> <code>{row.db.host}</code>
                {@render copyAddressButton(row)}
                {#if !forwarded(row.name)}
                  <span class="badge badge-gray" title="Resolves through normal DNS: hostname forwarding is paused"
                    >DNS</span
                  >
                {/if}
              </span>
              <span class="lc-meta-sep">·</span>
              <span class="lc-meta-item">
                <span class="muted">Ports:</span>
                <code>{row.db.port} → {localEndpoint(row)}</code>
              </span>
              <span class="lc-meta-sep">·</span>
              <span class="lc-meta-item">
                <span class="muted">Uptime:</span>
                {formatUptime(row.conn?.uptime_seconds)}
              </span>
            </div>
            {#if problem}
              {@render problemNote(connState(row), problem)}
            {/if}
          </div>
          <div class="lc-actions">
            {@render forwardingToggle(row.name, "btn-secondary")}
            {#if canStart(row)}
              <button
                class="btn-primary"
                onclick={() => startOne(row.name)}
                disabled={busyConns.has(row.name) || busyAll}
              >
                {startLabel(row)}
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
            <RowMenu label="More actions for {row.name}" items={dbMenu(row)} />
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
          <input bind:value={form.name} placeholder="my-db" />
        </FormField>
        <FormField
          label="Bastion instance"
          required
          error={formErrors.bastion}
          hint={bastionOptions.length ? "A saved instance, or type an instance ID" : "Type an instance ID (i-…)"}
        >
          <SearchableSelect
            options={bastionOptions}
            value={form.bastion}
            placeholder="i-0abc123def456"
            allowCustom
            onchange={pickBastion}
          />
        </FormField>
        <FormField label="Profile" hint="Optional" error={formErrors.profile}>
          <SearchableSelect
            options={profileOptions}
            value={form.profile ?? ""}
            placeholder="default"
            onchange={(v) => (form.profile = v)}
          />
        </FormField>
        <FormField
          label="Region"
          required
          error={formErrors.region}
          hint={regionFromHost(form.host) === form.region.trim() ? "From the host" : undefined}
        >
          <input bind:value={form.region} placeholder="us-east-1" />
        </FormField>
        <div class="span-2">
          <FormField label="Remote host" required error={formErrors.host} hint={hostHint}>
            <SearchableSelect
              options={hostOptions}
              value={form.host}
              placeholder="mydb.cluster-abc123.us-east-1.rds.amazonaws.com"
              allowCustom
              onchange={pickHost}
            />
          </FormField>
        </div>
        <FormField label="Remote port" required error={formErrors.port}>
          <input type="number" bind:value={form.port} placeholder="5432" />
        </FormField>
      </div>

      <details class="advanced">
        <summary>Advanced</summary>
        <div class="form-grid">
          <FormField
            label="Local port"
            hint="Optional: the remote port when it's free"
            error={formErrors.local_port}
          >
            <input type="number" bind:value={form.local_port} placeholder="auto" />
          </FormField>
          {#if editingName && editingLocalAddress !== "127.0.0.1"}
            <p class="muted local-address">
              Local address <code>{editingLocalAddress}</code>, assigned by Devo for hostname forwarding.
            </p>
          {/if}
        </div>
      </details>

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
  .span-2 {
    grid-column: span 2;
  }
  .advanced summary {
    cursor: pointer;
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 0.6rem;
  }
  .local-address {
    align-self: center;
    margin: 0;
    font-size: 0.78rem;
  }
  .host-wrap {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    max-width: 180px;
  }
  .host-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .host-wrap .copy-btn,
  .host-wrap .badge {
    flex-shrink: 0;
  }
  tr.has-problem td {
    border-bottom: none;
  }
  .problem-row td {
    padding-top: 0;
  }
  .problem-row td .lc-error {
    margin-top: 0;
  }
  .uptime-cell {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.78rem;
    color: var(--text-secondary);
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
  .copy-btn {
    display: inline-flex;
    vertical-align: middle;
    color: var(--text-secondary);
  }
  .copy-btn.copied {
    color: var(--success);
    opacity: 1;
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

  .lc-error.warning {
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 10%, transparent);
  }

  .lc-error.info {
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }

  .lc-error-detail {
    margin-top: 0.25rem;
    font-size: 0.78rem;
  }

  .lc-error-detail summary {
    cursor: pointer;
    color: var(--text-muted);
    user-select: none;
  }

  .lc-error-detail code {
    display: block;
    margin-top: 0.25rem;
    color: var(--text-secondary);
    white-space: pre-wrap;
    word-break: break-word;
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
    background: color-mix(in srgb, var(--warning) 10%, transparent);
    border: 1px solid var(--warning);
    border-radius: 6px;
    padding: 0.75rem 1rem;
    color: var(--warning);
    font-size: 0.85rem;
    margin-bottom: 1rem;
  }
  .alert-sso strong {
    display: block;
    margin-bottom: 0.2rem;
  }
  .alert-sso p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }
  .alert-sso code {
    color: var(--warning);
  }
  .alert-sso a {
    word-break: break-all;
    overflow-wrap: anywhere;
    color: var(--warning);
    text-decoration: underline;
  }
  .spinner-sso {
    margin-top: 3px;
    flex-shrink: 0;
  }
</style>
