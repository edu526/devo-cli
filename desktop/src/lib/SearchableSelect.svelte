<script lang="ts">
  // Searchable single-select dropdown. Native <select> doesn't support
  // typeahead filtering, which is painful when an SSO org has 30+
  // accounts. This component renders a text input that filters the
  // option list below it.
  //
  // UX:
  //  - Click/focus the input → dropdown opens, query is cleared
  //  - Type → options filter by case-insensitive substring on `label`
  //  - ArrowDown / ArrowUp → move highlight through filtered options
  //  - Enter → select the highlighted option
  //  - Escape → close (keeps the current value)
  //  - Click outside → close (keeps the current value)
  //  - When closed, the input shows the selected option's label
  //  - When no option is selected, the input shows the placeholder

  import { onMount, onDestroy } from "svelte";

  export interface SearchableOption {
    value: string;
    label: string;
  }

  interface Props {
    options: SearchableOption[];
    value: string;
    placeholder?: string;
    disabled?: boolean;
    /** Optional extra class(es) for the input element. */
    inputClass?: string;
    /** Fires when the user picks a different option. */
    onchange?: (value: string) => void;
  }

  let {
    options,
    value = $bindable(""),
    placeholder = "Select…",
    disabled = false,
    inputClass = "",
    onchange,
  }: Props = $props();

  let open = $state(false);
  let query = $state("");
  let highlight = $state(0);
  let rootEl: HTMLDivElement | undefined = $state();
  let inputEl: HTMLInputElement | undefined = $state();
  // Dropdown position relative to the viewport. Using `position: fixed`
  // (instead of `position: absolute` inside the input wrapper) means the
  // panel is NOT clipped by ancestor overflow rules — important when this
  // component is used inside a modal that has its own `overflow-y: auto`.
  let dropdownPos = $state({ top: 0, left: 0, width: 0, openAbove: false });

  const filtered = $derived.by(() => {
    const q = query.toLowerCase().trim();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  });

  const selected = $derived(options.find((o) => o.value === value) ?? null);

  // Approximate dropdown height — must match the `max-height` in CSS.
  const _DROPDOWN_MAX_HEIGHT = 220;

  function updateDropdownPos() {
    if (!inputEl) return;
    const rect = inputEl.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const openAbove =
      spaceBelow < _DROPDOWN_MAX_HEIGHT && spaceAbove > spaceBelow;
    dropdownPos = {
      top: openAbove ? rect.top - _DROPDOWN_MAX_HEIGHT - 4 : rect.bottom + 4,
      left: rect.left,
      width: rect.width,
      openAbove,
    };
  }

  function openDropdown() {
    if (disabled) return;
    open = true;
    query = "";
    highlight = 0;
    updateDropdownPos();
  }

  function closeDropdown() {
    open = false;
    query = "";
    highlight = 0;
  }

  function selectOption(opt: SearchableOption) {
    value = opt.value;
    closeDropdown();
    onchange?.(opt.value);
    inputEl?.focus();
  }

  function onWindowChange() {
    if (open) updateDropdownPos();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) openDropdown();
      highlight = Math.min(highlight + 1, Math.max(0, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlight = Math.max(highlight - 1, 0);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = filtered[highlight];
      if (opt) selectOption(opt);
    } else if (e.key === "Escape") {
      e.preventDefault();
      if (open) closeDropdown();
    }
  }

  function onDocPointer(e: MouseEvent) {
    if (!open) return;
    if (rootEl && !rootEl.contains(e.target as Node)) closeDropdown();
  }

  onMount(() => {
    document.addEventListener("mousedown", onDocPointer);
    window.addEventListener("resize", onWindowChange);
    window.addEventListener("scroll", onWindowChange, true);
  });
  onDestroy(() => {
    document.removeEventListener("mousedown", onDocPointer);
    window.removeEventListener("resize", onWindowChange);
    window.removeEventListener("scroll", onWindowChange, true);
  });

  // Reset highlight when the filtered list shrinks below the current index.
  $effect(() => {
    if (highlight >= filtered.length) highlight = Math.max(0, filtered.length - 1);
  });
</script>

<div class="searchable-select" class:open class:disabled bind:this={rootEl}>
  <input
    bind:this={inputEl}
    type="text"
    role="combobox"
    aria-expanded={open}
    aria-controls="searchable-listbox"
    aria-autocomplete="list"
    autocomplete="off"
    spellcheck="false"
    {placeholder}
    {disabled}
    class={inputClass}
    value={open ? query : selected?.label ?? ""}
    onfocus={openDropdown}
    oninput={() => {
      if (!open) openDropdown();
      query = (inputEl?.value ?? "");
      highlight = 0;
    }}
    onkeydown={onKeydown}
  />
  <span class="caret" aria-hidden="true">▾</span>

  {#if open && !disabled}
    <ul
      id="searchable-listbox"
      class="options"
      role="listbox"
      style="top: {dropdownPos.top}px; left: {dropdownPos.left}px; width: {dropdownPos.width}px;"
    >
      {#each filtered as opt, i (opt.value)}
        <li
          role="option"
          aria-selected={value === opt.value}
          class:hl={highlight === i}
          class:sel={value === opt.value}
          onmouseenter={() => (highlight = i)}
          onmousedown={(e) => {
            e.preventDefault();
            selectOption(opt);
          }}
        >
          {opt.label}
        </li>
      {/each}
      {#if filtered.length === 0}
        <li class="empty">No matches</li>
      {/if}
    </ul>
  {/if}
</div>

<style>
  .searchable-select {
    position: relative;
    width: 100%;
  }
  input {
    width: 100%;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 0.85rem;
    padding: 0.45rem 1.8rem 0.45rem 0.6rem;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s;
  }
  input:focus {
    border-color: #4f8ef7;
  }
  .disabled input {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .caret {
    position: absolute;
    right: 0.6rem;
    top: 50%;
    transform: translateY(-50%);
    color: #94a3b8;
    pointer-events: none;
    font-size: 0.75rem;
  }
  .options {
    position: fixed;
    max-height: 220px;
    overflow-y: auto;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    list-style: none;
    margin: 0;
    padding: 0.25rem 0;
    z-index: 200;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  }
  .options li {
    padding: 0.4rem 0.7rem;
    font-size: 0.85rem;
    color: #e0e0e0;
    cursor: pointer;
    user-select: none;
  }
  .options li.hl {
    background: #2a2a2a;
  }
  .options li.sel::before {
    content: "✓ ";
    color: #4f8ef7;
  }
  .options li.empty {
    color: #6a6a6a;
    font-style: italic;
    cursor: default;
  }
</style>
