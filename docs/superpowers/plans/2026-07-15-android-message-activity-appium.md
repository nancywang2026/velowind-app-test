# Android Message And Activity Appium Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all eight message and activity Appium cases pass on `emulator-5554` with the requested login account.

**Architecture:** Fix confirmed product-layout defects in the application source and Android-specific automation compatibility in the Appium harness. Every defect gets a focused failing test before its minimal fix, then the affected case is rerun before the full suite.

**Tech Stack:** React Native/Taro, Jest, Python, pytest, Appium, Android Gradle, adb

---

### Task 1: Restore The Android Root Bottom Navigation

**Files:**
- Modify: `/Users/test/Documents/velowind-app-dev/apps/velowind-app/src/components/navigation/root-tab-shell/index.tsx`
- Test: `/Users/test/Documents/velowind-app-dev/apps/velowind-app/src/components/navigation/root-tab-shell/__tests__/index.test.tsx`

- [ ] **Step 1: Write the failing Android layout regression test**

Change the native Android assertion to require the shell to rely on `flex: 1` without fixed `height` or `minHeight`, because the Activity content host is smaller than the full display viewport.

- [ ] **Step 2: Run the focused Jest test and verify RED**

Run the repository's existing Jest command for `root-tab-shell/__tests__/index.test.tsx` and confirm it fails because the shell still emits `height: 844px` and `min-height: 844px`.

- [ ] **Step 3: Implement the platform-aware shell sizing**

Keep the calculated viewport height for Web, but omit fixed height styles on native platforms so the existing `flex: 1` fills the actual host bounds.

- [ ] **Step 4: Run the focused Jest test and verify GREEN**

Run the same Jest target and confirm all `RootTabShell` tests pass.

- [ ] **Step 5: Rebuild and install the Android release APK**

Build `apps/velowind-app/android/app/build/outputs/apk/release/app-release.apk`, reinstall it on `emulator-5554`, and confirm `bottom-nav-activity` appears in the Android UI tree after login.

### Task 2: Run And Repair The Activity Browse Case

**Files:**
- Modify if required: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/velowind_appium/modules/activity_browse.py`
- Test if required: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/tests/test_activity_browse_helpers.py`

- [ ] **Step 1: Rerun the activity browse case on the emulator**

Use the configured Appium server and credentials environment variables; verify the bottom activity tab opens and capture any next failure artifacts.

- [ ] **Step 2: Add a focused failing helper test for any new Android-only defect**

Model the exact locator or page-source evidence from the failed emulator run and confirm the new test fails for the observed reason.

- [ ] **Step 3: Implement only the confirmed compatibility fix**

Update the narrow activity helper involved in the failure without changing unrelated category matching behavior.

- [ ] **Step 4: Verify the helper and emulator case pass**

Run the focused pytest helper target, then rerun `test_ios_activity_browse.py` on `emulator-5554`.

### Task 3: Run And Repair Both Publish Cases

**Files:**
- Modify if required: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/velowind_appium/modules/activity.py`
- Modify if required: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/velowind_appium/modules/message_detail.py`
- Test if required: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/tests/test_activity_helpers.py`
- Test if required: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/tests/test_message_detail_helpers.py`

- [ ] **Step 1: Run the message publish case and retain failure artifacts**

Run `message/test_ios_publish_note.py` using the Android environment and identify the first failing UI transition from its screenshot and XML.

- [ ] **Step 2: Use RED-GREEN for each confirmed message publish defect**

Add one focused Python regression test, verify its expected failure, implement the smallest helper change, and rerun both the helper and emulator case.

- [ ] **Step 3: Run the activity publish case and retain failure artifacts**

Run `activity/test_ios_publish_activity.py` using the same Android session configuration and identify the first failing UI transition.

- [ ] **Step 4: Use RED-GREEN for each confirmed activity publish defect**

Add one focused Python regression test, verify its expected failure, implement the smallest helper change, and rerun both the helper and emulator case.

### Task 4: Full Verification And Cleanup

**Files:**
- Verify: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/tests/message/`
- Verify: `/Users/test/Documents/velowind-app-dev-test/apps/velowind-app/appium/tests/activity/`
- Clean temporary mirror lines if present: `/Users/test/Documents/velowind-app-dev/node_modules/@react-native/gradle-plugin/settings.gradle.kts`
- Clean temporary mirror lines if present: `/Users/test/Documents/velowind-app-dev/node_modules/@react-native/gradle-plugin/build.gradle.kts`

- [ ] **Step 1: Run all eight Appium cases in one fresh invocation**

Run the five previously passing message cases plus message publish, activity browse, and activity publish together. Require pytest exit code 0 and `8 passed` from this fresh run.

- [ ] **Step 2: Run relevant Python regression tests**

Run the Android action, driver, session, home feed, message detail, note picker, activity, and runner helper tests; separate any known fixture-data mismatch caused by user-owned YAML from code regressions.

- [ ] **Step 3: Rerun the focused application Jest test**

Confirm the native shell sizing regression remains green after the installed APK verification.

- [ ] **Step 4: Remove build-only mirror edits and inspect both repositories**

Delete only the temporary mirror lines introduced during the APK build, then inspect `git status` and `git diff` without reverting user changes.

- [ ] **Step 5: Report fresh evidence**

Report the exact emulator pass count, unit-test results, APK used, root causes fixed, and any user-owned changes intentionally preserved.
