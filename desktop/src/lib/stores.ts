import { writable } from "svelte/store";
import type { SidecarInfo } from "./api";

export type Page =
  | "connections"
  | "instances"
  | "databases"
  | "profiles"
  | "hosts"
  | "registry"
  | "config"
  | "logs";
export type AppStatus = "loading" | "ready" | "error";

export const sidecar = writable<SidecarInfo | null>(null);
export const appStatus = writable<AppStatus>("loading");
export const appError = writable<string | null>(null);
export const currentPage = writable<Page>("databases");
export const wsConnected = writable<boolean>(false);
function createViewModeStore(pageId: string) {
  const key = `devo_view_mode_${pageId}`;
  const store = writable<"table" | "card">(
    (localStorage.getItem(key) as "table" | "card") || "card",
  );
  store.subscribe((value) => {
    localStorage.setItem(key, value);
  });
  return store;
}

export const viewModes = {
  connections: createViewModeStore("connections"),
  databases: createViewModeStore("databases"),
  hosts: createViewModeStore("hosts"),
  profiles: createViewModeStore("profiles"),
  registry: createViewModeStore("registry"),
};
