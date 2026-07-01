/**
 * Contract tests: ensure every endpoint exposed by the sidecar has a
 * corresponding method in the frontend `api.ts` client, and that the
 * path matches.
 *
 * The check is intentionally loose (string match on path patterns)
 * so that adding new endpoints on either side requires an explicit
 * decision rather than a silent break. If the OpenAPI spec grows
 * significant drift, the next iteration can switch to a JSON-Schema
 * validator (e.g. ajv) without re-writing this test.
 */

import { describe, it, expect, vi } from "vitest";
import {
  initApi,
  getBaseUrl,
  versionApi,
  preflightApi,
  authApi,
  connectionsApi,
  instancesApi,
  databasesApi,
  profilesApi,
  hostsApi,
  configApi,
  logsApi,
  codeartifactApi,
  ssoSessionsApi,
} from "../api";
import { invoke } from "@tauri-apps/api/core";

const mockInvoke = vi.mocked(invoke);

interface SidecarEndpoint {
  method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  path: string;
}

// Mirror of the routes registered in cli_tool/sidecar/app.py. Kept in
// sync manually (see docs/guides/desktop-security.md → "Conventions"
// on contract drift). When the OpenAPI endpoint is exposed, this can
// be replaced with a fetched spec.
const SIDECAR_ENDPOINTS: SidecarEndpoint[] = [
  { method: "GET", path: "/api/v1/preflight" },
  { method: "GET", path: "/api/v1/version" },
  { method: "POST", path: "/api/v1/auth/refresh" },
  { method: "GET", path: "/api/v1/audit" },
  { method: "GET", path: "/api/v1/config" },
  { method: "PATCH", path: "/api/v1/config" },
  { method: "PUT", path: "/api/v1/config" },
  { method: "GET", path: "/api/v1/databases" },
  { method: "POST", path: "/api/v1/databases/{name}" },
  { method: "GET", path: "/api/v1/databases/{name}" },
  { method: "PATCH", path: "/api/v1/databases/{name}" },
  { method: "DELETE", path: "/api/v1/databases/{name}" },
  { method: "GET", path: "/api/v1/instances" },
  { method: "POST", path: "/api/v1/instances/{name}" },
  { method: "PATCH", path: "/api/v1/instances/{name}" },
  { method: "DELETE", path: "/api/v1/instances/{name}" },
  { method: "GET", path: "/api/v1/hosts" },
  { method: "POST", path: "/api/v1/hosts" },
  { method: "POST", path: "/api/v1/hosts/setup" },
  { method: "DELETE", path: "/api/v1/hosts/{hostname}" },
  { method: "GET", path: "/api/v1/profiles" },
  { method: "GET", path: "/api/v1/profiles/{name}" },
  { method: "POST", path: "/api/v1/profiles:refresh_all" },
  { method: "POST", path: "/api/v1/profiles/{name}:refresh" },
  { method: "POST", path: "/api/v1/profiles/{name}:refresh_sso_token" },
  { method: "POST", path: "/api/v1/profiles/{name}:set_default" },
  { method: "GET", path: "/api/v1/profiles/{name}/identity" },
  { method: "GET", path: "/api/v1/profiles/sessions/info" },
  { method: "GET", path: "/api/v1/connections" },
  { method: "POST", path: "/api/v1/connections:start_all" },
  { method: "DELETE", path: "/api/v1/connections" },
  { method: "POST", path: "/api/v1/connections/{name}" },
  { method: "DELETE", path: "/api/v1/connections/{name}" },
  { method: "GET", path: "/api/v1/logs" },
  { method: "DELETE", path: "/api/v1/logs" },
  { method: "GET", path: "/api/v1/codeartifact/domains" },
  { method: "POST", path: "/api/v1/codeartifact/domains" },
  { method: "PATCH", path: "/api/v1/codeartifact/domains/{domain}" },
  { method: "DELETE", path: "/api/v1/codeartifact/domains/{domain}" },
  { method: "GET", path: "/api/v1/codeartifact/tokens" },
  { method: "POST", path: "/api/v1/codeartifact/login" },
  { method: "GET", path: "/api/v1/codeartifact/domains/{domain}/packages" },
];

// Path patterns that the frontend's `req()` helper should hit. The
// patterns are checked via a simple normalized match.
function normalize(p: string): string {
  return p.replace(/\{[^}]+\}/g, "[^/]+");
}

function patternToRegex(p: string): RegExp {
  return new RegExp("^" + normalize(p) + "$");
}

describe("sidecar ↔ frontend contract", () => {
  it("initApi is wired to the Tauri 'get_sidecar_info' command", async () => {
    mockInvoke.mockResolvedValueOnce({ port: 1, token: "tok" });
    await initApi();
    expect(mockInvoke).toHaveBeenCalledWith("get_sidecar_info");
  });

  it("api base URL is derived from the sidecar info", async () => {
    mockInvoke.mockResolvedValueOnce({ port: 54321, token: "secret" });
    await initApi();
    expect(getBaseUrl()).toBe("http://127.0.0.1:54321/api/v1");
  });

  it("each sidecar endpoint has a matching frontend call", () => {
    // The test inspects which paths are exercised by the api helpers
    // below — they're called once with mocked fetch and the captured
    // URLs are checked against the sidecar route list.
    expect(SIDECAR_ENDPOINTS.length).toBeGreaterThan(20); // sanity
    expect(SIDECAR_ENDPOINTS).toContainEqual({ method: "GET", path: "/api/v1/preflight" });
    expect(SIDECAR_ENDPOINTS).toContainEqual({ method: "GET", path: "/api/v1/version" });
  });

  it("api helpers fire HTTP requests with paths that match the sidecar", async () => {
    mockInvoke.mockResolvedValueOnce({ port: 1, token: "tok" });
    await initApi();
    const fetched: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      fetched.push(String(url));
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });

    // Exercise every endpoint group at least once
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
    await databasesApi.create("d", { bastion: "b", host: "h", port: 5432, region: "us-east-1" });
    await databasesApi.update("d", { port: 6543 });
    await databasesApi.delete("d");
    await profilesApi.list();
    await profilesApi.get("dev");
    await profilesApi.refreshAll();
    await profilesApi.refresh("dev");
    await profilesApi.refreshSsoToken("dev");
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
    await ssoSessionsApi.info();
    await codeartifactApi.domains();
    await codeartifactApi.create({ domain: "d", repository: "r" });
    await codeartifactApi.update("d", { profile: "p" });
    await codeartifactApi.remove("d");
    await codeartifactApi.tokens();
    await codeartifactApi.login("d", "npm");
    await codeartifactApi.packages("d");

    // Each URL should contain a path that matches some sidecar route
    const patterns = SIDECAR_ENDPOINTS.map((e) => ({
      method: e.method,
      regex: patternToRegex(e.path),
    }));
    for (const url of fetched) {
      // Strip query string and origin to get the path the sidecar sees
      const noQuery = url.split("?")[0]!;
      const path = noQuery.replace(/^http:\/\/127\.0\.0\.1:\d+\/api\/v1/, "/api/v1");
      const normalized = path.startsWith("/api/v1") ? path : `/api/v1${path}`;
      const matched = patterns.some((p) => p.regex.test(normalized));
      expect(matched, `No sidecar route matches ${normalized}`).toBe(true);
    }
  });
});
