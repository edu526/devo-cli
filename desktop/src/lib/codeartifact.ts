import type { CodeArtifactDomain, CodeArtifactToken } from "./api";

export const CODEARTIFACT_TOOLS = ["npm", "pip", "twine"] as const;
export type CodeArtifactTool = (typeof CODEARTIFACT_TOOLS)[number];

/**
 * The tool a domain's card starts on. A CodeArtifact repository can serve
 * several formats and its name is only a name, so this goes by what is
 * known: the tool the user already logged in with (otherwise a domain set up
 * for pip showed "Not connected" every time Devo opened), then an npm scope
 * as namespace, then a Python-looking repository name, then npm.
 */
export function defaultTool(domain: CodeArtifactDomain, tokens: CodeArtifactToken[]): CodeArtifactTool {
  const [latest] = tokens
    .filter((t) => t.domain === domain.domain && isTool(t.tool))
    .sort((a, b) => (b.expires_at ?? "").localeCompare(a.expires_at ?? ""));
  if (latest) return latest.tool as CodeArtifactTool;
  if (domain.namespace?.startsWith("@")) return "npm";
  if (/(^|[^a-z])(pypi|python|pip|py)([^a-z]|$)/i.test(domain.repository)) return "pip";
  return "npm";
}

function isTool(tool: string): tool is CodeArtifactTool {
  return (CODEARTIFACT_TOOLS as readonly string[]).includes(tool);
}
