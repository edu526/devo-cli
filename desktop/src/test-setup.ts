import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock Tauri invoke and Channel — tests don't run inside a Tauri webview.
vi.mock("@tauri-apps/api/core", () => {
  class FakeChannel {
    onmessage: ((msg: unknown) => void) | null = null;
    // Test helpers — production code never calls these
    emit(msg: unknown): void {
      this.onmessage?.(msg);
    }
  }
  return {
    invoke: vi.fn(),
    Channel: FakeChannel,
  };
});

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: vi.fn(() => ({
    startDragging: vi.fn(),
    minimize: vi.fn(),
    close: vi.fn(),
    toggleMaximize: vi.fn(),
    isMaximized: vi.fn().mockResolvedValue(false),
  })),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn().mockResolvedValue(() => {}),
}));

vi.mock("@tauri-apps/plugin-process", () => ({
  relaunch: vi.fn().mockResolvedValue(undefined),
}));
