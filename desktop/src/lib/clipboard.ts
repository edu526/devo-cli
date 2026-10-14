/** Copy text, falling back to execCommand when the clipboard API is blocked. */
export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // The clipboard API can be blocked (no secure context, denied
    // permission). The legacy path still works there, so the user is never
    // left without a way to copy.
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
    } catch {
      /* nothing else we can do without clipboard access */
    }
    document.body.removeChild(ta);
  }
}
