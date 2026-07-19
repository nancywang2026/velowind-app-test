# iOS Activity Session Date Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the iOS real-device add-session Appium case fill and confirm session datetime fields without changing Android automation behavior.

**Architecture:** Keep the existing activity session automation module as the single owner of session datetime UI handling. Add iOS-only custom picker recognition, parsing, and selection helpers, then route `_write_session_datetime_value()` by platform before falling back to text fields.

**Tech Stack:** Python, pytest, Appium Python client, Selenium/Appium driver APIs.

---

### Task 1: iOS Picker Detection And Parsing

**Files:**
- Modify: `apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py`
- Modify: `apps/velowind-app/appium/velowind_appium/modules/activity_sessions.py`

- [ ] **Step 1: Write failing tests for custom iOS picker detection and parsing**

Add tests that assert `_ios_datetime_picker_visible()` returns true for `已选择时间 7月18日 22点 取消 确认 月 日 时`, and `_ios_datetime_picker_current_parts_from_source()` returns `{"month": "07", "day": "18", "hour": "22", "minute": "00"}`.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -k "ios_datetime_picker" -q`

Expected: FAIL because the parser is missing and custom iOS picker visibility returns false.

- [ ] **Step 3: Implement minimal detection and parsing helpers**

Update `_ios_datetime_picker_visible(page_source)` to accept the custom iOS panel tokens and add `_ios_datetime_picker_current_parts_from_source(page_source)`.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -k "ios_datetime_picker" -q`

Expected: PASS.

### Task 2: iOS Writer Routing

**Files:**
- Modify: `apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py`
- Modify: `apps/velowind-app/appium/velowind_appium/modules/activity_sessions.py`

- [ ] **Step 1: Write failing routing tests**

Add tests proving iOS drivers call `_write_ios_datetime_picker_value()` when the iOS picker is visible, and Android drivers do not call the iOS writer.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -k "write_session_datetime_value" -q`

Expected: FAIL because `_write_session_datetime_value()` has no iOS writer route.

- [ ] **Step 3: Implement minimal route**

In `_write_session_datetime_value()`, check `_is_ios_driver(driver)` first. If true and the iOS picker is visible, call `_write_ios_datetime_picker_value(driver, keyword, value)`. Otherwise keep existing Android and text-field paths.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -k "write_session_datetime_value" -q`

Expected: PASS.

### Task 3: iOS Custom Picker Selection

**Files:**
- Modify: `apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py`
- Modify: `apps/velowind-app/appium/velowind_appium/modules/activity_sessions.py`

- [ ] **Step 1: Write failing test for iOS writer**

Add a fake-driver test where the current iOS source is `7月18日 22点`, target is `2026-07-23 18:00`, and the writer taps iOS wheel positions until page source reads month `07`, day `23`, hour `18`.

- [ ] **Step 2: Run test to verify RED**

Run: `python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -k "ios_datetime_picker_value" -q`

Expected: FAIL until iOS writer exists.

- [ ] **Step 3: Implement iOS writer**

Implement `_write_ios_datetime_picker_value()`, `_fill_ios_datetime_picker_fields()`, `_ios_datetime_picker_wheel_center()`, and small step helpers using iOS-only tap coordinates and condition-based source readback.

- [ ] **Step 4: Run test to verify GREEN**

Run: `python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -k "ios_datetime_picker_value" -q`

Expected: PASS.

### Task 4: Verification

**Files:**
- Verify: `apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py`
- Verify: `apps/velowind-app/appium/tests/activity/test_manage_activity_session.py`

- [ ] **Step 1: Run focused unit tests**

Run: `python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -q`

Expected: PASS.

- [ ] **Step 2: Run target iOS real-device test**

Run the repository's existing iOS Appium pytest command for `apps/velowind-app/appium/tests/activity/test_manage_activity_session.py::test_user_can_add_activity_session_from_my_approved_activity`.

Expected: pytest exit code 0.

- [ ] **Step 3: Inspect diff**

Run: `git diff -- apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py apps/velowind-app/appium/velowind_appium/modules/activity_sessions.py`

Expected: Only Appium automation and unit test changes are present, with iOS logic behind `_is_ios_driver(driver)`.
