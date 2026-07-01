<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { logsApi, configApi, ApiError } from "../lib/api";
  import { ws, type WsMessage } from "../lib/ws";
  import { errorLog, clearErrorLog } from "../lib/error-log";
  import SearchInput from "../lib/SearchInput.svelte";
  import { Play, Pause, RefreshCw } from "@lucide/svelte";
  import { parseLogLine, groupLogLines, type LogLevel, type LogEntry } from "../lib/log-parser";

  let nextId = 1;
  let logEntries: LogEntry[] = $state([]);
  let expandedLogs = $state<Set<number>>(new Set());

  function toggleLog(id: number) {
    const next = new Set(expandedLogs);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    expandedLogs = next;
  }

  let levels: Record<LogLevel, boolean> = $state({
    ALL: true,
    DEBUG: true,
    INFO: true,
    WARN: true,
    ERROR: true,
  });
  let query = $state("");
  let loading = $state(true);
  let clearing = $state(false);
  let showConfirmClear = $state(false);
  let error: string | null = $state(null);
  let paused = $state(false);
  let debugMode = $state(false);
  let lineCount = $state(300);
  let clientErrorsExpanded = $state(true);
  let expandedErrorIds = $state<Set<number>>(new Set());

  let logViewer: HTMLDivElement | undefined = $state();
  let wasAtBottom = $state(true);

  $effect(() => {
    // This effect runs after DOM updates when 'filtered' changes.
    // We reference it to establish the dependency.
    void filtered;
    if (logViewer && wasAtBottom) {
      logViewer.scrollTop = logViewer.scrollHeight;
    }
  });

  function handleLogScroll(e: Event) {
    const target = e.target as HTMLElement;
    // Check if we are within 10px of the bottom
    wasAtBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 10;
  }

  function toggleErrorDetail(id: number): void {
    const next = new Set(expandedErrorIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    expandedErrorIds = next;
  }

  function formatErrorReport(entries: typeof $errorLog): string {
    const lines: string[] = [
      "Devo Desktop — client error report",
      `Generated: ${new Date().toISOString()}`,
      `Count: ${entries.length}`,
      "",
    ];
    for (const e of entries) {
      lines.push(`[${new Date(e.ts).toISOString()}] [${e.source}] ${e.message}`);
      if (e.detail) lines.push(e.detail);
      lines.push("");
    }
    return lines.join("\n");
  }

  async function copyToClipboard(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // ponytail: clipboard API can be blocked (no secure context, denied
      // permission). Fall back to the legacy execCommand path so the user
      // is never left without a copy option.
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch {
        /* swallow — nothing else we can do without clipboard access */
      }
      document.body.removeChild(ta);
    }
  }

  async function copyError(entry: (typeof $errorLog)[number]): Promise<void> {
    await copyToClipboard(formatErrorReport([entry]));
  }

  async function copyAllErrors(): Promise<void> {
    await copyToClipboard(formatErrorReport($errorLog));
  }

  function downloadReport(): void {
    const text = formatErrorReport($errorLog);
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `devo-client-errors-${date}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const filteredClientErrors = $derived(
    query.trim()
      ? $errorLog.filter(
          (e) =>
            e.message.toLowerCase().includes(query.toLowerCase()) ||
            e.source.toLowerCase().includes(query.toLowerCase()) ||
            (e.detail?.toLowerCase().includes(query.toLowerCase()) ?? false),
        )
      : $errorLog,
  );

  function formatTs(ts: number): string {
    const d = new Date(ts);
    return d.toLocaleTimeString();
  }

  const filtered = $derived(
    logEntries.filter((entry) => {
      // Level filter
      const cls = getLevelClass(entry.level || entry.raw);
      let matchesLevel = false;
      if (cls === "level-debug" && levels.DEBUG) matchesLevel = true;
      if (cls === "level-info" && levels.INFO) matchesLevel = true;
      if (cls === "level-warn" && levels.WARN) matchesLevel = true;
      if (cls === "level-error" && levels.ERROR) matchesLevel = true;

      if (!matchesLevel) return false;

      // Text filter
      if (query.trim() && !entry.raw.toLowerCase().includes(query.toLowerCase())) {
        return false;
      }
      return true;
    }),
  );

  let autoRefreshInterval: ReturnType<typeof setInterval> | null = null;

  async function load() {
    error = null;
    try {
      const rawLines = await logsApi.get(lineCount);
      const parsed = groupLogLines(rawLines, nextId);
      logEntries = parsed.entries;
      nextId = parsed.nextId;
    } catch (e) {
      error = e instanceof ApiError ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  async function clear() {
    showConfirmClear = false;
    clearing = true;
    try {
      await logsApi.clear();
      logEntries = [];
    } catch (e) {
      error = e instanceof ApiError ? e.message : String(e);
    } finally {
      clearing = false;
    }
  }

  function getLevelClass(levelOrLine: string): string {
    if (!levelOrLine) return "level-debug";
    if (levelOrLine === "ERROR" || levelOrLine === "CRITICAL" || levelOrLine.includes(" ERROR ") || levelOrLine.includes(" CRITICAL")) return "level-error";
    if (levelOrLine === "WARNING" || levelOrLine === "WARN" || levelOrLine.includes(" WARNING ")) return "level-warn";
    if (levelOrLine === "INFO" || levelOrLine.includes(" INFO ")) return "level-info";
    return "level-debug";
  }

  // WS: append incoming log lines in real-time
  const off = ws.on("log.line", (msg: WsMessage) => {
    if (paused) return;
    const raw = (msg.line as string) ?? "";
    if (!raw) return;

    let next = [...logEntries];
    const entry = parseLogLine(raw, nextId);

    if (entry.ts) {
      next.push(entry);
      nextId++;
    } else {
      if (next.length > 0) {
        const lastIdx = next.length - 1;
        const last = { ...next[lastIdx]! };
        last.raw += "\n" + raw;
        if (last.msg !== undefined) {
          last.msg += "\n" + raw;
        }
        next[lastIdx] = last;
      } else {
        next.push(entry);
        nextId++;
      }
    }

    // Cap the in-memory buffer at 5000 lines so a runaway producer
    // does not balloon the renderer.
    if (next.length >= 5000) next = next.slice(-4500);
    logEntries = next;
  });

  function togglePause() {
    paused = !paused;
  }

  async function toggleDebugMode() {
    const nextVal = !debugMode;
    try {
      await configApi.patch({ debug_mode: nextVal });
      debugMode = nextVal;
    } catch {
      error = "Failed to update debug mode";
    }
  }

  onMount(async () => {
    try {
      const cfg = await configApi.get();
      debugMode = !!cfg.debug_mode;
    } catch {
      // ignore
    }
    load();
    // Periodic snapshot as a safety net: WS may miss lines if the
    // sidecar is restarted while we're connected. Every 30 s we
    // re-fetch the tail and merge.
    autoRefreshInterval = setInterval(() => {
      if (!paused) load();
    }, 30000);
  });

  onDestroy(() => {
    off();
    if (autoRefreshInterval !== null) clearInterval(autoRefreshInterval);
  });
</script>

<div class="page">
  <div class="page-header">
    <h1>Logs</h1>
    <div class="header-actions">
      <SearchInput bind:value={query} placeholder="Filter text…" />
      <select class="line-select" bind:value={lineCount} onchange={() => load()}>
        <option value={100}>Last 100</option>
        <option value={300}>Last 300</option>
        <option value={1000}>Last 1000</option>
        <option value={5000}>Last 5000</option>
      </select>
      <div class="actions">
        <button class="btn-secondary" onclick={togglePause} disabled={loading}>
          {#if paused}<Play size={14} /> Resume{:else}<Pause size={14} /> Pause{/if}
        </button>
        <button class="btn-secondary" onclick={() => load()} disabled={loading}>
          <RefreshCw size={14} /> Refresh
        </button>
        <button class="btn-danger" onclick={() => (showConfirmClear = true)} disabled={clearing}>
          {clearing ? "Clearing…" : "Clear"}
        </button>
      </div>
    </div>
  </div>

  {#if $errorLog.length > 0}
    <section class="client-errors" data-testid="client-errors">
      <div class="client-errors-header">
        <button
          type="button"
          class="client-errors-toggle"
          onclick={() => (clientErrorsExpanded = !clientErrorsExpanded)}
          aria-expanded={clientErrorsExpanded}
        >
          <span class="chev">{clientErrorsExpanded ? "▾" : "▸"}</span>
          <strong>Client errors</strong>
          <span class="badge-count">{$errorLog.length}</span>
        </button>
        <span class="header-spacer"></span>
        <button type="button" class="btn-sm btn-secondary" onclick={copyAllErrors}> Copy </button>
        <button type="button" class="btn-sm btn-secondary" onclick={downloadReport}>
          Download
        </button>
        <button type="button" class="btn-sm btn-secondary" onclick={clearErrorLog}> Clear </button>
      </div>
      {#if clientErrorsExpanded}
        <div class="client-errors-list">
          {#each filteredClientErrors as entry (entry.id)}
            <div class="client-error-row" data-source={entry.source}>
              <div class="client-error-summary">
                <button
                  type="button"
                  class="client-error-toggle"
                  class:has-detail={!!entry.detail}
                  onclick={() => entry.detail && toggleErrorDetail(entry.id)}
                  aria-expanded={expandedErrorIds.has(entry.id)}
                >
                  <span class="chev ce-chev">
                    {#if entry.detail}{expandedErrorIds.has(entry.id) ? "▾" : "▸"}{:else}&nbsp;{/if}
                  </span>
                  <span class="ce-ts">{formatTs(entry.ts)}</span>
                  <span class="ce-source">{entry.source}</span>
                  <span class="ce-msg">{entry.message}</span>
                </button>
                <button
                  type="button"
                  class="ce-copy"
                  onclick={() => copyError(entry)}
                  aria-label="Copy error"
                  title="Copy this error"
                >
                  Copy
                </button>
              </div>
              {#if entry.detail && expandedErrorIds.has(entry.id)}
                <pre class="ce-detail">{entry.detail}</pre>
              {/if}
            </div>
          {/each}
          {#if filteredClientErrors.length === 0}
            <div class="ce-empty">No client errors match the current filter.</div>
          {/if}
        </div>
      {/if}
    </section>
  {/if}

  <div class="toolbar">
    <div class="level-filter">
      <span class="filter-label">Levels:</span>
      {#each ["DEBUG", "INFO", "WARN", "ERROR"] as level (level)}
        <label class="level-toggle">
          <input
            type="checkbox"
            checked={levels[level as LogLevel]}
            onchange={() => {
              levels[level as LogLevel] = !levels[level as LogLevel];
            }}
          />
          <span class="level-dot level-{level.toLowerCase()}"></span>
          {level}
        </label>
      {/each}
      <span style="border-left: 1px solid #333; height: 16px; margin: 0 0.5rem;"></span>
      <label class="level-toggle" title="Enable Uvicorn debug logs. Requires app restart to take effect.">
        <input type="checkbox" checked={debugMode} onchange={toggleDebugMode} />
        <span class="filter-label" style="text-transform:none; margin:0;">Backend Debug Mode</span>
      </label>
    </div>
  </div>

  <p class="muted log-path">~/.devo/sidecar.log · streaming via WS</p>

  {#if error}
    <div class="alert-error">{error}</div>
  {/if}

  {#if loading && logEntries.length === 0}
    <p class="muted">Loading…</p>
  {:else if filtered.length === 0}
    <p class="muted">
      {logEntries.length === 0
        ? "No log entries yet."
        : `No log entries match the current filters (${logEntries.length} total hidden).`}
    </p>
  {:else}
    <div class="log-viewer" bind:this={logViewer} onscroll={handleLogScroll}>
      {#each filtered as entry (entry.id)}
        <div class="log-row" class:expanded={expandedLogs.has(entry.id)}>
          <button
            type="button"
            class="log-toggle"
            onclick={() => toggleLog(entry.id)}
            aria-expanded={expandedLogs.has(entry.id)}
          >
            <span class="chev">{expandedLogs.has(entry.id) ? "▾" : "▸"}</span>
            {#if entry.ts}
              <span class="log-ts">{entry.ts}</span>
              <span class="log-level {getLevelClass(entry.level || '')}">{entry.level}</span>
              <span class="log-msg">{entry.msg}</span>
            {:else}
              <span class="log-msg {getLevelClass(entry.raw)}">{entry.raw}</span>
            {/if}
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if showConfirmClear}
  <div class="modal-backdrop" role="presentation" onclick={() => (showConfirmClear = false)} onkeydown={() => (showConfirmClear = false)}>
    <div
      class="modal modal-confirm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="clear-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.key === "Escape" && (showConfirmClear = false)}
    >
      <h2 id="clear-title">Clear sidecar logs?</h2>
      <p class="modal-hint">
        This will permanently delete the contents of <code>~/.devo/sidecar.log</code>.
      </p>
      <div class="modal-actions">
        <button class="btn-secondary" onclick={() => (showConfirmClear = false)} disabled={clearing}>Cancel</button>
        <button class="btn-danger" onclick={clear} disabled={clearing}>
          {#if clearing}
            <span class="spinner-sm"></span> Clearing…
          {:else}
            Clear
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-confirm {
    min-width: 380px;
  }
  .log-path {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.75rem;
    margin-top: -0.5rem;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 0.5rem 0 0.75rem;
    flex-wrap: wrap;
  }

  .level-filter {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .filter-label {
    font-size: 0.78rem;
    color: #6a6a6a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .level-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.78rem;
    color: #8a8a8a;
    cursor: pointer;
    user-select: none;
  }

  .level-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .level-dot.level-debug {
    background: #4a4a4a;
  }
  .level-dot.level-info {
    background: #94a3b8;
  }
  .level-dot.level-warn {
    background: #fbbf24;
  }
  .level-dot.level-error {
    background: #f87171;
  }

  .line-select {
    -webkit-appearance: none;
    appearance: none;
    background: var(--bg-surface-2);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 0.82rem;
    padding: 0.35rem 1.8rem 0.35rem 0.6rem;
    cursor: pointer;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='none' stroke='%2394a3b8' stroke-width='1.5' d='M1 1l4 4 4-4'/></svg>");
    background-repeat: no-repeat;
    background-position: right 0.55rem center;
  }

  .line-select:focus {
    outline: none;
    border-color: var(--accent);
  }

  .line-select option {
    background: var(--bg-surface);
    color: var(--text-primary);
  }

  .log-viewer {
    background: #0d0d0d;
    border: 1px solid #1e1e1e;
    border-radius: 6px;
    padding: 0.25rem 0;
    font-family: "JetBrains Mono", "Cascadia Code", monospace;
    font-size: 0.75rem;
    line-height: 1.5;
    overflow-x: hidden;
    overflow-y: auto;
    max-height: calc(100vh - 260px);
    margin: 0;
  }

  .log-row {
    border-bottom: 1px solid transparent;
  }
  .log-row:last-child {
    border-bottom: 0;
  }

  .log-toggle {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    width: 100%;
    padding: 0.25rem 0.75rem;
    background: transparent;
    border: 0;
    color: var(--text-primary);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .log-toggle:hover {
    background: #161616;
  }
  .log-row.expanded .log-toggle {
    background: #111;
  }

  .log-ts {
    color: var(--text-faint);
    flex-shrink: 0;
  }
  .log-level {
    flex-shrink: 0;
    font-weight: 600;
  }
  .log-msg {
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .log-row.expanded .log-msg {
    white-space: pre-wrap;
    word-break: break-all;
  }

  .level-error {
    color: #f87171;
  }
  .level-warn {
    color: #fbbf24;
  }
  .level-info {
    color: #94a3b8;
  }
  .level-debug {
    color: #4a4a4a;
  }

  /* ── Client errors panel ────────────────────────────────────────────────── */
  .client-errors {
    background: #0d0d0d;
    border: 1px solid var(--border);
    border-radius: 6px;
    margin: 0.75rem 0;
    overflow: hidden;
    font-family: "JetBrains Mono", "Cascadia Code", monospace;
    font-size: 0.75rem;
    line-height: 1.7;
  }

  .client-errors-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.75rem;
    color: var(--text-primary);
    border-bottom: 1px solid var(--border);
  }

  .client-errors-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: transparent;
    border: 0;
    color: inherit;
    font: inherit;
    cursor: pointer;
    padding: 0;
  }

  .client-errors-toggle:hover {
    color: var(--accent);
  }

  .chev {
    color: var(--text-faint);
    font-size: 0.75rem;
  }

  .badge-count {
    background: var(--danger);
    color: #1a0a0a;
    border-radius: 999px;
    padding: 0 0.45rem;
    font-size: 0.7rem;
    font-weight: 600;
    min-width: 1.25rem;
    text-align: center;
    font-family: "Inter", system-ui, sans-serif;
  }

  .header-spacer {
    flex: 1;
  }

  .client-errors-list {
    max-height: 240px;
    overflow-y: auto;
  }

  .client-error-row {
    border-bottom: 1px solid var(--border);
  }
  .client-error-row:last-child {
    border-bottom: 0;
  }

  .client-error-summary {
    display: flex;
    align-items: stretch;
    width: 100%;
  }

  .client-error-toggle {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    flex: 1;
    min-width: 0;
    padding: 0.25rem 0.5rem 0.25rem 0.75rem;
    background: transparent;
    border: 0;
    color: var(--text-primary);
    font: inherit;
    text-align: left;
  }
  .client-error-toggle.has-detail {
    cursor: pointer;
  }
  .client-error-toggle.has-detail:hover {
    background: var(--bg-surface-2);
  }

  .ce-copy {
    flex-shrink: 0;
    align-self: stretch;
    padding: 0 0.55rem;
    background: transparent;
    border: 0;
    border-left: 1px solid var(--border);
    color: var(--text-faint);
    font: inherit;
    font-size: 0.7rem;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.1s;
  }
  .client-error-row:hover .ce-copy,
  .client-error-row:focus-within .ce-copy,
  .ce-copy:focus {
    opacity: 1;
  }
  .ce-copy:hover {
    color: var(--accent);
    background: var(--bg-surface-2);
  }

  .ce-chev {
    width: 0.9rem;
    flex-shrink: 0;
    text-align: center;
  }

  .ce-ts {
    color: var(--text-faint);
    flex-shrink: 0;
  }

  .ce-source {
    color: var(--accent);
    flex-shrink: 0;
  }

  .client-error-row[data-source="window"] .ce-source,
  .client-error-row[data-source="unhandledrejection"] .ce-source {
    color: var(--danger);
  }

  .ce-msg {
    color: var(--text-primary);
    word-break: break-word;
    min-width: 0;
  }

  .ce-detail {
    margin: 0;
    padding: 0.4rem 0.75rem 0.4rem 2.5rem;
    color: var(--text-faint);
    background: #050505;
    font-size: 0.72rem;
    overflow-x: auto;
    white-space: pre-wrap;
  }

  .ce-empty {
    padding: 0.6rem 0.75rem;
    color: var(--text-faint);
    font-size: 0.78rem;
  }
</style>
