import { get, writable } from "svelte/store";

/**
 * In-app confirmation dialog, used instead of the browser's `confirm()` (a
 * native "localhost:5173 says…" box that doesn't look like Devo). One
 * `<ConfirmDialog />` in App.svelte shows whatever is asked here:
 *
 *   if (!(await askConfirm({ title: "Delete database?", ... }))) return;
 */
export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel: string;
  /** Red confirm button, for destructive actions. */
  danger?: boolean;
}

export interface ConfirmRequest extends ConfirmOptions {
  resolve: (confirmed: boolean) => void;
}

export const pendingConfirm = writable<ConfirmRequest | null>(null);

/** Resolves true if the user confirms, false if they cancel. */
export function askConfirm(options: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    // A new question replaces one still open, which counts as cancelled.
    get(pendingConfirm)?.resolve(false);
    pendingConfirm.set({ ...options, resolve });
  });
}

export function answerConfirm(confirmed: boolean): void {
  const request = get(pendingConfirm);
  pendingConfirm.set(null);
  request?.resolve(confirmed);
}
