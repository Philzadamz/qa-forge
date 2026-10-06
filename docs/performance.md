# Performance targets — measured

PRD §12 sets performance targets. Measured on 2026-10-04, macOS, local SQLite, API in-process.
Reproduce with:

```bash
cd services/api && uv run python scripts/measure_targets.py
```

The script uses a throwaway database and storage root, never the dev DB, and the AI provider is
the fake client, so no network calls are made.

| Target (PRD §12) | Requirement | Measured (median of 5, or 3 where noted) | Result |
|---|---|---|---|
| Defaults render | < 500 ms | 3 ms (31 default scenarios) | pass |
| xlsx export | < 10 s for 300 cases | 692 ms (300 cases, team template) | pass |
| docx render | < 5 s | 139 ms (tokenized team template) | pass |
| Story generation | < 3 min for a 3-page story (Standard depth) | **not measured** | see below |
| Concurrency | 20 users; 3 web runs and 1–2 Android runs at once | **not measured** | see below |

## Not measured, and why

- **Story generation.** The target depends on the live model's latency and cannot be timed
  without a provider key and a real story. Run one generation on a 3-page story against the
  DeepSeek provider and record the time here. The job's wall-clock time is in
  `generation_jobs.started_at` / `finished_at`, and the `qaforge_generation_jobs_total` counter is
  on `/metrics`.
- **Concurrency.** The Test Lab runs one browser or emulator per job in a background thread. Load
  testing it at the stated concurrency needs a host with the emulator configured, which this
  measurement didn't have. The per-job cap is not yet enforced in code; see the admin guide's
  "Known limits".
- **Test Lab run durations** depend on the target app and the model. They are recorded in the
  `qaforge_run_duration_seconds` histogram on `/metrics` for each run.
