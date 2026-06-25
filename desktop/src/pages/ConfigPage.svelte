<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { EditorView, basicSetup } from "codemirror";
  import { json } from "@codemirror/lang-json";
  import { oneDark } from "@codemirror/theme-one-dark";
  import { EditorState } from "@codemirror/state";
  import { keymap } from "@codemirror/view";
  import { configApi, ApiError } from "../lib/api";

  let config: Record<string, unknown> = $state({});
  let loading = $state(true);
  let saving = $state(false);
  let parseError: string | null = $state(null);
  let saveOk = $state(false);

  let editorEl: HTMLDivElement;
  let view: EditorView | null = null;

  function createEditor(initialContent: string) {
    if (view) view.destroy();

    const saveKeymap = keymap.of([
      {
        key: "Mod-s",
        run: () => {
          save();
          return true;
        },
      },
    ]);

    const state = EditorState.create({
      doc: initialContent,
      extensions: [
        basicSetup,
        json(),
        oneDark,
        saveKeymap,
        EditorView.theme({
          "&": { height: "100%", fontSize: "0.82rem" },
          ".cm-scroller": {
            fontFamily: '"JetBrains Mono", "Cascadia Code", monospace',
            overflow: "auto",
          },
          ".cm-content": { padding: "0.75rem 0" },
          "&.cm-focused": { outline: "none" },
        }),
        EditorView.lineWrapping,
      ],
    });

    view = new EditorView({ state, parent: editorEl });
  }

  async function load() {
    try {
      config = await configApi.get();
      const text = JSON.stringify(config, null, 2);
      if (view) {
        view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
      } else {
        createEditor(text);
      }
    } catch (e) {
      parseError = String(e);
    } finally {
      loading = false;
    }
  }

  async function save() {
    if (!view) return;
    parseError = null;
    saveOk = false;
    const raw = view.state.doc.toString();
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      parseError = `JSON parse error: ${e}`;
      return;
    }
    saving = true;
    try {
      config = await configApi.put(parsed);
      const updated = JSON.stringify(config, null, 2);
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: updated } });
      saveOk = true;
      setTimeout(() => {
        saveOk = false;
      }, 2000);
    } catch (e) {
      parseError = e instanceof ApiError ? e.message : String(e);
    } finally {
      saving = false;
    }
  }

  function reset() {
    if (!view) return;
    parseError = null;
    const text = JSON.stringify(config, null, 2);
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
  }

  onMount(() => {
    createEditor("");
    load();
  });

  onDestroy(() => view?.destroy());
</script>

<div class="page">
  <div class="page-header">
    <h1>Config</h1>
    <div class="actions">
      <button class="btn-secondary" onclick={reset}>Reset</button>
      <button class="btn-primary" onclick={save} disabled={saving}>
        {#if saving}
          <span class="spinner-sm"></span> Saving…
        {:else if saveOk}
          Saved ✓
        {:else}
          Save
        {/if}
      </button>
    </div>
  </div>

  {#if parseError}
    <div class="alert-error">{parseError}</div>
  {/if}

  {#if loading}
    <p class="muted">Loading…</p>
  {:else}
    <p class="muted hint">
      Edit the JSON below. Changes are written to <code>~/.devo/config.json</code>.
      <span class="shortcuts">Ctrl+Z undo · Ctrl+Y redo · Ctrl+S save</span>
    </p>
  {/if}

  <div class="editor-wrap" class:hidden={loading} bind:this={editorEl}></div>
</div>

<style>
  .hint {
    margin-bottom: 0.5rem;
  }

  .shortcuts {
    margin-left: 0.75rem;
    color: var(--text-faint);
    font-size: 0.75rem;
  }

  .editor-wrap {
    flex: 1;
    min-height: 400px;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    transition: border-color 0.15s;
  }

  .editor-wrap:focus-within {
    border-color: var(--accent);
  }

  .editor-wrap.hidden {
    display: none;
  }

  .editor-wrap :global(.cm-editor) {
    background: var(--bg-surface);
    width: 100%;
    height: 100%;
    min-height: 400px;
  }

  .editor-wrap :global(.cm-gutters) {
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
  }
</style>
