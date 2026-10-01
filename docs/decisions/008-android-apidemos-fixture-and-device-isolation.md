# 008 — ApiDemos as the Android fixture; the local provider never touches a device it wasn't told about

**Status:** accepted · **Date:** 2026-10-01

## Context
PRD §13.6 asks for "Android runner smoke test against a sample open-source APK (skipped when
no KVM)." Unlike `infra/demo-target`/`infra/demo-api` (Phases 5/6, both hand-built in this
repo), a native Android app needs a full SDK build toolchain (Gradle, a signing config,
resource compilation) that isn't realistic to stand up from scratch here.

Separately: the machine this was built and verified on turned out to have hardware
virtualization available and an Android emulator *already running*, started independently of
this work. A naive "find any attached emulator and use it" provider would have grabbed that
instance — wrong, and risky, since installing/uninstalling APKs and force-stopping apps on
someone else's running instance is exactly the kind of action that needs explicit scope.

## Decisions
1. **Fixture app:** `infra/demo-android/ApiDemos-debug.apk` is downloaded from the
   `android-apidemos` npm package (`github.com/appium/android-apidemos`) — a fork of Google's
   own ApiDemos sample, maintained by the Appium project *specifically* to be a stable
   Appium-automation test target. It's committed as a binary fixture (6.4 MB), the same way
   `templates/tokenized/*.docx` is — not fetched at test time, so a run never depends on a
   third party being reachable. Rationale over hand-building: real multi-screen native
   navigation (needed to exercise `tap`/`scroll_to`/`back`) that a from-scratch app without a
   build toolchain couldn't practically match, and it's the de facto standard fixture for this
   exact purpose in the Android-automation ecosystem.
2. **Device isolation:** `LocalEmulatorProvider` (`android_provider.py`) identifies a usable
   emulator by asking each attached device "which AVD are you running" (`adb -s <serial> emu
   avd name`) and only ever acts on one matching `Settings.android_avd_name` — never just the
   first entry in `adb devices`. If none match, it boots a fresh instance of that specific AVD
   rather than touching an unrelated one. This was verified for real on a machine with two
   simultaneous emulator instances (the test machine's own pre-existing one, left completely
   alone, and a second `QAForgeTest` AVD created and used for this phase's development and
   tests) — `tests/unit/test_android_provider.py` pins this behavior with mocked `adb` output
   so it can't silently regress.

## Consequences
- A fresh checkout needs `infra/demo-android/ApiDemos-debug.apk` present (it's committed, so
  this is automatic) and a locally-configured AVD named to match `ANDROID_AVD_NAME` (default
  `QAForgeTest`) for the live tests in `tests/execution/` to run — otherwise they skip
  (`android_device_udid` fixture), the same graceful-skip pattern as the Playwright-dependent
  Web/API live tests.
- `aapt`/`aapt2` and the `emulator` binary are typically **not** on `PATH` even with the
  Android SDK installed — `ANDROID_AAPT_PATH`/`ANDROID_EMULATOR_PATH`/`ANDROID_ADB_PATH` need
  real paths in `.env` (documented in `.env.example`); there's no auto-discovery.
- `RemoteAppiumProvider` (the PRD's device-farm fallback) stays an explicit stub — no farm
  account exists to build and verify against, and docs/decisions/005's lesson (an untested
  code path is worse than a clear `NotImplementedError`) applies here too.
