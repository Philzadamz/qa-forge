# QA Forge — admin guide

For the person who installs, configures, and looks after a QA Forge instance. The user guide
covers day-to-day testing.

## Install and first run

Requirements: `uv`, Node 20+, npm, and `make`. Local mode uses SQLite and local file storage
(see docs/decisions/001). Docker Compose is available for the full stack with Postgres and
MinIO.

```bash
make install                              # Python and Node dependencies
cp .env.example .env                      # then set the values below
make migrate                              # apply database migrations
make seed-admin EMAIL=you@example.com PASSWORD='a-long-password'
make seed-defaults                        # 31 default scenarios from the team template
make seed-report-defaults                 # exit criteria, approval roles, classification label
make dev                                  # API on :8000, web on :3000
```

Before any shared use, set these in `.env`:

| Setting | Why |
|---|---|
| `JWT_SECRET` | Signs sign-in tokens. The default is for local development only. |
| `SECRETS_KEY` | Fernet key that encrypts project secrets. See "Key rotation" below. |
| `DEEPSEEK_API_KEY` and `AI_PROVIDER=deepseek` | Enables real AI generation. The default `fake` provider returns no AI output. |
| `ENVIRONMENT=prod` | Turns on `Secure` for auth cookies. Serve the app over HTTPS. |
| `CORS_ORIGINS` | Must include the web origin users open. |

## Users and roles

Create accounts under **Admin Console → Users**. Roles:

- **Admin.** Sees all projects, manages types, defaults, templates, users, and the audit log.
- **User.** Sees the projects they own or are a member of.
- **Viewer.** Can sign in, but the workspace endpoints currently reject the role (403). A
  read-only viewer mode is not built yet; see "Known limits".

Deactivating a user blocks sign-in immediately. Password reset issues a one-hour link, which
the server writes to the application log. Hand it to the user out of band until an email
service is configured. Every reset is recorded in the audit log.

## Test case types, defaults, and templates

- **Types** (for example "Web Application") group the default scenarios a new suite starts with.
  Editing a default changes new suites only; existing suites keep the snapshot they were created
  from.
- **Templates.** The team's `.xlsx` and `.docx` templates in `templates/source/` are read-only
  inputs. Upload a new version under **Admin Console → Templates**. Word templates are
  auto-tokenized on upload.
- **Report defaults** set the exit criteria, approval roles, and classification label that appear
  on every report.

## Audit log

**Admin Console → Audit Log** lists every create, update, delete, sign-in, password reset,
and generated-case action, newest first. Filter by action or entity. Each entry records the
actor, entity, the request IP, and a diff of the change.

Entries older than `RETENTION_AUDIT_LOG_DAYS` (730 by default) are pruned by the retention
sweep. Export the log before then if you need it for longer.

## Usage and metrics

- **Dashboard** shows AI token use over the last 30 days, by feature, for the projects each user
  can see.
- **Cost estimate** stays at $0 until you set `AI_COST_PER_MILLION_INPUT_TOKENS` and
  `AI_COST_PER_MILLION_OUTPUT_TOKENS` to your provider's current rates. A hardcoded price would
  go stale.
- **`GET /metrics`** exposes Prometheus counters and histograms: AI tokens by model and
  direction, generation jobs by outcome, and Test Lab run durations by target and status. It
  has no authentication, so keep it on the internal network or behind your proxy. Counters are
  per process; for several API workers, set `PROMETHEUS_MULTIPROC_DIR`.
- **`GET /health`** is a liveness check. **`GET /ready`** checks the database and storage and
  returns 503 when either fails.
- Logs are JSON, one line per event, each with a request ID. Send a caller's `X-Request-ID`
  header to correlate with your own logs.

## Retention and deletion

Run the sweep on a schedule, for example a daily cron entry:

```bash
cd /path/to/qa-forge && make retention-sweep
```

It does three things:
- Deletes evidence older than `RETENTION_EVIDENCE_DAYS` (180 by default), including the image
  files.
- Removes the raw uploaded story files and rendered report files past the same window. The story
  text and report fields stay, since they are part of the suite history.
- Prunes audit log rows older than `RETENTION_AUDIT_LOG_DAYS` (730 by default).

Deleting a project purges its files at once, rather than waiting for the sweep. Shared admin
templates are not time-limited.

## Security controls

- Passwords are hashed with Argon2. Sign-in tokens are short-lived and stored in `httpOnly`,
  `SameSite=Lax` cookies.
- Sign-in is rate-limited to five attempts per minute for each address and email pair.
- Every endpoint checks the caller's role and whether they can access the specific project. Every
  workspace endpoint has a test that rejects anonymous requests, and the project-ownership and
  cross-user checks have their own tests.
- URLs the server fetches for API spec import must resolve to public addresses. Private, loopback,
  and cloud-metadata addresses are refused, and redirects are not followed. See
  docs/decisions/009 for the one remaining gap (DNS rebinding) and the `SSRF_ALLOWED_HOSTS`
  exception for internal hosts.
- Secrets are encrypted at rest with Fernet and are resolved only at the moment a run uses them.
- Uploads are checked by content. Evidence images are identified from their leading bytes
  (PNG, JPEG, GIF, WebP), and the stored extension comes from that check, not the client's filename.
  APKs must parse with `aapt` before they're stored.
- Containers run as a non-root user.
- CI runs `pip-audit` on the Python runtime dependencies, which blocks on findings, and `npm
  audit` on the web dependencies, which is currently informational.

### Key rotation

Changing `SECRETS_KEY` makes existing encrypted secrets unreadable. Re-enter them after a rotation,
or re-encrypt them with the old key before switching. There is no built-in re-encryption step yet.

### Backups

Back up two things together: the database (`DATABASE_URL`, default `var/qa_forge.db`) and the
storage root (`STORAGE_LOCAL_ROOT`, default `var/storage/`). A database backup without its storage
root has broken evidence and report links.

## Android runner

The Android runner needs an emulator that only QA Forge uses, configured by name:

- `ANDROID_AVD_NAME` names the AVD QA Forge boots or attaches to. It never acts on any other
  running emulator, even one attached to the same machine.
- `ANDROID_ADB_PATH`, `ANDROID_AAPT_PATH`, and `ANDROID_EMULATOR_PATH` must point at real binaries
  under your SDK. They are usually not on `PATH`.
- Appium must be running at `ANDROID_APPIUM_URL`.
- Use one Android run at a time per emulator. The runner does not queue them.

See docs/decisions/008 for the device-isolation design.

## Known limits

- **Concurrency caps are not enforced in code.** The PRD asks for 3 concurrent web runs and 1–2
  Android runs per host. Each run starts its own thread, so limit concurrent use operationally
  until the caps are added.
- **Viewer role is not usable.** A viewer can sign in but is rejected by the workspace endpoints.
  A read-only mode needs a product decision on what viewers see before it's built.
- **Single process.** Rate limiting and metrics are in-process. A multi-worker deployment needs a
  shared store (Redis) and `PROMETHEUS_MULTIPROC_DIR`.
- **No email.** Password reset links are written to the log.
- **Next.js advisories.** `npm audit` reports two findings in `postcss`, bundled under `next`
  15.5. The fix is a Next.js major upgrade. Tracked in docs/decisions/010.
- **Performance.** Document generation and export are well within PRD targets (docs/performance.md).
  Story generation time and concurrency have not been measured against a live model.
