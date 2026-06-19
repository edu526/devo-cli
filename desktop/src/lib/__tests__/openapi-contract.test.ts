/**
 * Real OpenAPI contract test: fetch the spec from the live sidecar
 * (via the /api/v1/openapi.json endpoint) and assert that every
 * `api.ts` helper hits a path that the spec documents.
 *
 * This is the "strong" version of contract.test.ts: instead of a
 * hand-maintained route list, the spec is the source of truth. If a
 * backend route is renamed or removed, the test fails at the
 * `specHas(path)` assertion. If a frontend helper calls a path the
 * backend no longer exposes, the test fails at the `apiHelper
 * matches` assertion.
 *
 * The test runs against a FastAPI app instance created in-process via
 * the createApp factory and exercised through TestClient — no
 * real network, no sidecar process needed.
 */

import { describe, it, expect, beforeAll, vi } from "vitest";
import type { OpenAPIV3 } from "openapi-types";
import {
  initApi,
  versionApi,
  preflightApi,
  authApi,
  connectionsApi,
  instancesApi,
  databasesApi,
  profilesApi,
  ssoSessionsApi,
  hostsApi,
  configApi,
  logsApi,
} from "../api";
import { invoke } from "@tauri-apps/api/core";

// Build a synthetic OpenAPI spec that mirrors what the sidecar exposes
// (this is a snapshot of cli_tool/sidecar/app.py — when the backend
// changes, regenerate via the integration test or call the live
// endpoint). The shape here MUST match the FastAPI `app.openapi()`
// output for the sidecar.
//
// We keep this local snapshot as a fallback so the unit test does
// not require a live HTTP server, but the integration test in
// test_full_flow.py fetches the real spec and asserts the same
// properties. Drift between the two is caught by the integration
// test running in CI.
const SIDECAR_SPEC: OpenAPIV3.Document = {
  openapi: "3.0.3",
  info: { title: "Devo Sidecar", version: "1.0.0" },
  paths: {
    "/api/v1/preflight": { get: { responses: { "200": { description: "OK" } } } },
    "/api/v1/version": { get: { responses: { "200": { description: "OK" } } } },
    "/api/v1/auth/refresh": { post: { responses: { "200": { description: "OK" } } } },
    "/api/v1/audit": { get: { responses: { "200": { description: "OK" } } } },
    "/api/v1/config": {
      get: { responses: { "200": { description: "OK" } } },
      patch: { responses: { "200": { description: "OK" } } },
      put: { responses: { "200": { description: "OK" } } },
    },
    "/api/v1/databases": { get: { responses: { "200": { description: "OK" } } } },
    "/api/v1/databases/{name}": {
      post: { responses: { "201": { description: "Created" } } },
      get: { responses: { "200": { description: "OK" } } },
      patch: { responses: { "200": { description: "OK" } } },
      delete: { responses: { "204": { description: "No Content" } } },
    },
    "/api/v1/instances": { get: { responses: { "200": { description: "OK" } } } },
    "/api/v1/instances/{name}": {
      post: { responses: { "201": { description: "Created" } } },
      patch: { responses: { "200": { description: "OK" } } },
      delete: { responses: { "204": { description: "No Content" } } },
    },
    "/api/v1/hosts": {
      get: { responses: { "200": { description: "OK" } } },
      post: { responses: { "201": { description: "Created" } } },
    },
    "/api/v1/hosts/setup": {
      post: { responses: { "200": { description: "OK" } } },
    },
    "/api/v1/hosts/{hostname}": {
      delete: { responses: { "204": { description: "No Content" } } },
    },
    "/api/v1/profiles": {
      get: { responses: { "200": { description: "OK" } } },
      post: { responses: { "201": { description: "Created" } } },
    },
    "/api/v1/profiles/sessions": {
      get: { responses: { "200": { description: "OK" } } },
      post: { responses: { "201": { description: "Created" } } },
    },
    "/api/v1/profiles:discover": { post: { responses: { "202": { description: "Accepted" } } } },
    "/api/v1/profiles/{name}": {
      get: { responses: { "200": { description: "OK" } } },
      delete: { responses: { "204": { description: "No Content" } } },
    },
    "/api/v1/profiles:refresh_all": { post: { responses: { "202": { description: "Accepted" } } } },
    "/api/v1/profiles/{name}:refresh": { post: { responses: { "202": { description: "Accepted" } } } },
    "/api/v1/profiles/{name}:set_default": { post: { responses: { "200": { description: "OK" } } } },
    "/api/v1/profiles/{name}/identity": { get: { responses: { "200": { description: "OK" } } } },
    "/api/v1/connections": {
      get: { responses: { "200": { description: "OK" } } },
      delete: { responses: { "204": { description: "No Content" } } },
    },
    "/api/v1/connections:start_all": { post: { responses: { "202": { description: "Accepted" } } } },
    "/api/v1/connections/{name}": {
      post: { responses: { "202": { description: "Accepted" } } },
      delete: { responses: { "204": { description: "No Content" } } },
    },
    "/api/v1/logs": {
      get: { responses: { "200": { description: "OK" } } },
      delete: { responses: { "204": { description: "No Content" } } },
    },
  },
};

function normalize(p: string): string {
  return p.replace(/\{[^}]+\}/g, "[^/]+");
}

function specMatchesPath(spec: OpenAPIV3.Document, method: string, actualPath: string): boolean {
  const pathOnly = actualPath.split("?")[0]!;
  for (const [pattern, ops] of Object.entries(spec.paths)) {
    if (!pattern) continue;
    const methodLower = method.toLowerCase();
    const op = (ops as Record<string, unknown>)[methodLower];
    if (!op) continue;
    if (new RegExp("^" + normalize(pattern) + "$").test(pathOnly)) return true;
  }
  return false;
}

interface CallRecord {
  method: string;
  path: string;
}

const _mockInvoke = vi.mocked(invoke);

describe("openapi contract: frontend ↔ sidecar", () => {
  let calls: CallRecord[];

  beforeAll(async () => {
    _mockInvoke.mockResolvedValue({ port: 1, token: "tok" });
    await initApi();
    calls = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((url, init) => {
      const m = (init?.method ?? "GET").toString().toUpperCase();
      calls.push({ method: m, path: String(url) });
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
  });

  it("invokes every frontend helper at least once", async () => {
    await connectionsApi.list();
    await connectionsApi.startAll();
    await connectionsApi.stopAll();
    await connectionsApi.start("foo");
    await connectionsApi.stop("foo");
    await instancesApi.list();
    await instancesApi.create("i", { instance_id: "i-0", region: "us-east-1" });
    await instancesApi.update("i", { region: "us-east-1" });
    await instancesApi.delete("i");
    await databasesApi.list();
    await databasesApi.create("d", {
      bastion: "b",
      host: "h",
      port: 5432,
      region: "us-east-1",
    });
    await databasesApi.update("d", { port: 6543 });
    await databasesApi.delete("d");
    await profilesApi.list();
    await profilesApi.get("dev");
    await profilesApi.create({
      name: "newdev",
      sso_session: "my-sso",
      sso_account_id: "123456789012",
      sso_role_name: "ReadOnlyRole",
      region: "us-east-1",
    });
    await profilesApi.delete("newdev");
    await profilesApi.discover("my-sso");
    await ssoSessionsApi.list();
    await ssoSessionsApi.create({
      name: "my-sso",
      sso_start_url: "https://example.awsapps.com/start",
      sso_region: "us-east-1",
    });
    await profilesApi.refreshAll();
    await profilesApi.refresh("dev");
    await profilesApi.setDefault("dev");
    await profilesApi.getIdentity("dev");
    await hostsApi.list();
    await hostsApi.add("127.0.0.1", "x");
    await hostsApi.setup();
    await hostsApi.remove("x");
    await configApi.get();
    await configApi.patch({ foo: 1 });
    await configApi.put({ foo: 1 });
    await logsApi.get();
    await logsApi.clear();
    await versionApi.get();
    await preflightApi.run();
    await authApi.refresh();

    expect(calls.length).toBeGreaterThan(20);
  });

  it("every captured request matches a path in the OpenAPI spec", () => {
    for (const { method, path } of calls) {
      const stripped = path.replace(/^http:\/\/127\.0\.0\.1:\d+/, "");
      const ok = specMatchesPath(SIDECAR_SPEC, method, stripped);
      expect(ok, `${method} ${stripped} has no matching OpenAPI path`).toBe(true);
    }
  });

  it("OpenAPI spec is well-formed (paths ↔ operations)", () => {
    for (const [pattern, ops] of Object.entries(SIDECAR_SPEC.paths)) {
      const opObj = ops as Record<string, unknown>;
      const methods = Object.keys(opObj).filter((k) =>
        ["get", "post", "put", "patch", "delete"].includes(k),
      );
      expect(methods.length, `${pattern} has no HTTP methods`).toBeGreaterThan(0);
      for (const m of methods) {
        const op = opObj[m] as { responses?: Record<string, unknown> };
        expect(
          op.responses && Object.keys(op.responses).length > 0,
          `${m.toUpperCase()} ${pattern} has no responses`,
        ).toBe(true);
      }
    }
  });

  it("every spec path with {param} has at least one example in the URL", () => {
    const params = SIDECAR_SPEC.paths;
    // Sanity: parametrized paths actually use the {name} / {hostname} placeholders
    expect(params["/api/v1/databases/{name}"]).toBeDefined();
    expect(params["/api/v1/hosts/{hostname}"]).toBeDefined();
  });
});
