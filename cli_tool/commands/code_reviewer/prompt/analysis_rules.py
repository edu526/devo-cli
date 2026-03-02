"""
Optimized analysis rules - consolidated and removed duplications.
"""

CORE_ANALYSIS_RULES = """
**CRITICAL**: Analyze EXCLUSIVELY the lines that changed in the diff (+ additions and - deletions). Do NOT comment on unchanged code.

Your responsibilities:
1. Analyze ONLY the diff changes carefully
2. Use file context as reference, but do NOT report issues in unchanged code
3. When detecting breaking changes, use tools to search dependencies and analyze impact
4. Adapt analysis to the specific programming language and file type
"""

PRIORITY_CHECKS = """
**Analysis Priority:**
- **CRITICAL**: Security vulnerabilities, breaking changes, data corruption risks
- **HIGH**: Performance bottlenecks, memory leaks, broken references, auth flaws
- **MEDIUM**: Code quality, missing error handling, configuration issues
- **LOW**: Style, documentation, minor optimizations
"""

ANALYSIS_CHECKS = """
**Required Checks (ON CHANGED LINES ONLY):**
- **Dependencies**: Missing, unused, or invalid imports/packages
- **References**: Deleted/renamed functions, variables, classes still referenced elsewhere
- **Quality**: Unused variables, redundant logic, missing error handling, async/await issues
- **Security**: Apply security standards to identify vulnerabilities
- **Performance**: Unnecessary loops, duplicate queries, expensive operations
- **Configuration**: Syntax errors, deprecated settings, security issues
- **Naming**: Non-descriptive names (flag MEDIUM: single chars except i,j,k in loops; generic names like 'data','temp','val'; unclear abbreviations)
- **Breaking Changes**: Function/method/class renames, signature changes, parameter modifications
"""

BREAKING_CHANGES_ANALYSIS = """
**Breaking Changes Detection:**

**CRITICAL (Always Breaking):**
- Parameters removed/reordered, required parameters added without defaults
- Function/method/class renames or deletions, incompatible return types
- API endpoint changes, required request parameter changes

**NON-CRITICAL (Backward Compatible):**
- Optional parameters with defaults added at end
- New overloaded methods, new optional properties with defaults
- New API endpoints or response fields

**Analysis Process:**
1. Use search tools to find all references
2. Estimate impact scope and suggest migration strategy
3. Distinguish between critical and non-critical changes
"""

FALSE_POSITIVE_PREVENTION = """
**Do NOT Report:**
- Unused variables in test files, style issues in generated/vendor code
- Single-char variables in math contexts (x,y,z), standard loops (i,j,k), events (e), lambdas
- Optional parameters with defaults, new overloaded methods, additive API changes
- Framework-specific patterns (React unused props, Django ORM, Spring DI)

**Verify Context:**
- Check if "unused" variables are used in templates/configs
- Confirm breaking changes aren't intentional with migration
- Validate security issues aren't framework-protected false positives
"""
