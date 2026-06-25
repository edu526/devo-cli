<script lang="ts">
  import { viewModes } from "./stores";

  let { page }: { page: keyof typeof viewModes } = $props();
  const currentViewMode = $derived(viewModes[page]);
</script>

<div class="view-toggle">
  <button
    class="vt-btn"
    class:active={$currentViewMode === 'card'}
    onclick={() => currentViewMode.set('card')}
    title="Card View"
    aria-label="Card View"
  >
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="4" width="18" height="4" rx="1"></rect>
      <rect x="3" y="10" width="18" height="4" rx="1"></rect>
      <rect x="3" y="16" width="18" height="4" rx="1"></rect>
    </svg>
  </button>
  <button
    class="vt-btn"
    class:active={$currentViewMode === 'table'}
    onclick={() => currentViewMode.set('table')}
    title="Table View"
    aria-label="Table View"
  >
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="3" y1="9" x2="21" y2="9"></line>
      <line x1="9" y1="21" x2="9" y2="9"></line>
    </svg>
  </button>
</div>

<style>
  .view-toggle {
    display: flex;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 2px;
    gap: 2px;
  }

  .vt-btn {
    background: transparent;
    border: none;
    color: var(--text-muted, #a0a0a0);
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }

  .vt-btn:hover {
    color: var(--text-normal, #e0e0e0);
    background: rgba(255, 255, 255, 0.05);
  }

  .vt-btn.active {
    color: #4f8ef7;
    background: rgba(79, 142, 247, 0.1);
  }
</style>
