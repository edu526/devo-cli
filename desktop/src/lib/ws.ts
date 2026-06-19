import { getToken } from "./api";
import { logError } from "./error-log";

export interface WsMessage {
  event: string;
  [key: string]: unknown;
}

type Handler = (msg: WsMessage) => void;

class SidecarWs {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<Handler>>();
  private port = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private destroyed = false;

  connect(port: number): void {
    this.port = port;
    this.destroyed = false;
    this._open();
  }

  private _open(): void {
    if (this.destroyed) return;
    const token = getToken();
    const url = `ws://127.0.0.1:${this.port}/api/v1/events`;
    const ws = new WebSocket(url, ["bearer", token]);

    ws.onopen = () => {
      this._emit("$connected", { event: "$connected" });
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string) as WsMessage;
        if (msg.event === "ping") return;
        this._emit(msg.event, msg);
        this._emit("*", msg);
      } catch {
        // ignore malformed payloads
      }
    };

    ws.onclose = () => {
      this._emit("$disconnected", { event: "$disconnected" });
      if (!this.destroyed) {
        logError("ws", `WebSocket disconnected from ${url} — retrying in 3s`);
        this.reconnectTimer = setTimeout(() => this._open(), 3000);
      }
    };

    ws.onerror = () => {
      logError("ws", `WebSocket error on ${url}`);
      ws.close();
    };

    this.ws = ws;
  }

  private _emit(event: string, msg: WsMessage): void {
    this.handlers.get(event)?.forEach((h) => {
      try {
        h(msg);
      } catch {
        // swallow handler errors so one bad subscriber doesn't break others
      }
    });
  }

  on(event: string, handler: Handler): () => void {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler);
    return () => this.handlers.get(event)?.delete(handler);
  }

  disconnect(): void {
    this.destroyed = true;
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const ws = new SidecarWs();
