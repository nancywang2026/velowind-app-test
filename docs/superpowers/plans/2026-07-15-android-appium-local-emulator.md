# Android Appium Local Emulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local Android emulator Appium support that mirrors the existing iOS pytest/Appium workflow.

**Architecture:** Add Android-specific config, driver, preflight, runner, and pytest fixtures while keeping existing iOS files stable. Android artifacts live in `.tmp/appium-android`; test suite YAML behavior matches the iOS runner.

**Tech Stack:** Python, pytest, Appium Python Client, UiAutomator2, adb, pnpm scripts, Allure.

---

### Task 1: Android Config And Capabilities

**Files:**
- Create: `apps/velowind-app/appium/velowind_appium/android_config.py`
- Create: `apps/velowind-app/appium/tests/test_android_config.py`
- Create: `apps/velowind-app/appium/android-appium.yaml`

- [x] **Step 1: Write failing tests** for default config, YAML/env overrides, APK capabilities, installed-app capabilities, and missing package/activity validation.
- [x] **Step 2: Run tests** with `PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests/test_android_config.py -q` and verify import failures.
- [x] **Step 3: Implement `AndroidAppiumConfig`, `load_android_config`, `build_android_capabilities`, and emulator detection helpers.**
- [x] **Step 4: Re-run the config tests** and verify they pass.

### Task 2: Android Driver And Runner

**Files:**
- Create: `apps/velowind-app/appium/velowind_appium/android_driver.py`
- Create: `apps/velowind-app/appium/velowind_appium/run_android_tests.py`
- Create: `apps/velowind-app/appium/tests/test_run_android_tests.py`

- [x] **Step 1: Write failing runner tests** mirroring iOS suite behavior but using `.tmp/appium-android` and Android test path.
- [x] **Step 2: Run tests** and verify missing module failure.
- [x] **Step 3: Implement Android driver and runner.**
- [x] **Step 4: Re-run runner tests** and verify they pass.

### Task 3: Android Preflight

**Files:**
- Create: `apps/velowind-app/appium/velowind_appium/android_preflight.py`
- Create: `apps/velowind-app/appium/tests/test_android_preflight.py`

- [x] **Step 1: Write failing tests** for adb device parsing, package/activity validation, and APK file checks.
- [x] **Step 2: Run tests** and verify missing module or missing functions.
- [x] **Step 3: Implement preflight helpers and `main`.**
- [x] **Step 4: Re-run preflight tests** and verify they pass.

### Task 4: Android Pytest Fixtures And Smoke Test

**Files:**
- Create: `apps/velowind-app/appium/tests/android_smoke/conftest.py`
- Create: `apps/velowind-app/appium/tests/android_smoke/test_android_feature_walkthrough.py`
- Create: `apps/velowind-app/appium/tests/android_smoke/__init__.py`

- [x] **Step 1: Add fixture code** that creates an Android driver, ensures artifact dir, wraps steps, and captures failure artifacts.
- [x] **Step 2: Add smoke walkthrough** for the Android home categories, with optional full cases for bottom-tab compatibility.
- [x] **Step 3: Run collection** with `PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests/android_smoke --collect-only -q`.

### Task 5: Scripts And Documentation

**Files:**
- Modify: `package.json`
- Modify: `apps/velowind-app/appium/README.md`
- Create: `apps/velowind-app/appium/test-suites/android-smoke.yaml`

- [x] **Step 1: Add pnpm Android commands** for preflight, smoke, full, suite, and Allure report.
- [x] **Step 2: Add README Android setup and run instructions.**
- [x] **Step 3: Add Android smoke suite YAML.**
- [x] **Step 4: Run targeted unit tests and pytest collection.**
