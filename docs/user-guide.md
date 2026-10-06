# QA Forge — user guide

For testers and QA leads using QA Forge day to day. The admin guide covers setup and
configuration.

## Signing in

Sign in with the email and password your admin gave you. After five failed attempts within a
minute the sign-in is temporarily blocked. If you forget your password, use **Forgot password**
on the sign-in page; the reset link is delivered out of band, since this install has no email
service configured.

## Your dashboard

The dashboard shows what you can see: projects, suites, Test Lab runs from the last 30 days with
their pass rate, the most recent runs, and AI token usage broken down by feature. Only projects
you own or belong to are counted, so the numbers reflect your own work.

## Projects

A project is a product or application under test. It holds its suites, user stories, APKs for
Android testing, and secrets. You see projects you own or have been added to as a member.
Deleting a project removes its uploaded files and generated reports from storage immediately.

## Test suites

A suite is one test cycle for a project, built from a test case type (for example "Web
Application"). A new suite starts with the type's default scenarios. You can add more in three
ways:

- **Generate from user stories.** Upload or paste a story. QA Forge analyses it, drafts
  functional cases, and removes duplicates. Generation runs in the background and streams
  progress. Story text is masked for personal data before it is sent to the AI model.
- **Import an API spec.** Paste or upload an OpenAPI, Postman, or curl definition, pick the
  endpoints, and generate API test cases. Specs can also be fetched from a URL, but only public
  hosts are allowed (see the admin guide).
- **Add by hand** from the case table.

Each case has a status, actual result, priority, and evidence group. Use the bulk actions to
update many cases at once, for example "Mark all as passed".

## Running tests in the Test Lab

Tick **Run in Test Lab** on the cases you want to execute, then choose a target:

- **Web.** Enter the base URL. An AI agent drives a browser through the case steps, takes
  screenshots at assertions and failures, and records a verdict.
- **API.** Runs deterministic HTTP requests built from the case's request plan. Values can chain
  from one case to the next, for example a token from a login response.
- **Android.** Choose an APK that has been uploaded to the project. The app is installed on the
  test emulator, driven through each case, and checked for crashes. A crash fails the case
  regardless of what the agent reports.

Runs stream progress live. When a run finishes, its verdicts are **not yet applied**. Review
them on the run page, then choose **Apply** to write the status and result into the suite. Nothing
in the Test Lab overwrites a case's status without that step.

Secrets stored on the project are referenced by name in steps (for example `{{secret_password}}`).
QA Forge substitutes the value only at the moment it's used, and keeps it out of run logs and
step records. Screenshots, however, capture whatever is on screen, so a secret that is shown
on the page during a run can appear in an evidence image. Review evidence before sharing it.

## Evidence

Screenshots from manual runs and from the Test Lab are attached to the case they belong to. Each
case lists its evidence, and it can be downloaded or removed. Evidence and uploaded files are
removed automatically after the retention period set by your admin (180 days by default).

## Bugs

Raise defects from a failing case. Each bug records its severity, status, and the case it came
from. Bug counts feed the report.

## Reports

Generate a report for a suite to draft the QA summary. QA Forge fills in the team's Word template
from the suite's results, bugs, and the report defaults. The AI draft of feature descriptions and
comments is a starting point: review and edit it before you render the final document. The
document keeps the team's exact labels and layout.

## What the AI does and doesn't do

- It drafts cases, descriptions, and comments. A person decides what is kept.
- It never changes a case's verdict on its own. Test Lab results wait for you to apply them.
- A run's verdict can be wrong. A crash, an unreachable app, or a model error is shown as
  **blocked** or **error**, not as a pass.

## Known limits

- The AI provider can run out of credit. When that happens, generation and runs stop with a clear
  error. Your data is not lost, and you can retry once credit is restored.
- Android runs need an emulator configured by your admin. If it isn't available, the run reports
  an error rather than silently skipping.
