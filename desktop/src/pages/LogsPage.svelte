<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { logsApi, ApiError } from "../lib/api";
  import { ws, type WsMessage } from "../lib/ws";
  import { errorLog, clearErrorLog } from "../lib/error-log";
  import SearchInput from "../lib/SearchInput.svelte";

  type LogLevel = "ALL" | "DEBUG" | "INFO" | "WARN" | "ERROR";

  let lines: string[] = $state([]);
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
  let error: string | null = $state(null);
  let paused = $state(false);
  let lineCount = $state(300);
  let clientErrorsExpanded = $state(true);
  let expandedErrorIds = $state<Set<number>>(new Set());

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
    lines.filter((line) => {
      // Level filter
      if (!levels.ALL) {
        if (levels.DEBUG && (line.includes(" DEBUG   ") || line.includes(" DEBUG "))) return true;
        if (levels.INFO && line.includes(" INFO    ")) return true;
        if (levels.WARN && line.includes(" WARNING ")) return true;
        if (levels.ERROR && (line.includes(" ERROR   ") || line.includes(" CRITICAL"))) return true;
        return false;
      }
      // Text filter
      if (query.trim() && !line.toLowerCase().includes(query.toLowerCase())) {
        return false;
      }
      return true;
    }),
  );

  let autoRefreshInterval: ReturnType<typeof setInterval> | null = null;

  async function load() {
    error = null;
    try {
      lines = await logsApi.get(lineCount);
    } catch (e) {
      error = e instanceof ApiError ? String(e.detail) : String(e);
    } finally {
      loading = false;
    }
  }

  async function clear() {
    if (!confirm("Clear the sidecar log file?")) return;
    clearing = true;
    try {
      await logsApi.clear();
      lines = [];
    } catch (e) {
      error = e instanceof ApiError ? String(e.detail) : String(e);
    } finally {
      clearing = false;
    }
  }

  function levelClass(line: string): string {
    if (line.includes(" ERROR   ") || line.includes(" CRITICAL")) return "level-error";
    if (line.includes(" WARNING ")) return "level-warn";
    if (line.includes(" INFO    ")) return "level-info";
    return "level-debug";
  }

  // WS: append incoming log lines in real-time
  const off = ws.on("log.line", (msg: WsMessage) => {
    if (paused) return;
    const line = (msg.line as string) ?? "";
    if (!line) return;
    // Cap the in-memory buffer at 5000 lines so a runaway producer
    // does not balloon the renderer.
    if (lines.length >= 5000) lines = lines.slice(-4500);
    lines = [...lines, line];
  });

  function togglePause() {
    paused = !paused;
  }

  async function download() {
    const content = lines.join("\n");
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sidecar-${date}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  onMount(() => {
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
    <div class="actions">
      <button class="btn-secondary" onclick={togglePause} disabled={loading}>
        {paused ? "▶ Resume" : "⏸ Pause"}
      </button>
      <button class="btn-secondary" onclick={() => load()} disabled={loading}>↺ Refresh</button>
      <button class="btn-secondary" onclick={download} disabled={lines.length === 0}>
        ⤓ Download
      </button>
      <button class="btn-danger" onclick={clear} disabled={clearing}>
        {clearing ? "Clearing…" : "Clear"}
      </button>
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
        <button type="button" class="btn-sm btn-secondary" onclick={copyAllErrors}>
          Copy
        </button>
        <button type="button" class="btn-sm btn-secondary" onclick={downloadReport}>
          Download
        </button>
        <button type="button" class="btn-sm btn-secondary" onclick={clearErrorLog}>
          Clear
        </button>
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
    <SearchInput bind:value={query} placeholder="Filter text…" />
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
    </div>
    <select class="line-select" bind:value={lineCount} onchange={() => load()}>
      <option value={100}>Last 100</option>
      <option value={300}>Last 300</option>
      <option value={1000}>Last 1000</option>
      <option value={5000}>Last 5000</option>
    </select>
  </div>

  <p class="muted log-path">~/.devo/sidecar.log · streaming via WS</p>

  {#if error}
    <div class="alert-error">{error}</div>
  {/if}

  {#if loading && lines.length === 0}
    <p class="muted">Loading…</p>
  {:else if filtered.length === 0}
    <p class="muted">
      {lines.length === 0
        ? "No log entries yet."
        : `No log entries match the current filters (${lines.length} total hidden).`}
    </p>
  {:else}
    <pre class="log-viewer">{#each filtered as line}<span class="log-line {levelClass(line)}"
          >{line}</span
        >
      {/each}</pre>
  {/if}
</div>

<style>
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
    padding: 0.75rem 1rem;
    font-family: "JetBrains Mono", "Cascadia Code", monospace;
    font-size: 0.75rem;
    line-height: 1.7;
    overflow-x: auto;
    overflow-y: auto;
    max-height: calc(100vh - 260px);
    white-space: pre;
    margin: 0;
  }

  .log-line {
    display: block;
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
