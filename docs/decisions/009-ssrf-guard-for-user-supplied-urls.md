# 009 — SSRF guard for server-side fetches of user-supplied URLs

**Status:** accepted · **Date:** 2026-10-04

## Context
`POST /api-specs/parse` (kind=`openapi`, `url=`) fetches a URL the user typed, from the server.
Before Phase 8 nothing constrained that host, so a user could point the server at
`http://169.254.169.254/` (cloud metadata), `localhost` admin routes, or any private address.
PRD §12 lists an SSRF allowlist as a security requirement.

## Decisions
1. **Resolve, then reject non-public addresses.** `app/core/ssrf.py` resolves the host and
   rejects loopback, private, link-local, reserved, multicast, and unspecified addresses. Checking
   the resolved address (not the string) catches `localhost`, decimal/hex IP tricks, and DNS names
   that point inward.
2. **No redirect following.** The fetch uses `follow_redirects=False`, so a public host can't
   bounce the request to an internal one.
3. **Operator allowlist for legitimate internal hosts.** `SSRF_ALLOWED_HOSTS` (JSON list, empty by
   default) exempts named hosts. It exists so the local `infra/demo-api` fixture can be used in
   live tests; production leaves it empty.
4. **Known residual risk: DNS rebinding.** The address is checked, then `httpx` resolves again
   when it connects. A hostile DNS server can return a public address first and a private one
   second. Closing this needs connecting to the already-validated IP with the original `Host`
   header. It's deferred: this is a single-tenant internal tool, the fetch is a one-shot spec
   import with a 10-second timeout, and the response body is returned only to the same
   authenticated user.

## Consequences
- Specs served only from internal hosts must be imported by pasting or uploading the file, or the
  host must be added to `SSRF_ALLOWED_HOSTS`.
- The Test Lab's browser and API runners already constrain targets to the project's configured
  URL prefix (`_check_allowlist`), so they aren't covered by this guard. That prefix is set by
  project admins, not by free-form request input.
