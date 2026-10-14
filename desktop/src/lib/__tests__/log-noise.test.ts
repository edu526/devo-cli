import { describe, it, expect } from "vitest";
import { displayMessage, groupLogLines, httpStatus, isRoutineHttp, parseLogLine } from "../log-parser";

const line = (msg: string, level = "INFO") => parseLogLine(`2026-10-14 09:08:01 ${level}     ${msg}`, 1);
const access = (status: string) =>
  line(`[console] INFO:     127.0.0.1:52293 - "GET /api/v1/connections HTTP/1.1" ${status}`);

describe("HTTP request lines", () => {
  it("are recognized with their status", () => {
    expect(httpStatus(access("200 OK"))).toBe(200);
    expect(httpStatus(line("cli_tool.sidecar.app: started"))).toBeNull();
  });

  it("are routine only while they succeed", () => {
    expect(isRoutineHttp(access("200 OK"))).toBe(true);
    expect(isRoutineHttp(access("304 Not Modified"))).toBe(true);
    expect(isRoutineHttp(access("429 Too Many Requests"))).toBe(false);
    expect(isRoutineHttp(access("500 Internal Server Error"))).toBe(false);
    expect(isRoutineHttp(line("auto-renew: renewed 3 profile(s)"))).toBe(false);
  });
});

describe("displayMessage", () => {
  it("keeps only the last part of the logger name", () => {
    expect(displayMessage("cli_tool.commands.ssm.core.connection_runner: [orders-dev] Tunnel connected")).toBe(
      "connection_runner: [orders-dev] Tunnel connected",
    );
  });

  it("shows a request as method, path and status", () => {
    expect(displayMessage(access("200 OK").msg!)).toBe("GET /api/v1/connections → 200 OK");
  });

  it("leaves other messages alone", () => {
    expect(displayMessage("Something: with a colon")).toBe("Something: with a colon");
    expect(displayMessage("plain text")).toBe("plain text");
  });
});

describe("lines copied from stderr without a timestamp", () => {
  const lines = [
    "2026-10-14 09:08:01 INFO     cli_tool.sidecar.app: started",
    "DEBUG:    > TEXT '{\"event\": \"connection.metrics\"}' [142 bytes]",
    'INFO:     127.0.0.1:52293 - "GET /api/v1/connections HTTP/1.1" 200 OK',
    "Traceback (most recent call last):",
  ];

  it("are entries of their own, with their level, not part of the entry before", () => {
    const { entries } = groupLogLines(lines);
    expect(entries.map((e) => e.level)).toEqual(["INFO", "DEBUG", "INFO"]);
    expect(entries[0]!.raw).toBe(lines[0]);
    // a traceback still belongs to the line before it
    expect(entries[2]!.raw).toBe(`${lines[2]}
${lines[3]}`);
  });

  it("include requests, recognized as such", () => {
    const { entries } = groupLogLines(lines);
    expect(isRoutineHttp(entries[2]!)).toBe(true);
  });
});
