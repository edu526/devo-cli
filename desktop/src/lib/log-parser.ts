export type LogLevel = "ALL" | "DEBUG" | "INFO" | "WARN" | "ERROR";

export type LogEntry = {
  id: number;
  raw: string;
  ts?: string;
  level?: string;
  msg?: string;
};

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
  return { id, raw };
}

export function groupLogLines(rawLines: string[], startId = 1): { entries: LogEntry[]; nextId: number } {
  const entries: LogEntry[] = [];
  let nextId = startId;
  for (const raw of rawLines) {
    if (!raw) continue;
    const entry = parseLogLine(raw, nextId);
    if (entry.ts) {
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
