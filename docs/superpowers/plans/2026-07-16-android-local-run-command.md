# Android Local Run Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-command local Android Appium entrypoint that bakes in the known emulator, server, app, and login defaults for this workspace.

**Architecture:** Reuse the existing root-level `pnpm` Android Appium scripts and prepend the known local environment variables inline, so the test runner and preflight logic stay unchanged. Keep the change scoped to `package.json` to avoid touching Python runtime behavior.

**Tech Stack:** pnpm scripts, shell environment variables, Python Appium runner

---

### Task 1: Add the local Android script

**Files:**
- Create: `docs/superpowers/plans/2026-07-16-android-local-run-command.md`
- Modify: `package.json`

- [ ] **Step 1: Add a new root script that exports the local Android defaults inline**

Update `package.json` by adding an `appium:android:test:local` script alongside the existing Android scripts. The command should set:

```bash
VW_APPIUM_SERVER_URL=http://127.0.0.1:4725
VW_APPIUM_PLATFORM=android
VW_ANDROID_UDID=emulator-5554
VW_ANDROID_DEVICE_NAME="Android Emulator"
VW_ANDROID_APP_PACKAGE=com.velowind.rider
VW_ANDROID_APP_ACTIVITY=.MainActivity
VW_LOGIN_USERNAME=13381509990
VW_LOGIN_PASSWORD=12345678
```

Then run:

```bash
pnpm appium:android:preflight && PYTHONPATH=apps/velowind-app/appium python3 -m velowind_appium.run_android_tests
```

- [ ] **Step 2: Run the new command**

Run:

```bash
pnpm appium:android:test:local
```

Expected: the command reaches the existing Android preflight and launches the runner without requiring manual `export` steps in the terminal.

- [ ] **Step 3: Verify the script is registered**

Run:

```bash
cat package.json
```

Expected: the new `appium:android:test:local` entry is present in the root `scripts` map.
