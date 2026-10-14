import { describe, it, expect } from "vitest";
import type { CodeArtifactDomain, CodeArtifactToken } from "../api";
import { defaultTool } from "../codeartifact";

const domain = (overrides: Partial<CodeArtifactDomain> = {}): CodeArtifactDomain => ({
  domain: "acme",
  repository: "packages",
  namespace: "",
  account_id: "111122223333",
  profile: "tooling",
  region: "us-east-1",
  ...overrides,
});

const token = (tool: string, expires_at: string | null, forDomain = "acme"): CodeArtifactToken => ({
  domain: forDomain,
  repository: "packages",
  account_id: "111122223333",
  region: "us-east-1",
  tool,
  registry_url: "https://example",
  expires_at,
});

describe("defaultTool", () => {
  it("starts on the tool the user already logged in with", () => {
    expect(defaultTool(domain({ namespace: "@acme" }), [token("pip", "2026-10-14T20:00:00Z")])).toBe("pip");
  });

  it("prefers the most recent login when there are several", () => {
    const tokens = [token("npm", "2026-10-14T10:00:00Z"), token("twine", "2026-10-14T20:00:00Z")];
    expect(defaultTool(domain(), tokens)).toBe("twine");
  });

  it("ignores other domains' logins", () => {
    expect(defaultTool(domain(), [token("pip", "2026-10-14T20:00:00Z", "other")])).toBe("npm");
  });

  it("uses npm for an npm scope", () => {
    expect(defaultTool(domain({ namespace: "@acme", repository: "pypi-mirror" }), [])).toBe("npm");
  });

  it("uses pip for a Python-looking repository", () => {
    expect(defaultTool(domain({ repository: "pypi" }), [])).toBe("pip");
    expect(defaultTool(domain({ repository: "python-internal" }), [])).toBe("pip");
  });

  it("falls back to npm", () => {
    expect(defaultTool(domain({ repository: "packages" }), [])).toBe("npm");
    expect(defaultTool(domain({ repository: "happy-npm" }), [])).toBe("npm");
  });
});
