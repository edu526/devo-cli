import { describe, it, expect, beforeEach } from "vitest";
import { get } from "svelte/store";
import { errorLog, logError, clearErrorLog, getErrorLogSnapshot } from "../error-log";

describe("error-log", () => {
  beforeEach(() => {
    clearErrorLog();
  });

  it("appends entries with incrementing ids and timestamps", () => {
    logError("api", "GET /config failed");
    logError("ws", "WebSocket error");

    const entries = get(errorLog);
    expect(entries).toHaveLength(2);
    expect(entries[0]!.source).toBe("api");
    expect(entries[0]!.message).toBe("GET /config failed");
    expect(entries[0]!.id).toBeLessThan(entries[1]!.id);
    expect(typeof entries[0]!.ts).toBe("number");
  });

  it("captures optional detail", () => {
    logError("window", "boom", "stack trace here");
    expect(get(errorLog)[0]!.detail).toBe("stack trace here");
  });

  it("caps the buffer at 200 entries by dropping oldest", () => {
    for (let i = 0; i < 210; i++) logError("api", `err ${i}`);
    const entries = get(errorLog);
    expect(entries).toHaveLength(200);
    expect(entries[0]!.message).toBe("err 10");
    expect(entries.at(-1)!.message).toBe("err 209");
  });

  it("clearErrorLog empties the buffer", () => {
    logError("api", "x");
    clearErrorLog();
    expect(get(errorLog)).toEqual([]);
  });

  it("getErrorLogSnapshot returns a plain array copy", () => {
    logError("tauri", "invoke failed");
    const snap = getErrorLogSnapshot();
    expect(snap).toHaveLength(1);
    expect(snap[0]!.source).toBe("tauri");
    // mutating the snapshot must not affect the store
    snap.pop();
    expect(get(errorLog)).toHaveLength(1);
  });
});
