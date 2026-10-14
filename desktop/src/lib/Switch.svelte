<script lang="ts">
  /**
   * On/off switch for a setting. Controlled: clicking it only asks `onchange`
   * to save the new value, and it shows `checked` until the parent updates it,
   * so a save that fails never leaves it showing a value that wasn't saved.
   */
  interface Props {
    checked: boolean;
    onchange: () => void;
    disabled?: boolean;
    id?: string;
    describedby?: string;
  }

  let { checked, onchange, disabled = false, id, describedby }: Props = $props();

  function handleChange(e: Event & { currentTarget: HTMLInputElement }) {
    e.currentTarget.checked = checked;
    onchange();
  }
</script>

<input
  {id}
  class="switch"
  type="checkbox"
  role="switch"
  {checked}
  {disabled}
  aria-checked={checked}
  aria-describedby={describedby}
  onchange={handleChange}
/>

<style>
  .switch {
    appearance: none;
    position: relative;
    flex-shrink: 0;
    width: 2.25rem;
    height: 1.25rem;
    margin: 0;
    border-radius: 999px;
    background: var(--border-strong);
    cursor: pointer;
    transition: background 0.15s;
  }

  .switch::before {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: calc(1.25rem - 4px);
    height: calc(1.25rem - 4px);
    border-radius: 50%;
    background: #fff;
    transition: transform 0.15s;
  }

  .switch:checked {
    background: var(--accent);
  }

  .switch:checked::before {
    transform: translateX(1rem);
  }

  .switch:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .switch:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
</style>
