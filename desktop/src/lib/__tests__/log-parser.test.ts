import { describe, it, expect } from "vitest";
import { parseLogLine, groupLogLines } from "../log-parser";

describe("log-parser", () => {
  describe("parseLogLine", () => {
    it("parses a correctly formatted log line", () => {
      const line = "2026-07-01 10:46:26 WARNING botocore.credentials: Refresh failed";
      const result = parseLogLine(line, 1);

      expect(result.id).toBe(1);
      expect(result.ts).toBe("2026-07-01 10:46:26");
      expect(result.level).toBe("WARNING");
      expect(result.msg).toBe("botocore.credentials: Refresh failed");
      expect(result.raw).toBe(line);
    });

    it("returns raw string if not matching format", () => {
      const line = "Traceback (most recent call last):";
      const result = parseLogLine(line, 2);

      expect(result.id).toBe(2);
      expect(result.ts).toBeUndefined();
      expect(result.level).toBeUndefined();
      expect(result.msg).toBeUndefined();
      expect(result.raw).toBe(line);
    });
  });

  describe("groupLogLines", () => {
    it("groups multiline logs to the previous entry", () => {
      const lines = [
        "2026-07-01 10:46:26 WARNING first issue",
        "Traceback (most recent call last):",
        "  File \"test.py\", line 1",
        "2026-07-01 10:46:27 INFO all good now"
      ];

      const { entries, nextId } = groupLogLines(lines, 1);

      expect(entries).toHaveLength(2);
      expect(nextId).toBe(3);

      expect(entries[0]!.id).toBe(1);
      expect(entries[0]!.level).toBe("WARNING");
      expect(entries[0]!.msg).toBe("first issue\nTraceback (most recent call last):\n  File \"test.py\", line 1");
      expect(entries[0]!.raw).toBe("2026-07-01 10:46:26 WARNING first issue\nTraceback (most recent call last):\n  File \"test.py\", line 1");

      expect(entries[1]!.id).toBe(2);
      expect(entries[1]!.level).toBe("INFO");
      expect(entries[1]!.msg).toBe("all good now");
    });

    it("handles lines without timestamp at the very beginning", () => {
      const lines = [
        "some random garbage",
        "2026-07-01 10:46:26 INFO started"
      ];

      const { entries, nextId } = groupLogLines(lines, 1);

      expect(entries).toHaveLength(2);
      expect(nextId).toBe(3);

      expect(entries[0]!.id).toBe(1);
      expect(entries[0]!.ts).toBeUndefined();
      expect(entries[0]!.raw).toBe("some random garbage");

      expect(entries[1]!.id).toBe(2);
      expect(entries[1]!.level).toBe("INFO");
    });
  });
});
