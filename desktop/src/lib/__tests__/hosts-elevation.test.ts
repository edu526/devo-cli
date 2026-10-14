import { describe, it, expect, vi, beforeEach } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { ApiError, hostsApi, type ElevationHint } from "../api";
import { elevatedArgs, elevationHint, withHostsElevation } from "../hosts-elevation";

const mockInvoke = vi.mocked(invoke);

function hint(params: Record<string, unknown>): ElevationHint {
  return { message: "Elevated privileges required", command: "cmd", action: "hosts-clear", params };
}

const unix = { python_bin: "/opt/devo/devo-sidecar", config_dir: "/home/u/.devo", use_env: true };

describe("elevatedArgs", () => {
  it("runs the command the sidecar names, with the config dir on Linux/macOS", () => {
    expect(elevatedArgs(hint({ ...unix, cli_args: ["ssm", "hosts", "clear", "--yes"] }))).toEqual([
      "/usr/bin/env",
      "DEVO_CONFIG_DIR=/home/u/.devo",
      "/opt/devo/devo-sidecar",
      "-m",
      "cli_tool.cli",
      "ssm",
      "hosts",
      "clear",
      "--yes",
    ]);
  });

  it("has no env prefix on Windows", () => {
    const args = elevatedArgs(
      hint({ python_bin: "C:\\Devo\\devo-sidecar.exe", config_dir: "C:\\u\\.devo", use_env: false, cli_args: ["ssm"] }),
    );
    expect(args).toEqual(["C:\\Devo\\devo-sidecar.exe", "-m", "cli_tool.cli", "ssm"]);
  });

  it("falls back to `hosts setup <db_names>` for sidecars that don't send cli_args", () => {
    expect(elevatedArgs(hint({ ...unix, use_env: false, db_names: ["a", "b"] })).slice(3)).toEqual([
      "ssm",
      "hosts",
      "setup",
      "a",
      "b",
    ]);
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
      .mockRejectedValueOnce(new ApiError(403, hint({ ...unix, cli_args: ["ssm", "hosts", "clear", "--yes"] })))
      .mockResolvedValueOnce("recorded");

    await expect(withHostsElevation(request)).resolves.toBe("recorded");

    expect(mockInvoke).toHaveBeenCalledWith("run_elevated", {
      args: expect.arrayContaining(["clear", "--yes"]),
    });
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("reports a failed elevated command (Windows returns its exit code) without repeating", async () => {
    mockInvoke.mockResolvedValue(1);
    const request = vi.fn().mockRejectedValue(new ApiError(403, hint({ ...unix, cli_args: ["ssm"] })));

    await expect(withHostsElevation(request)).rejects.toThrow("exit code 1");
    expect(request).toHaveBeenCalledTimes(1);
  });

  describe("a hosts file locked even for administrators (exit code 3)", () => {
    const locked = () =>
      vi.fn().mockRejectedValue(new ApiError(403, hint({ ...unix, cli_args: ["ssm", "hosts", "clear"] })));

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
    const request = vi.fn().mockRejectedValue(new ApiError(403, hint({ ...unix, cli_args: ["ssm"] })));

    const error = await withHostsElevation(request).catch((e: Error) => e);

    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toContain("didn't change");
    expect((error as Error).message).not.toContain("{"); // not the raw 403 detail
  });

  it("does not repeat the request when the admin prompt is cancelled", async () => {
    mockInvoke.mockRejectedValue(new Error("UAC prompt was cancelled or access denied"));
    const request = vi.fn().mockRejectedValue(new ApiError(403, hint({ ...unix, cli_args: ["ssm"] })));

    await expect(withHostsElevation(request)).rejects.toThrow("cancelled");
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("rethrows errors that are not elevation requests", async () => {
    await expect(withHostsElevation(() => Promise.reject(new ApiError(404, "nope")))).rejects.toThrow("nope");
    expect(mockInvoke).not.toHaveBeenCalled();
  });
});
