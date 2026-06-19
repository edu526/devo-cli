/**
 * Shared data cache for each page.
 * Lives outside components so navigation doesn't reset the data.
 * Each page reads from these on mount (instant render) and refreshes in background.
 */
import { writable } from "svelte/store";
import type {
  ConnectionRecord,
  DatabaseRecord,
  HostRecord,
  InstanceRecord,
  ProfileRecord,
} from "./api";

export const connectionsCache = writable<ConnectionRecord[] | null>(null);
export const instancesCache = writable<Record<string, InstanceRecord> | null>(null);
export const databasesCache = writable<Record<string, DatabaseRecord> | null>(null);
export const profilesCache = writable<ProfileRecord[] | null>(null);
export const hostsCache = writable<HostRecord[] | null>(null);
