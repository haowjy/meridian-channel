# Security Review

Think like an attacker. What can be abused?

## Trust Boundaries

Every place where data crosses a trust boundary is a potential vulnerability. Identify where external input enters the system and trace it through:

- HTTP request parameters, headers, cookies
- File uploads, user-provided paths
- Environment variables, config files (who can modify them?)
- Inter-service communication (is the caller authenticated?)
- Database content (was it validated on write, or do you trust it on read?)

Data that crosses a trust boundary should be validated, sanitized, or escaped before use. If it's not, that's a finding.

## Common Patterns to Look For

**Input validation** — Is user input validated before use? Are there length limits, type checks, range constraints? What happens with unexpected unicode, null bytes, or extremely long strings?

**Injection** — SQL, command, template, path traversal. Any place where user input is interpolated into a query, command, or path without proper escaping.

**Authentication and authorization** — Are endpoints protected? Can a user access resources belonging to another user? Are there privilege escalation paths? Is session management sound?

**Secrets** — API keys, tokens, passwords in code, config, logs, or error messages. Check `.env` files, hardcoded credentials, secrets passed as URL parameters (which end up in logs).

**Rate limiting and resource exhaustion** — Can an attacker trigger expensive operations without limits? Upload large files? Create unbounded allocations? Open connections that never close?

**Error handling** — Do error messages leak internal state, stack traces, or file paths? Does the system fail open (granting access on error) or fail closed?

## What Good Looks Like

A security finding should explain the attack vector, not just point at the code. "Missing input validation" is vague. "An attacker can submit a path like `../../etc/passwd` in the filename field, which is joined with the upload directory without sanitization, allowing arbitrary file read" is actionable.
