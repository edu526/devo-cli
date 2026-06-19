import { describe, it, expect, beforeEach } from "vitest";
import { get } from "svelte/store";
import { updateAvailable, setUpdateAvailable, fetchUpdate } from "../update";

describe("updateAvailable store", () => {
  beforeEach(() => {
    setUpdateAvailable(null);
  });

  it("starts at null", () => {
    expect(get(updateAvailable)).toBeNull();
  });

  it("setUpdateAvailable updates the store", () => {
    setUpdateAvailable({ version: "1.0.0", currentVersion: "0.9.0" });
    expect(get(updateAvailable)).toEqual({ version: "1.0.0", currentVersion: "0.9.0" });
  });
});

describe("fetchUpdate", () => {
  it("falls back gracefully when the command is not available", async () => {
    // The Tauri runtime in the test setup returns undefined for any
    // command, so invoke resolves to undefined. We verify that the
    // wrapper does not throw and clears the store.
    const result = await fetchUpdate();
    expect(result).toBeFalsy();
    expect(get(updateAvailable)).toBeFalsy();
  });
});
