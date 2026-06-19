import { invoke } from "@tauri-apps/api/core";
import { logError } from "./error-log";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SidecarInfo {
  port: number;
  token: string;
}

export interface ConnectionRecord {
  name: string;
  state: "starting" | "connecting" | "connected" | "stopped" | "error" | "expired_credentials";
  local_port: number;
  error: string | null;
  uptime_seconds?: number;
  attempts?: number;
  last_error_at?: number | null;
}

export interface InstanceRecord {
  instance_id: string;
  region: string;
  profile?: string;
}

export interface InstanceIn {
  instance_id: string;
  region?: string;
  profile?: string;
}

export interface DatabaseRecord {
  bastion: string;
  host: string;
  port: number;
  region: string;
  profile?: string;
  local_port?: number;
  local_address: string;
}

export interface DatabaseIn {
  bastion: string;
  host: string;
  port: number;
  region?: string;
  profile?: string;
  local_port?: number;
  local_address?: string;
}

export interface ProfileRecord {
  name: string;
  source: "sso" | "both";
  expiration: string | null;
  seconds_remaining: number | null;
  status: "valid" | "expiring" | "expired" | "unknown";
  is_default: boolean;
}

export interface IdentityRecord {
  account_id: string;
  user_id: string;
  arn: string;
}

export interface HostRecord {
  ip: string;
  hostname: string;
}

// ── Client internals ──────────────────────────────────────────────────────────

let _baseUrl = "";
let _token = "";
let _refreshInFlight: Promise<string> | null = null;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.name = "ApiError";
  }
}

export async function initApi(): Promise<SidecarInfo> {
  const info = await invoke<SidecarInfo>("get_sidecar_info");
  _baseUrl = `http://127.0.0.1:${info.port}/api/v1`;
  _token = info.token;
  return info;
}

export function getBaseUrl(): string {
  return _baseUrl;
}

export function getToken(): string {
  return _token;
}

export interface RefreshResponse {
  token: string;
  expires_at: number;
  issued_at: number;
}

export const authApi = {
  refresh: () => req<RefreshResponse>("POST", "/auth/refresh"),
};

async function _refreshToken(): Promise<string> {
  // Coalesce concurrent 401s into a single /auth/refresh roundtrip.
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = (async () => {
    try {
      const res = await fetch(`${_baseUrl}/auth/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${_token}` },
      });
      if (!res.ok) {
        throw new ApiError(res.status, `Token refresh failed: ${res.statusText}`);
      }
      const body = (await res.json()) as RefreshResponse;
      _token = body.token;
      return _token;
    } finally {
      _refreshInFlight = null;
    }
  })();
  return _refreshInFlight;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const send = () =>
    fetch(`${_baseUrl}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${_token}`,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  let res: Response;
  try {
    res = await send();
  } catch (e) {
    // CORS rejection, sidecar down, DNS fail, abort, etc. — these never
    // produce an HTTP response so the sidecar has no log of them. Capture
    // them client-side so the user can see why the call never landed.
    const msg = e instanceof Error ? e.message : String(e);
    logError("api", `${method} ${path} failed: ${msg}`, _baseUrl);
    throw e;
  }

  // On 401, try refreshing the token once. /auth/refresh itself is exempt
  // from retry to avoid an infinite loop.
  if (res.status === 401 && path !== "/auth/refresh") {
    try {
      await _refreshToken();
      res = await send();
    } catch {
      // refresh failed — fall through and let the original 401 surface
    }
  }

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const json = await res.json();
      detail = json.detail ?? json;
    } catch {
      // response body not parseable; fall through with statusText
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

// ── Endpoint groups ───────────────────────────────────────────────────────────

export const connectionsApi = {
  list: () => req<ConnectionRecord[]>("GET", "/connections"),
  startAll: () => req<ConnectionRecord[]>("POST", "/connections:start_all"),
  stopAll: () => req<void>("DELETE", "/connections"),
  start: (name: string) => req<ConnectionRecord>("POST", `/connections/${name}`),
  stop: (name: string) => req<void>("DELETE", `/connections/${name}`),
};

export const instancesApi = {
  list: () => req<Record<string, InstanceRecord>>("GET", "/instances"),
  create: (name: string, body: InstanceIn) =>
    req<InstanceRecord>("POST", `/instances/${name}`, body),
  update: (name: string, body: Partial<InstanceIn>) =>
    req<InstanceRecord>("PATCH", `/instances/${name}`, body),
  delete: (name: string) => req<void>("DELETE", `/instances/${name}`),
};

export const databasesApi = {
  list: () => req<Record<string, DatabaseRecord>>("GET", "/databases"),
  create: (name: string, body: DatabaseIn) =>
    req<DatabaseRecord>("POST", `/databases/${name}`, body),
  update: (name: string, body: Partial<DatabaseIn>) =>
    req<DatabaseRecord>("PATCH", `/databases/${name}`, body),
  delete: (name: string) => req<void>("DELETE", `/databases/${name}`),
};

export const profilesApi = {
  list: () => req<ProfileRecord[]>("GET", "/profiles"),
  get: (name: string) => req<ProfileRecord>("GET", `/profiles/${name}`),
  refreshAll: () => req<{ status: string; message: string }>("POST", "/profiles:refresh_all"),
  refresh: (name: string) =>
    req<{ status: string; message: string }>("POST", `/profiles/${name}:refresh`),
  setDefault: (name: string) => req<{ name: string }>("POST", `/profiles/${name}:set_default`),
  getIdentity: (name: string) => req<IdentityRecord>("GET", `/profiles/${name}/identity`),
};

export const hostsApi = {
  list: () => req<HostRecord[]>("GET", "/hosts"),
  add: (ip: string, hostname: string) => req<HostRecord>("POST", "/hosts", { ip, hostname }),
  remove: (hostname: string) => req<void>("DELETE", `/hosts/${hostname}`),
  setup: (db_names?: string[]) =>
    req<{ succeeded: HostSetupEntry[]; failed: HostSetupFailure[] }>("POST", "/hosts/setup", {
      db_names: db_names ?? null,
    }),
};

export interface HostSetupEntry {
  name: string;
  host: string;
  ip: string;
  local_port: number;
  port_reassigned: boolean;
}

export interface HostSetupFailure {
  name: string;
  host: string;
  error: string;
  needs_elevation: boolean;
}

export const configApi = {
  get: () => req<Record<string, unknown>>("GET", "/config"),
  patch: (body: Record<string, unknown>) => req<Record<string, unknown>>("PATCH", "/config", body),
  put: (body: Record<string, unknown>) => req<Record<string, unknown>>("PUT", "/config", body),
};

export const logsApi = {
  get: (lines = 300) => req<string[]>("GET", `/logs?lines=${lines}`),
  clear: () => req<void>("DELETE", "/logs"),
};

export interface PreflightPayload {
  aws_cli?: { ok: boolean; version?: string | null };
  session_manager_plugin?: { ok: boolean; install_url?: string };
  socat?: { ok: boolean; version?: string | null };
}

export const preflightApi = {
  run: () => req<PreflightPayload>("GET", "/preflight"),
};

export interface VersionInfo {
  sidecar_version: string;
  server_version: string;
  build_date: string | null;
  update_available: boolean;
}

export const versionApi = {
  get: () => req<VersionInfo>("GET", "/version"),
};

export type BootStatus =
  | { status: "loading" }
  | { status: "ready"; sidecar_info: SidecarInfo; version: string }
  | { status: "version_error"; required: string; found: string };

export const bootApi = {
  get: () => invoke<BootStatus>("get_boot_status"),
};
