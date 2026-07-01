import { describe, it, expect, vi } from "vitest";
import { retryNetworkErrors } from "../retry";

describe("retryNetworkErrors", () => {
  it("returns the result on first success", async () => {
    const fn = vi.fn().mockResolvedValue("ok");
    const r = await retryNetworkErrors(fn);
    expect(r).toBe("ok");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("retries on TypeError and returns the eventual success", async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Load failed"))
      .mockResolvedValue("ok");
    const r = await retryNetworkErrors(fn, { baseMs: 1 });
    expect(r).toBe("ok");
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("does NOT retry on a non-TypeError (real server error)", async () => {
    class FakeApiError extends Error {
      constructor(public status: number, public detail: unknown) {
        super(String(detail));
        this.name = "ApiError";
      }
    }
    const err = new FakeApiError(409, "Profile exists");
    const fn = vi.fn().mockRejectedValue(err);
    await expect(retryNetworkErrors(fn, { baseMs: 1 })).rejects.toBe(err);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("gives up after `attempts` and throws the last error", async () => {
    const err = new TypeError("Load failed");
    const fn = vi.fn().mockRejectedValue(err);
    await expect(
      retryNetworkErrors(fn, { attempts: 3, baseMs: 1 }),
    ).rejects.toBe(err);
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("calls onRetry with the next attempt number before each retry", async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("x"))
      .mockRejectedValueOnce(new TypeError("x"))
      .mockResolvedValue("ok");
    const onRetry = vi.fn();
    await retryNetworkErrors(fn, { baseMs: 1, onRetry });
    expect(onRetry).toHaveBeenCalledTimes(2);
    expect(onRetry).toHaveBeenNthCalledWith(1, 2);
    expect(onRetry).toHaveBeenNthCalledWith(2, 3);
  });

  it("waits `baseMs * attempt` ms between retries (linear backoff)", async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("x"))
      .mockResolvedValue("ok");
    const start = Date.now();
    await retryNetworkErrors(fn, { baseMs: 50 });
    const elapsed = Date.now() - start;
    // CI environments (like Ubuntu runners) can occasionally trigger setTimeout
    // a millisecond or two early due to timer resolution and event loop drift.
    expect(elapsed).toBeGreaterThanOrEqual(45);
  });
});
