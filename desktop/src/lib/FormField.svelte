<script lang="ts">
  // Field wrapper providing a consistent label / hint / error layout.
  // The error slot is controlled externally so the parent owns validation.
  // Children render the actual control (input, select, textarea).

  import type { Snippet } from "svelte";

  interface Props {
    label: string;
    error?: string | null;
    hint?: string;
    required?: boolean;
    children?: Snippet;
  }

  let { label, error = null, hint, required = false, children }: Props = $props();

  const id = `field-${Math.random().toString(36).slice(2, 9)}`;
</script>

<div class="form-field" class:has-error={!!error}>
  <label class="field-label" for={id}>
    {label}
    {#if required}<span class="required" aria-label="required">*</span>{/if}
  </label>
  <div class="control" {id}>
    {@render children?.()}
  </div>
  {#if error}
    <p class="error" role="alert">{error}</p>
  {:else if hint}
    <p class="hint">{hint}</p>
  {/if}
</div>

<style>
  .form-field {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    margin-bottom: 0.85rem;
  }
  label {
    font-size: 0.8rem;
    color: #94a3b8;
    font-weight: 500;
  }
  /* Override the global .modal label rule (flex-direction: column)
     which would push the required * onto a new line below the label
     text. Keep the * inline with the label. */
  .field-label {
    display: flex;
    flex-direction: row;
    align-items: baseline;
    gap: 0.15rem;
  }
  .required {
    color: #f87171;
    margin-left: 0.15rem;
  }
  .control {
    display: block;
  }
  .control :global(input),
  .control :global(select),
  .control :global(textarea) {
    width: 100%;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 0.85rem;
    padding: 0.45rem 0.6rem;
    font-family: inherit;
  }
  .control :global(select) {
    -webkit-appearance: none;
    appearance: none;
    padding-right: 2rem;
    cursor: pointer;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='none' stroke='%2394a3b8' stroke-width='1.5' d='M1 1l4 4 4-4'/></svg>");
    background-repeat: no-repeat;
    background-position: right 0.6rem center;
  }
  .control :global(select option) {
    background: #1a1a1a;
    color: #e0e0e0;
  }
  .control :global(input:focus),
  .control :global(select:focus),
  .control :global(textarea:focus) {
    outline: none;
    border-color: #4f8ef7;
  }
  .control :global(input::placeholder) {
    color: #6a6a6a;
  }
  .has-error .control :global(input),
  .has-error .control :global(select),
  .has-error .control :global(textarea) {
    border-color: #f87171;
  }
  .error {
    color: #f87171;
    font-size: 0.75rem;
    margin: 0;
  }
  .hint {
    color: #6a6a6a;
    font-size: 0.72rem;
    margin: 0;
  }
</style>
