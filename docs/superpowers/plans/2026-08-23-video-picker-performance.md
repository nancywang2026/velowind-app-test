# Video Picker Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make first-video selection continue as soon as the iOS preview confirmation is ready, with a maximum 10-second wait and no Collections navigation.

**Architecture:** Keep the public `choose_video_from_library` contract unchanged. Add a focused readiness helper in `photo_picker.py`; `_confirm_video_picker_selection` uses it before the existing tap/fallback logic. Unit tests use a fake driver and patched clock to verify both early and timeout paths.

**Tech Stack:** Python, pytest, Appium/XCUITest, Allure.

---

### Task 1: Lock the readiness behavior with tests

**Files:**
- Modify: `apps/velowind-app/appium/tests/unit-test/test_photo_picker_helpers.py`
- Test: `apps/velowind-app/appium/tests/unit-test/test_photo_picker_helpers.py`

- [ ] **Step 1: Write a failing test** for `_wait_for_video_preview_confirmation` returning immediately when a confirmation element is visible, and returning false after the bounded timeout when it never appears.
- [ ] **Step 2: Run the focused tests** with `pytest -q tests/unit-test/test_photo_picker_helpers.py -k video_preview_confirmation`; confirm the new tests fail because the helper is absent.
- [ ] **Step 3: Keep the direct Videos-path regression test** asserting `_select_ios_video_filter` does not call Collections/精选集 navigation.

### Task 2: Implement bounded readiness polling

**Files:**
- Modify: `apps/velowind-app/appium/velowind_appium/modules/photo_picker.py`

- [ ] **Step 1: Add a helper** that checks fast confirmation locators (`确认`, `Confirm`, `完成`, `Done`) and the preview marker without an unconditional sleep.
- [ ] **Step 2: Change `_confirm_video_picker_selection`** to wait at most 10 seconds, tap as soon as readiness is detected, and retain the current fallback confirmation path.
- [ ] **Step 3: Keep the existing post-confirm transition wait and diagnostics unchanged.**

### Task 3: Verify and measure

**Files:**
- No production files beyond Task 2.
- Artifacts: `.tmp/appium-ios/runs/<run-id>/allure-results/` and `.tmp/appium-ios/runs/<run-id>/allure-report/`.

- [ ] **Step 1: Run picker and message helper tests** and confirm all pass.
- [ ] **Step 2: Run the dedicated iOS video publish test on the connected real device with profiling and Allure enabled.**
- [ ] **Step 3: Compare the picker profile timings and report the real-device result, including any WDA/device blocker.
