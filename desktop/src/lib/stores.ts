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
export const currentPage = writable<Page>("connections");
export const wsConnected = writable<boolean>(false);
