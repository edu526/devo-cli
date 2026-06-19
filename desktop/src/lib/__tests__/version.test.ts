import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { initApi, versionApi, ApiError } from "../api";

const mockInvoke = vi.mocked(invoke);

describe("versionApi", () => {
  beforeEach(async () => {
    mockInvoke.mockReset();
    mockInvoke.mockResolvedValue({ port: 1, token: "tok" });
    await initApi();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed version info on 200", async () => {
    const body = {
      sidecar_version: "3.9.0",
      server_version: "3.9.0",
      build_date: null,
      update_available: false,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(body), { status: 200 }),
    );

    const result = await versionApi.get();

    expect(result).toEqual(body);
  });

  it("hits GET /version (no auth required)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 }),
    );

    await versionApi.get();

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(url).toContain("/version");
    expect(init?.method).toBe("GET");
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBeDefined();
  });

  it("propagates ApiError on non-2xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    );

    await expect(versionApi.get()).rejects.toBeInstanceOf(ApiError);
  });
});
