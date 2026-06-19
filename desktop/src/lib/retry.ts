/**
 * Retry helper for transient network failures.
 *
 * The Tauri webview on some platforms throws `TypeError: Load failed`
 * on the first POST after a GET (or after the modal opens). The request
 * succeeds on the next attempt, often without any user action. The
 * sidecar logs show no record of the failed request — the failure is
 * purely client-side, so retrying is the only fix that works without
 * patching the webview.
 *
 * Rules:
 *  - Only retries on `TypeError` (the catch-all fetch() throws for
 *    network-level failures: connection refused, CORS preflight blocked,
 *    request aborted, webview quirk). `ApiError` (4xx/5xx from the
 *    sidecar) is surfaced immediately — those are real server errors.
 *  - Linear-ish backoff: each attempt waits `baseMs * attempt` ms.
 *  - `onRetry(n)` is called BEFORE attempt n+1, so the caller can
 *    surface a "Retrying…" indicator. 1-based: first call is for
 *    the second attempt.
 *  - Returns the first successful result, or throws the last error
 *    after all attempts fail.
 */
export async function retryNetworkErrors<T>(
  fn: () => Promise<T>,
  opts: { attempts?: number; baseMs?: number; onRetry?: (nextAttempt: number) => void } = {},
): Promise<T> {
  const attempts = opts.attempts ?? 3;
  const baseMs = opts.baseMs ?? 600;
  let lastErr: unknown;
  for (let i = 1; i <= attempts; i++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      const isNetwork = e instanceof TypeError;
      if (!isNetwork || i === attempts) throw e;
      opts.onRetry?.(i + 1);
      await new Promise((r) => setTimeout(r, baseMs * i));
    }
  }
  throw lastErr;
}
