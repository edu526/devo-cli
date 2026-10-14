import { invoke } from "@tauri-apps/api/core";
import { ApiError, hostsApi, type ElevationHint } from "./api";

/**
 * Hosts-file changes the sidecar can't make without admin rights come back as
 * a 403 whose detail names the `devo` command to run elevated. That command
 * runs through Tauri's `run_elevated` (UAC / osascript / pkexec), and the
 * request is then repeated: it finds the hosts file already done and records
 * the change.
 */
export async function withHostsElevation<T>(request: () => Promise<T>): Promise<T> {
  try {
    return await request();
  } catch (e) {
    const hint = elevationHint(e);
    if (!hint) throw e;
    // Windows reports the command's exit code; macOS/Linux reject on failure.
    let code: number;
    try {
      code = await invoke<number>("run_elevated", { args: elevatedArgs(hint) });
    } catch (elevationError) {
      if (exitCodeIn(elevationError) === HOSTS_LOCKED_EXIT_CODE) throw await hostsLockedError();
      throw elevationError;
    }
    if (code === HOSTS_LOCKED_EXIT_CODE) throw await hostsLockedError();
    if (code !== 0) {
      throw new Error(
        `Couldn't change the hosts file as administrator (exit code ${code}). The reason is in Logs.`,
      );
    }
    try {
      return await request();
    } catch (retryError) {
      if (!elevationHint(retryError)) throw retryError;
      throw new Error(
        "The administrator command ran, but the hosts file didn't change. Something may be " +
          "blocking changes to it (e.g. antivirus hosts-file protection). The reason is in Logs.",
      );
    }
  }
}

/**
 * Exit code of `devo ssm hosts …` when the hosts file was denied even as
 * administrator (HostsFileLocked: an antivirus protecting it, the read-only
 * flag…). Admin rights don't help, so the user needs to know what does.
 */
const HOSTS_LOCKED_EXIT_CODE = 3;

async function hostsLockedError(): Promise<Error> {
  try {
    return new Error((await hostsApi.lockReason()).message);
  } catch {
    return new Error(
      "Something is blocking changes to your hosts file, even with administrator rights, " +
        "usually an antivirus. Pause it for a moment and try again.",
    );
  }
}

/** The exit code in run_elevated's macOS/Linux failure ("…failed with status: exit status: 3"). */
function exitCodeIn(error: unknown): number | null {
  const match = /exit (?:status|code):? ?(\d+)/i.exec(String(error));
  return match ? Number(match[1]) : null;
}

export function elevationHint(e: unknown): ElevationHint | null {
  if (!(e instanceof ApiError) || e.status !== 403) return null;
  let detail = e.detail;
  if (typeof detail === "string") {
    try {
      detail = JSON.parse(detail);
    } catch {
      return null; // a plain 403, not an elevation request
    }
  }
  const hint = detail as Partial<ElevationHint> | null;
  return hint && typeof hint === "object" && hint.params ? (hint as ElevationHint) : null;
}

/** argv for `run_elevated`: `[env DEVO_CONFIG_DIR=…] <python_bin> -m cli_tool.cli <cli_args>`. */
export function elevatedArgs(hint: ElevationHint): string[] {
  const p = hint.params as {
    cli_args?: string[];
    db_names?: string[];
    python_bin?: string;
    config_dir?: string;
    use_env?: boolean;
  };
  // Sidecars before cli_args only ever asked for `hosts setup`.
  const cliArgs = p.cli_args ?? ["ssm", "hosts", "setup", ...(p.db_names ?? [])];
  const args: string[] = [];
  if (p.config_dir && p.use_env) args.push("/usr/bin/env", `DEVO_CONFIG_DIR=${p.config_dir}`);
  args.push(p.python_bin || "python", "-m", "cli_tool.cli", ...cliArgs);
  return args;
}
