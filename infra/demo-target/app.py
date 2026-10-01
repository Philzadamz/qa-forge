"""Tiny demo web app used as the Test Lab's Web-runner fixture (PRD §13.6).

Deliberately minimal and dependency-light (FastAPI + stdlib only — reuses the `services/api`
venv's FastAPI install, no separate project/lock file) so it's cheap to boot per test run and
predictable enough for both the deterministic default routines and agent-mode runs to target:
a login form (valid/invalid/blank/lockout), a session-gated dashboard, logout, and a fixed set
of security headers. Not a product — just a stable target.
"""

import os
import secrets as pysecrets
import time
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

DEMO_USERNAME = os.environ.get("DEMO_TARGET_USERNAME", "demo")
DEMO_PASSWORD = os.environ.get("DEMO_TARGET_PASSWORD", "Demo12345!")
SESSION_TIMEOUT_SECONDS = float(os.environ.get("DEMO_TARGET_SESSION_TIMEOUT", "900"))
LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW_SECONDS = 60.0

app = FastAPI(title="QA Forge Demo Target")

# session token -> (username, last_seen_monotonic)
_sessions: dict[str, tuple[str, float]] = {}
# username -> list of failed-attempt timestamps (monotonic) within the lockout window
_failed_attempts: dict[str, list[float]] = {}

SESSION_COOKIE = "demo_session"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


app.add_middleware(SecurityHeadersMiddleware)


def _page(body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Demo Target</title></head>
<body>{body}</body>
</html>"""


def _login_page(*, error: str | None = None) -> str:
    error_html = f'<p id="error" role="alert">{error}</p>' if error else ""
    return _page(f"""
<h1>Sign in</h1>
{error_html}
<form method="post" action="/login">
  <label for="username">Username</label>
  <input id="username" name="username" type="text" autocomplete="username">
  <label for="password">Password</label>
  <input id="password" name="password" type="password" autocomplete="current-password">
  <button type="submit">Log in</button>
</form>
""")


def _is_locked(username: str) -> bool:
    attempts = _failed_attempts.get(username, [])
    now = time.monotonic()
    recent = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[username] = recent
    return len(recent) >= LOCKOUT_THRESHOLD


def _record_failure(username: str) -> None:
    _failed_attempts.setdefault(username, []).append(time.monotonic())


def _current_session(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or token not in _sessions:
        return None
    username, last_seen = _sessions[token]
    if time.monotonic() - last_seen > SESSION_TIMEOUT_SECONDS:
        del _sessions[token]
        return None
    _sessions[token] = (username, time.monotonic())
    return username


@app.get("/", response_class=RedirectResponse)
def root() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form() -> str:
    return _login_page()


@app.post("/login", response_model=None)
def login_submit(
    username: Annotated[str, Form()] = "", password: Annotated[str, Form()] = ""
) -> HTMLResponse | RedirectResponse:
    if not username or not password:
        return HTMLResponse(
            _login_page(error="Username and password are required."), status_code=400
        )
    if _is_locked(username):
        return HTMLResponse(_login_page(error="Account locked. Try again later."), status_code=423)
    if username != DEMO_USERNAME or password != DEMO_PASSWORD:
        _record_failure(username)
        return HTMLResponse(_login_page(error="Invalid username or password."), status_code=401)
    _failed_attempts.pop(username, None)
    token = pysecrets.token_urlsafe(24)
    _sessions[token] = (username, time.monotonic())
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.get("/dashboard", response_class=HTMLResponse, response_model=None)
def dashboard(request: Request) -> HTMLResponse | RedirectResponse:
    username = _current_session(request)
    if username is None:
        return RedirectResponse("/login", status_code=303)
    response = HTMLResponse(
        _page(f"""
<h1 id="welcome">Welcome, {username}</h1>
<form method="post" action="/logout">
  <button type="submit">Log out</button>
</form>
""")
    )
    # An authenticated page must never be restorable from the browser's back/forward cache
    # after logout — without this, pressing Back shows the stale dashboard from bfcache even
    # though the session was invalidated server-side.
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _sessions.pop(token, None)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8990")))
