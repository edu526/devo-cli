import { describe, it, expect } from "vitest";
import { get } from "svelte/store";
import { sidecar, appStatus, appError, currentPage, wsConnected } from "../stores";
import type { SidecarInfo } from "../api";

describe("stores", () => {
  it("sidecar defaults to null", () => {
    expect(get(sidecar)).toBeNull();
  });

  it("appStatus defaults to loading", () => {
    expect(get(appStatus)).toBe("loading");
  });

  it("appError defaults to null", () => {
    expect(get(appError)).toBeNull();
  });

  it("currentPage defaults to connections", () => {
    expect(get(currentPage)).toBe("connections");
  });

  it("wsConnected defaults to false", () => {
    expect(get(wsConnected)).toBe(false);
  });

  it("sidecar updates when set", () => {
    const info: SidecarInfo = { port: 1, token: "t" };
    sidecar.set(info);
    expect(get(sidecar)).toEqual(info);
    sidecar.set(null);
    expect(get(sidecar)).toBeNull();
  });

  it("appStatus transitions loading → ready → error", () => {
    appStatus.set("ready");
    expect(get(appStatus)).toBe("ready");
    appStatus.set("error");
    expect(get(appStatus)).toBe("error");
    appStatus.set("loading");
    expect(get(appStatus)).toBe("loading");
  });

  it("currentPage accepts any of the defined page ids", () => {
    const pages = [
      "connections",
      "instances",
      "databases",
      "profiles",
      "hosts",
      "config",
      "logs",
    ] as const;
    for (const page of pages) {
      currentPage.set(page);
      expect(get(currentPage)).toBe(page);
    }
  });
});
