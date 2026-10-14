import { describe, it, expect, vi, beforeEach } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { ApiError, hostsApi, type ElevationHint } from "../api";
import { elevationHint, hostsCommand, withHostsElevation } from "../hosts-elevation";

const mockInvoke = vi.mocked(invoke);

function hint(params: Record<string, unknown>, action = "hosts-clear"): ElevationHint {
  return { message: "Elevated privileges required", command: "cmd", action, params };
}

describe("hostsCommand", () => {
  it("turns the sidecar's request into an action for the shell, never a command line", () => {
    expect(hostsCommand(hint({ cli_args: ["ssm", "hosts", "clear", "--yes"] }))).toEqual({ action: "clear" });
    expect(hostsCommand(hint({}, "hosts-sync"))).toEqual({ action: "sync" });
    expect(hostsCommand(hint({ db_names: ["a", "b"] }, "hosts-setup"))).toEqual({ action: "setup", db_names: ["a", "b"] });
    expect(hostsCommand(hint({}, "hosts-setup"))).toEqual({ action: "setup", db_names: [] });
    expect(hostsCommand(hint({ hostname: "db.rds" }, "hosts-remove"))).toEqual({ action: "remove", hostname: "db.rds" });
  });

  it("refuses anything else", () => {
    expect(() => hostsCommand(hint({ python_bin: "/bin/sh" }, "run-anything"))).toThrow("can't run");
    expect(() => hostsCommand(hint({}, "hosts-remove"))).toThrow("can't run"); // no hostname
  });
});

describe("elevationHint", () => {
  it("is null for a plain auth 401", () => {
    expect(elevationHint(new ApiError(401, "Invalid token"))).toBeNull();
  });

  it("is null for other errors", () => {
    expect(elevationHint(new ApiError(500, hint({})))).toBeNull();
    expect(elevationHint(new Error("boom"))).toBeNull();
  });

  it("reads the hint from the 403 detail", () => {
    const h = hint({ cli_args: ["ssm"] });
    expect(elevationHint(new ApiError(403, h))).toEqual(h);
    expect(elevationHint(new ApiError(403, JSON.stringify(h)))).toEqual(h);
  });

  it("is not a 401: that one means an expired sidecar token", () => {
    expect(elevationHint(new ApiError(401, hint({ cli_args: ["ssm"] })))).toBeNull();
  });
});

describe("withHostsElevation", () => {
  beforeEach(() => {
    mockInvoke.mockReset();
  });

  it("returns the result when no elevation is needed", async () => {
    await expect(withHostsElevation(async () => "done")).resolves.toBe("done");
    expect(mockInvoke).not.toHaveBeenCalled();
  });

  it("runs the elevated command, then repeats the request", async () => {
    mockInvoke.mockResolvedValue(0);
    const request = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(403, hint({ cli_args: ["ssm", "hosts", "clear", "--yes"] })))
      .mockResolvedValueOnce("recorded");

    await expect(withHostsElevation(request)).resolves.toBe("recorded");

    expect(mockInvoke).toHaveBeenCalledWith("run_hosts_command", { command: { action: "clear" } });
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("reports a failed elevated command (Windows returns its exit code) without repeating", async () => {
    mockInvoke.mockResolvedValue(1);
    const request = vi.fn().mockRejectedValue(new ApiError(403, hint({ cli_args: ["ssm"] })));

    await expect(withHostsElevation(request)).rejects.toThrow("exit code 1");
    expect(request).toHaveBeenCalledTimes(1);
  });

  describe("a hosts file locked even for administrators (exit code 3)", () => {
    const locked = () =>
      vi.fn().mockRejectedValue(new ApiError(403, hint({ cli_args: ["ssm", "hosts", "clear"] })));

    it("shows why, as the sidecar explains it (Windows reports the code)", async () => {
      mockInvoke.mockResolvedValue(3);
      const lockReason = vi
        .spyOn(hostsApi, "lockReason")
        .mockResolvedValue({ message: "Kaspersky is blocking changes to your hosts file" });

      await expect(withHostsElevation(locked())).rejects.toThrow("Kaspersky is blocking changes");
      lockReason.mockRestore();
    });

    it("also from the macOS/Linux failure message", async () => {
      mockInvoke.mockRejectedValue("elevation command failed with status: exit status: 3");
      const lockReason = vi.spyOn(hostsApi, "lockReason").mockResolvedValue({ message: "Kaspersky is blocking it" });

      await expect(withHostsElevation(locked())).rejects.toThrow("Kaspersky is blocking it");
      lockReason.mockRestore();
    });

    it("falls back to a generic reason if the sidecar can't say", async () => {
      mockInvoke.mockResolvedValue(3);
      const lockReason = vi.spyOn(hostsApi, "lockReason").mockRejectedValue(new Error("down"));

      await expect(withHostsElevation(locked())).rejects.toThrow("usually an antivirus");
      lockReason.mockRestore();
    });
  });

  it("says so in plain words when the hosts file still needs elevation afterwards", async () => {
    mockInvoke.mockResolvedValue(0);
    const request = vi.fn().mockRejectedValue(new ApiError(403, hint({ cli_args: ["ssm"] })));

    const error = await withHostsElevation(request).catch((e: Error) => e);

    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toContain("didn't change");
    expect((error as Error).message).not.toContain("{"); // not the raw 403 detail
  });

  it("does not repeat the request when the admin prompt is cancelled", async () => {
    mockInvoke.mockRejectedValue(new Error("UAC prompt was cancelled or access denied"));
    const request = vi.fn().mockRejectedValue(new ApiError(403, hint({ cli_args: ["ssm"] })));

    await expect(withHostsElevation(request)).rejects.toThrow("cancelled");
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("rethrows errors that are not elevation requests", async () => {
    await expect(withHostsElevation(() => Promise.reject(new ApiError(404, "nope")))).rejects.toThrow("nope");
    expect(mockInvoke).not.toHaveBeenCalled();
  });
});
