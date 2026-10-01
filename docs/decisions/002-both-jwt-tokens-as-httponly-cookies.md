# 002 — Both JWT tokens as httpOnly cookies

**Status:** accepted · **Date:** 2026-09-30

## Context
PRD §2 specifies "JWT access tokens (15 min) + refresh tokens (7 days, httpOnly cookie)" but
doesn't say how the access token should reach the browser. The frontend scaffold built in
Phase 0 (`apps/web/src/lib/api.ts`) already calls every API request with
`credentials: "include"` and never reads a token from JS.

## Decision
Set the access token as an httpOnly cookie too, not just the refresh token. Both cookies
(`qa_forge_access`, `qa_forge_refresh`) are `httponly`, `samesite=lax`, and `secure` outside
`dev`/`test`.

## Consequences
- The access token is never reachable by page JS, closing off the main XSS token-theft path,
  at no cost: the SPA never needed to read it anyway (it rides on cookies via
  `credentials: "include"`).
- `POST /auth/refresh` re-sets both cookies from the refresh cookie; there's no client-side
  token refresh logic to write.
- If a future client (mobile app, CLI) needs the API without cookies, it'll need a separate
  bearer-token login path — not needed yet, not built.
