"""
Optimized security standards for code review - removed duplications and verbose examples.
"""

SECURITY_STANDARDS = """
**SECURITY ANALYSIS STANDARDS:**
Apply these frameworks when analyzing code changes:

**Key Standards:**
- **OWASP Top 10**: Injection, broken auth, data exposure, XXE, access control, misconfiguration, XSS, deserialization, vulnerable components, insufficient logging
- **CWE Top 25**: Focus on injection (CWE-79, 89, 78, 94), memory corruption (CWE-787, 125, 119), access control (CWE-22, 352, 434)
- **Language-specific**: Java deserialization, Python pickle/eval, JS prototype pollution, C/C++ buffer overflows

**Cryptographic Requirements:**
- Approved algorithms: AES-256, RSA-2048+, SHA-256+, ECDSA P-256+
- Proper key management, secure random generation, salt usage (bcrypt, scrypt, Argon2)

**Severity Classification:**
- **Critical**: RCE, SQL injection, auth bypass, data exposure
- **High**: XSS, CSRF, privilege escalation, crypto failures
- **Medium**: Info disclosure, missing validation, weak sessions
- **Low**: Missing headers, verbose errors, weak policies
"""

SECURITY_CHECKS = """
**Security Checks (ON CHANGED LINES ONLY):**
- **Injection**: SQL, NoSQL, LDAP, XPath, OS command, code injection
- **XSS**: Reflected, stored, DOM-based in user input handling
- **Auth/Access**: Weak passwords, missing MFA, insecure sessions, missing access controls
- **Crypto**: Weak algorithms, hard-coded keys, improper storage
- **Config**: Default credentials, unnecessary services, missing headers
- **Data**: Sensitive data in logs, unencrypted storage, information leakage
- **Other**: CSRF/SSRF, unsafe deserialization, race conditions, business logic flaws
"""
