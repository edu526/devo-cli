<script lang="ts">
  // Debounced search input. Emits `onchange` after `delay` ms of
  // idleness, never on every keystroke. Use as a header filter for tables
  // and lists; pair with `bind:value` for the live draft.
  //
  // Usage:
  //   <SearchInput bind:value={query} placeholder="Filter profiles…" />
  //   {#each items.filter(matches(query)) as item} ... {/each}

  interface Props {
    value: string;
    placeholder?: string;
    delay?: number;
    onchange?: (value: string) => void;
  }

  let { value = $bindable(""), placeholder = "Search…", delay = 200, onchange }: Props = $props();

  let timer: ReturnType<typeof setTimeout> | null = null;

  function handleInput(e: Event) {
    const next = (e.currentTarget as HTMLInputElement).value;
    value = next;
    if (timer !== null) clearTimeout(timer);
    if (onchange) {
      timer = setTimeout(() => onchange(next), delay);
    }
  }
</script>

<div class="search-input">
  <span class="search-icon" aria-hidden="true">⌕</span>
  <input
    type="search"
    {value}
    {placeholder}
    aria-label={placeholder}
    oninput={handleInput}
  />
  {#if value}
    <button
      type="button"
      class="clear-btn"
      aria-label="Clear search"
      onclick={() => {
        value = "";
        if (timer !== null) clearTimeout(timer);
        if (onchange) onchange("");
      }}>×</button
    >
  {/if}
</div>

<style>
  .search-input {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 0.35rem 0.6rem;
    min-width: 220px;
  }
  .search-icon {
    font-size: 0.85rem;
    opacity: 0.6;
  }
  input {
    background: transparent;
    border: none;
    outline: none;
    color: #e0e0e0;
    font-size: 0.85rem;
    flex: 1;
    min-width: 0;
  }
  .clear-btn {
    background: none;
    border: none;
    color: #8a8a8a;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0 0.2rem;
  }
</style>
