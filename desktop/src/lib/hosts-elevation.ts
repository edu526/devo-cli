import { invoke } from "@tauri-apps/api/core";
import { ApiError, hostsApi, type ElevationHint } from "./api";

/**
 * Hosts-file changes the sidecar can't make without admin rights come back as
 * a 403 naming the action to run elevated. The Tauri shell runs it
 * (`run_hosts_command`: UAC / osascript / pkexec), and the request is then
 * repeated: it finds the hosts file already done and records the change.
 *
 * Only the action and its values go to the shell, which builds the command
 * line itself: this page can't make it run anything else as administrator.
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
      code = await invoke<number>("run_hosts_command", { command: hostsCommand(hint) });
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

/** What `run_hosts_command` runs: an action and its values (hosts_command.rs). */
export type HostsCommand =
  | { action: "setup"; db_names: string[] }
  | { action: "sync" }
  | { action: "clear" }
  | { action: "remove"; hostname: string };

export function hostsCommand(hint: ElevationHint): HostsCommand {
  const params = hint.params as { db_names?: string[]; hostname?: string };
  switch (hint.action) {
    case "hosts-setup":
      return { action: "setup", db_names: params.db_names ?? [] };
    case "hosts-sync":
      return { action: "sync" };
    case "hosts-clear":
      return { action: "clear" };
    case "hosts-remove":
      if (params.hostname) return { action: "remove", hostname: params.hostname };
      break;
  }
  throw new Error(`Devo can't run "${hint.action}" as administrator`);
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

/** The exit code in the macOS/Linux failure ("…failed with status: exit status: 3"). */
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
