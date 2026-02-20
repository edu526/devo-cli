"""
Optimized output format - consolidated rules and removed redundancy.
"""

OUTPUT_RULES = """
**Output Requirements:**
- Always respond in valid JSON with summary and detailed issues
- Line numbers refer to NEW file (after changes), not diff lines
- Only report issues in actual changes (+ and - lines in diff)
- NO test suggestions or testing-related output
- For security issues: specify violated standard (e.g., "OWASP A03: Injection", "CWE-89")
- For multiple file references: use "Files that need updates:" with bulleted list
"""

OUTPUT_FORMAT = """
{
  "summary": "Overall assessment focusing on modified code and security impact",
  "issues": [
    {
      "type": "Dependency | Reference | Quality | Security | BestPractice | Performance | Configuration | Documentation | BreakingChange",
      "severity": "critical | high | medium | low",
      "file": "path/to/file",
      "line": 123,
      "description": "Clear problem explanation with security standards when applicable",
      "suggestion": "Fix proposal with structured file references when needed",
      "impact": "For breaking changes: affected areas. For security: attack vectors and business impact",
      "security_reference": "When applicable: violated standard (e.g., 'OWASP A03', 'CWE-89')"
    }
  ]
}
"""

SEVERITY_GUIDELINES = """
**Severity Levels:**
- **Critical**: Security exploits, compilation breaks, data corruption, RCE, auth bypass
- **High**: Performance issues, memory leaks, auth flaws, XSS/CSRF, major breaking changes
- **Medium**: Quality issues, missing validation, config security, moderate performance
- **Low**: Style/formatting, minor optimizations, documentation, weak policies
"""
