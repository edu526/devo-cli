<script module lang="ts">
  export interface RowMenuItem {
    label: string;
    onselect: () => void;
    danger?: boolean;
    disabled?: boolean;
    title?: string;
  }
</script>

<script lang="ts">
  /**
   * "⋯" button with a row's secondary actions (edit, delete, ...), so the
   * destructive ones aren't one stray click away next to everyday buttons.
   * The open menu lives in <body>, fixed-positioned: inside a table its
   * sticky actions cell would clip it and the next rows' cells would cover it.
   */
  import { tick } from "svelte";
  import { Ellipsis } from "@lucide/svelte";

  interface Props {
    items: RowMenuItem[];
    label?: string;
    disabled?: boolean;
  }

  let { items, label = "More actions", disabled = false }: Props = $props();

  let open = $state(false);
  let position = $state({ top: 0, right: 0 });
  let button: HTMLButtonElement | undefined = $state();
  let menu: HTMLDivElement | undefined = $state();

  async function toggle(e: MouseEvent & { currentTarget: HTMLButtonElement }) {
    if (open) return close();
    const rect = e.currentTarget.getBoundingClientRect();
    position = { top: rect.bottom + 4, right: window.innerWidth - rect.right };
    open = true;
    await tick();
    menu?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus();
  }

  function close(returnFocus = false) {
    open = false;
    if (returnFocus) button?.focus();
  }

  function select(item: RowMenuItem) {
    close();
    item.onselect();
  }

  function onKeydown(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === "Escape") {
      e.preventDefault();
      close(true);
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const buttons = [...(menu?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])];
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = e.key === "ArrowDown" ? index + 1 : index - 1;
    buttons[(next + buttons.length) % buttons.length]?.focus();
  }

  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return { destroy: () => node.remove() };
  }

  function onPointerDown(e: PointerEvent) {
    if (!open) return;
    const target = e.target as Node;
    if (!menu?.contains(target) && !button?.contains(target)) close();
  }
</script>

<svelte:window onkeydown={onKeydown} onpointerdown={onPointerDown} onresize={() => close()} onscroll={() => close()} />

<button
  bind:this={button}
  class="row-menu-btn"
  class:open
  type="button"
  aria-label={label}
  title={label}
  aria-haspopup="menu"
  aria-expanded={open}
  {disabled}
  onclick={toggle}
>
  <Ellipsis size={15} />
</button>

{#if open}
  <div
    bind:this={menu}
    use:portal
    class="row-menu"
    role="menu"
    style:top="{position.top}px"
    style:right="{position.right}px"
  >
    {#each items as item (item.label)}
      <button
        type="button"
        role="menuitem"
        class:danger={item.danger}
        disabled={item.disabled}
        title={item.title}
        onclick={() => select(item)}
      >
        {item.label}
      </button>
    {/each}
  </div>
{/if}

<style>
  .row-menu-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background: none;
    border: 1px solid transparent;
    border-radius: 6px;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .row-menu-btn:hover:not(:disabled),
  .row-menu-btn.open {
    background: var(--bg-surface-2);
    border-color: var(--border-strong);
    color: var(--text-primary);
  }

  .row-menu-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .row-menu-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .row-menu {
    position: fixed;
    z-index: 1000;
    min-width: 160px;
    padding: 0.25rem;
    background: var(--bg-surface);
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    display: flex;
    flex-direction: column;
  }

  .row-menu button {
    text-align: left;
    padding: 0.45rem 0.7rem;
    background: none;
    border: none;
    border-radius: 5px;
    color: var(--text-primary);
    font-size: 0.85rem;
    cursor: pointer;
  }

  .row-menu button:hover:not(:disabled),
  .row-menu button:focus-visible {
    background: var(--bg-surface-2);
    outline: none;
  }

  .row-menu button.danger {
    color: var(--danger);
  }

  .row-menu button:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
