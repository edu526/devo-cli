export type LogLevel = "ALL" | "DEBUG" | "INFO" | "WARN" | "ERROR";

export type LogEntry = {
  id: number;
  raw: string;
  ts?: string;
  level?: string;
  msg?: string;
};

// Lines the web server writes to the sidecar's stderr, copied into the log
// without a timestamp: `DEBUG:    > TEXT '{"event": ...}'`. With Backend Debug
// Mode on they are most of the file. Each is a line of its own, not part of
// the entry before it.
const STDERR_LINE = /^(DEBUG|INFO|WARNING|ERROR|CRITICAL):\s+(.*)$/;

export function parseLogLine(raw: string, id: number): LogEntry {
  const match = raw.match(/^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+([A-Z]+)\s+(.*)$/);
  if (match) {
    return {
      id,
      raw,
      ts: match[1],
      level: match[2],
      msg: match[3],
    };
  }
  const stderr = raw.match(STDERR_LINE);
  if (stderr) return { id, raw, level: stderr[1], msg: stderr[2] };
  return { id, raw };
}

export function groupLogLines(rawLines: string[], startId = 1): { entries: LogEntry[]; nextId: number } {
  const entries: LogEntry[] = [];
  let nextId = startId;
  for (const raw of rawLines) {
    if (!raw) continue;
    const entry = parseLogLine(raw, nextId);
    if (entry.ts || entry.level) {
      entries.push(entry);
      nextId++;
    } else {
      if (entries.length > 0) {
        const last = entries[entries.length - 1]!;
        last.raw += "\n" + raw;
        if (last.msg !== undefined) {
          last.msg += "\n" + raw;
        }
      } else {
        entries.push(entry);
        nextId++;
      }
    }
  }
  return { entries, nextId };
}

// `[console] INFO:     127.0.0.1:52293 - "GET /api/v1/connections HTTP/1.1" 200 OK`,
// or the same without the `[console] INFO:` part when it came from stderr.
const HTTP_ACCESS = /^(?:\[console\]\s+\w+:\s+)?\S+\s+-\s+"([A-Z]+ \S+) HTTP\/[\d.]+"\s+(\d{3})(.*)$/;

/**
 * The status of a request from the Devo window to its background service,
 * or null if the line isn't one. They are most of the log and rarely
 * interesting, unless they failed.
 */
export function httpStatus(entry: LogEntry): number | null {
  const match = firstLine(entry.msg ?? "").match(HTTP_ACCESS);
  return match ? Number(match[2]) : null;
}

function firstLine(text: string): string {
  const end = text.indexOf("\n");
  return end === -1 ? text : text.slice(0, end);
}

/** A request that went fine: hidden unless the user asks for them. */
export function isRoutineHttp(entry: LogEntry): boolean {
  const status = httpStatus(entry);
  return status !== null && status < 400;
}

// `cli_tool.commands.ssm.core.connection_runner: message` -> `connection_runner: message`
const LOGGER_PREFIX = /^(?:[A-Za-z_]\w*\.)+([A-Za-z_]\w*):\s/;

/** The message without the noise: short logger name, compact HTTP lines. */
export function displayMessage(msg: string): string {
  const http = firstLine(msg).match(HTTP_ACCESS);
  if (http) return `${http[1]} → ${http[2]}${http[3] ?? ""}`;
  return msg.replace(LOGGER_PREFIX, "$1: ");
}
