<script lang="ts">
  import { answerConfirm, pendingConfirm } from "./confirm";

  let confirmButton: HTMLButtonElement | undefined = $state();

  // Focus the action like the native dialog did: Enter confirms, Escape cancels.
  $effect(() => {
    if ($pendingConfirm) confirmButton?.focus();
  });

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      answerConfirm(false);
    }
  }
</script>

{#if $pendingConfirm}
  <div class="modal-backdrop confirm-backdrop" role="presentation">
    <div
      class="modal modal-confirm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-message"
      tabindex="-1"
      onkeydown={onKeydown}
    >
      <h2 id="confirm-title">{$pendingConfirm.title}</h2>
      <p id="confirm-message" class="confirm-message">{$pendingConfirm.message}</p>
      <div class="modal-actions">
        <button class="btn-secondary" onclick={() => answerConfirm(false)}>Cancel</button>
        <button
          bind:this={confirmButton}
          class={$pendingConfirm.danger ? "btn-danger" : "btn-primary"}
          onclick={() => answerConfirm(true)}
        >
          {$pendingConfirm.confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Above page modals: it can be asked from one (e.g. Delete in Edit Database). */
  .confirm-backdrop {
    z-index: 110;
  }
  .modal-confirm {
    min-width: 380px;
  }
  .confirm-message {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.5;
    color: var(--text-muted);
    white-space: pre-line;
  }
</style>
