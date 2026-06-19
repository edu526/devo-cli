<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { logsApi, ApiError } from "../lib/api";
  import { ws, type WsMessage } from "../lib/ws";
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
    background: var(--bg-surface-2);
    border: 1px solid var(--border-strong);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 0.82rem;
    padding: 0.35rem 0.6rem;
    cursor: pointer;
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
</style>
