import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { ws } from "../ws";
import { initApi } from "../api";

const mockInvoke = vi.mocked(invoke);

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];
  url: string;
  protocols: string | string[];

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols ?? [];
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  // Test helpers
  triggerOpen(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  triggerMessage(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  triggerClose(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  triggerError(): void {
    this.onerror?.();
  }
}

describe("ws", () => {
  let OriginalWebSocket: typeof WebSocket;

  beforeEach(async () => {
    FakeWebSocket.instances = [];
    OriginalWebSocket = globalThis.WebSocket;
    globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;

    mockInvoke.mockReset();
    mockInvoke.mockResolvedValueOnce({ port: 54321, token: "the-token" });
    await initApi();

    ws.disconnect();
    vi.useFakeTimers();
  });

  afterEach(() => {
    ws.disconnect();
    globalThis.WebSocket = OriginalWebSocket;
    vi.useRealTimers();
  });

  it("connects to localhost on the given port with bearer subprotocol", () => {
    ws.connect(54321);
    const socket = FakeWebSocket.instances[0]!;
    expect(socket.url).toBe("ws://127.0.0.1:54321/api/v1/events");
    expect(socket.protocols).toEqual(["bearer", "the-token"]);
  });

  it("emits $connected on open and $disconnected on close", () => {
    const onConnected = vi.fn();
    const onDisconnected = vi.fn();
    ws.on("$connected", onConnected);
    ws.on("$disconnected", onDisconnected);

    ws.connect(54321);
    const socket = FakeWebSocket.instances[0]!;
    socket.triggerOpen();
    expect(onConnected).toHaveBeenCalled();

    socket.triggerClose();
    expect(onDisconnected).toHaveBeenCalled();
  });

  it("dispatches named events from incoming messages and ignores ping", () => {
    const onAny = vi.fn();
    const onProfile = vi.fn();
    ws.on("*", onAny);
    ws.on("profile.refreshed", onProfile);

    ws.connect(54321);
    const socket = FakeWebSocket.instances[0]!;
    socket.triggerOpen();

    socket.triggerMessage({ event: "profile.refreshed", names: ["dev"] });
    expect(onProfile).toHaveBeenCalledTimes(1);
    expect(onAny).toHaveBeenCalledTimes(1);

    socket.triggerMessage({ event: "ping" });
    expect(onProfile).toHaveBeenCalledTimes(1); // unchanged
    expect(onAny).toHaveBeenCalledTimes(1); // unchanged
  });

  it("ignores malformed JSON payloads", () => {
    const onAny = vi.fn();
    ws.on("*", onAny);

    ws.connect(54321);
    const socket = FakeWebSocket.instances[0]!;
    socket.triggerOpen();
    socket.onmessage?.({ data: "not json {" });

    expect(onAny).not.toHaveBeenCalled();
  });

  it("auto-reconnects after 3 seconds when the socket closes", () => {
    ws.connect(54321);
    const first = FakeWebSocket.instances[0]!;
    first.triggerOpen();
    first.triggerClose();

    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(3000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("does not reconnect after disconnect()", () => {
    ws.connect(54321);
    const first = FakeWebSocket.instances[0]!;
    first.triggerOpen();

    ws.disconnect();
    first.triggerClose();

    vi.advanceTimersByTime(10_000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("returns an unsubscribe function from on()", () => {
    const handler = vi.fn();
    const off = ws.on("test.event", handler);
    ws.connect(54321);
    const socket = FakeWebSocket.instances[0]!;
    socket.triggerOpen();

    socket.triggerMessage({ event: "test.event" });
    expect(handler).toHaveBeenCalledTimes(1);

    off();
    socket.triggerMessage({ event: "test.event" });
    expect(handler).toHaveBeenCalledTimes(1);
  });
});
