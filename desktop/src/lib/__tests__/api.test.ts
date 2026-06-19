import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import {
  initApi,
  getBaseUrl,
  getToken,
  ApiError,
  connectionsApi,
  instancesApi,
  databasesApi,
  profilesApi,
  hostsApi,
  configApi,
  logsApi,
} from "../api";

const mockInvoke = vi.mocked(invoke);

describe("api", () => {
  beforeEach(() => {
    mockInvoke.mockReset();
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("initApi", () => {
    it("stores port and token returned by get_sidecar_info", async () => {
      mockInvoke.mockResolvedValueOnce({ port: 12345, token: "secret" });

      const info = await initApi();

      expect(info).toEqual({ port: 12345, token: "secret" });
      expect(getBaseUrl()).toBe("http://127.0.0.1:12345/api/v1");
      expect(getToken()).toBe("secret");
      expect(mockInvoke).toHaveBeenCalledWith("get_sidecar_info");
    });
  });

  describe("ApiError", () => {
    it("formats string detail as message", () => {
      const err = new ApiError(404, "Not found");
      expect(err.message).toBe("Not found");
      expect(err.status).toBe(404);
      expect(err.name).toBe("ApiError");
    });

    it("stringifies non-string detail as message", () => {
      const err = new ApiError(400, { foo: "bar" });
      expect(err.message).toBe('{"foo":"bar"}');
    });
  });

  describe("fetch wrapper", () => {
    it("attaches bearer token to every request", async () => {
      mockInvoke.mockResolvedValueOnce({ port: 1, token: "tok" });
      await initApi();

      const fetchSpy = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));

      await connectionsApi.list();

      const [, init] = fetchSpy.mock.calls[0]!;
      const headers = (init?.headers ?? {}) as Record<string, string>;
      expect(headers.Authorization).toBe("Bearer tok");
      expect(headers["Content-Type"]).toBe("application/json");
    });

    it("returns undefined for 204 No Content responses", async () => {
      mockInvoke.mockResolvedValueOnce({ port: 1, token: "tok" });
      await initApi();
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(null, { status: 204 }));

      const result = await connectionsApi.stopAll();
      expect(result).toBeUndefined();
    });

    it("throws ApiError with status + detail on non-2xx", async () => {
      mockInvoke.mockResolvedValueOnce({ port: 1, token: "tok" });
      await initApi();
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Connection not found" }), { status: 404 }),
      );

      await expect(connectionsApi.stop("missing")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
        message: "Connection not found",
      });
    });

    it("falls back to statusText when body is not JSON", async () => {
      mockInvoke.mockResolvedValueOnce({ port: 1, token: "tok" });
      await initApi();
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        new Response("plain", { status: 500, statusText: "Server Error" }),
      );

      await expect(connectionsApi.list()).rejects.toMatchObject({
        status: 500,
        message: "Server Error",
      });
    });

    it("retries once on 401 after a successful /auth/refresh", async () => {
      mockInvoke.mockResolvedValueOnce({ port: 1, token: "old-tok" });
      await initApi();

      const fetchSpy = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ detail: "expired" }), { status: 401 }),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ token: "new-tok", expires_at: 0, issued_at: 0 }),
            { status: 200 },
          ),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ ok: true }), { status: 200 }),
        );

      const result = await connectionsApi.list();
      expect(result).toEqual({ ok: true });
      // 1) original list, 2) /auth/refresh, 3) retried list
      expect(fetchSpy).toHaveBeenCalledTimes(3);
      const retried = fetchSpy.mock.calls[2]!;
      const retriedHeaders = (retried[1]?.headers ?? {}) as Record<string, string>;
      expect(retriedHeaders.Authorization).toBe("Bearer new-tok");
      // Token getter reflects the rotated token
      expect(getToken()).toBe("new-tok");
    });

    it("surfaces the original 401 when /auth/refresh itself fails", async () => {
      mockInvoke.mockResolvedValueOnce({ port: 1, token: "old-tok" });
      await initApi();

      const fetchSpy = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValueOnce(new Response(null, { status: 401 }))
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ detail: "too old" }), { status: 401 }),
        );

      await expect(connectionsApi.list()).rejects.toMatchObject({ status: 401 });
      expect(fetchSpy).toHaveBeenCalledTimes(2);
    });
  });

  describe("endpoint shapes", () => {
    beforeEach(async () => {
      mockInvoke.mockResolvedValueOnce({ port: 1, token: "tok" });
      await initApi();
      vi.spyOn(globalThis, "fetch").mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({}), { status: 200 })),
      );
    });

    it("connectionsApi maps to expected paths", async () => {
      const fetchSpy = vi.mocked(globalThis.fetch);
      await connectionsApi.list();
      expect(fetchSpy.mock.calls[0]![0]).toContain("/connections");
      await connectionsApi.startAll();
      expect(fetchSpy.mock.calls[1]![0]).toContain("/connections:start_all");
      await connectionsApi.start("db1");
      expect(fetchSpy.mock.calls[2]![0]).toContain("/connections/db1");
    });

    it("instancesApi supports CRUD with body", async () => {
      const fetchSpy = vi.mocked(globalThis.fetch);
      await instancesApi.create("prod", { instance_id: "i-1", region: "us-east-1" });
      const [url, init] = fetchSpy.mock.calls[0]!;
      expect(url).toContain("/instances/prod");
      expect(init?.method).toBe("POST");
      expect(JSON.parse(init?.body as string)).toEqual({
        instance_id: "i-1",
        region: "us-east-1",
      });
    });

    it("databasesApi.update sends PATCH", async () => {
      const fetchSpy = vi.mocked(globalThis.fetch);
      await databasesApi.update("db1", { port: 5433 });
      expect(fetchSpy.mock.calls[0]![0]).toContain("/databases/db1");
      expect(fetchSpy.mock.calls[0]![1]?.method).toBe("PATCH");
    });

    it("profilesApi.refresh uses :refresh action", async () => {
      const fetchSpy = vi.mocked(globalThis.fetch);
      await profilesApi.refresh("dev");
      expect(fetchSpy.mock.calls[0]![0]).toContain("/profiles/dev:refresh");
    });

    it("hostsApi.remove encodes hostname in path", async () => {
      const fetchSpy = vi.mocked(globalThis.fetch);
      await hostsApi.remove("db.example.com");
      expect(fetchSpy.mock.calls[0]![0]).toContain("/hosts/db.example.com");
    });

    it("configApi.patch sends PATCH with body", async () => {
      const fetchSpy = vi.mocked(globalThis.fetch);
      await configApi.patch({ ssm: { foo: 1 } });
      expect(fetchSpy.mock.calls[0]![1]?.method).toBe("PATCH");
    });

    it("logsApi.get passes lines query param", async () => {
      const fetchSpy = vi.mocked(globalThis.fetch);
      await logsApi.get(500);
      expect(fetchSpy.mock.calls[0]![0]).toContain("/logs?lines=500");
    });
  });
});
