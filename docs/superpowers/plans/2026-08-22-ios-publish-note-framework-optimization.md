# iOS Publish Note Framework Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stable, diagnosable locator/wait layer and reduce redundant waits in the iOS real-device and simulator publish-note flow.

**Architecture:** `actions.py` owns ordered locator candidates, shared-deadline polling, and diagnostic errors. `message_detail.py` migrates only the iOS publish hot path while preserving Android and existing public helper contracts. `session.py` adds a publish-ready fast path so an already-prepared pytest session is reused.

**Tech Stack:** Python 3, pytest, Appium Python Client, Selenium WebDriver, YAML suite profiles

---

## File map

- Create `apps/velowind-app/appium/tests/unit-test/test_actions.py` for locator priority, shared timeout, optional lookup, diagnostics, and transient errors.
- Modify `apps/velowind-app/appium/velowind_appium/actions.py` for candidate model, polling, tapping, summaries, and compatibility wrappers.
- Modify `apps/velowind-app/appium/velowind_appium/session.py` and `apps/velowind-app/appium/tests/shared_publish_note.py` for publish-session reuse.
- Modify `apps/velowind-app/appium/velowind_appium/modules/message_detail.py` and its helper tests for semantic publish-note candidates.
- Create `apps/velowind-app/appium/test-suites/ios-publish-note.yaml` and update `apps/velowind-app/appium/README.md`.

### Task 1: Locator candidate core

**Files:** `actions.py`, new `tests/unit-test/test_actions.py`

- [ ] Write failing fake-driver tests: accessibility id wins over text; `wait_for_first(timeout=0, required=False)` checks every candidate once.
- [ ] Run `PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_actions.py -q`; expect missing API failures.
- [ ] Add frozen `LocatorCandidate(kind, value, label=None)`, constructors `accessibility_id`, `text`, `ios_predicate`, `xpath`, and `_candidate_locator()` mapping to existing platform-aware locators.
- [ ] Implement `find_first()` in declaration order and `wait_for_first()` with one monotonic deadline, always performing an initial poll; continue on `NoSuchElementException`, `StaleElementReferenceException`, and recoverable `WebDriverException`.
- [ ] Re-run the focused test; expect pass.
- [ ] Commit with `git add apps/velowind-app/appium/velowind_appium/actions.py apps/velowind-app/appium/tests/unit-test/test_actions.py && git commit -m "feat(appium): add ordered locator candidates"`.

### Task 2: Optional waits and diagnostics

**Files:** `actions.py`, `tests/unit-test/test_actions.py`

- [ ] Add failing tests for `LocatorTimeoutError` content (logical name, rendered candidates, attempted order, elapsed time, bounded page summary), optional timeout returning `None`, `tap_first()` clicking, and stale-first-candidate fallback.
- [ ] Run the focused action test; expect missing diagnostic/tap API failures.
- [ ] Add `LocatorTimeoutError(TimeoutException)`, `_page_summary(driver, limit=8)`, and `tap_first(driver, candidates, logical_name, timeout, required)`; include `kind=value` candidates and page summary in the exception.
- [ ] Refactor `tap_if_present()` and `tap_text_if_present()` to delegate to `tap_first(..., required=False)` while preserving their boolean contracts.
- [ ] Run `PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_actions.py apps/velowind-app/appium/tests/unit-test/test_android_actions.py -q`; expect pass.
- [ ] Commit with `git add apps/velowind-app/appium/velowind_appium/actions.py apps/velowind-app/appium/tests/unit-test/test_actions.py && git commit -m "feat(appium): diagnose locator wait failures"`.

### Task 3: Publish-ready session reuse

**Files:** `session.py`, `tests/shared_publish_note.py`, `tests/unit-test/test_session_setup.py`

- [ ] Add a failing test that monkeypatches `_publish_entry_ready()` true and asserts `dismiss_common_system_alerts()` is not called; add a runner test proving preparation happens once.
- [ ] Run `PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q -k 'publish or publish_entry'`; expect the current alert scan to be observed.
- [ ] Start `ensure_logged_in_for_publish_entry()` with `if _publish_entry_ready(driver): return False` before optional alert handling.
- [ ] In `run_publish_note_case()`, retain only the `prepare-home-session` step calling `ensure_logged_in_for_publish_entry()`; remove standalone alert dismissal/import.
- [ ] Run session and message helper regressions; expect pass.
- [ ] Commit with `git add apps/velowind-app/appium/velowind_appium/session.py apps/velowind-app/appium/tests/shared_publish_note.py apps/velowind-app/appium/tests/unit-test/test_session_setup.py && git commit -m "perf(appium): reuse publish-ready iOS session"`.

### Task 4: iOS publish-note semantic migration

**Files:** `message_detail.py`, `tests/unit-test/test_message_detail_helpers.py`

- [ ] Add failing tests monkeypatching `tap_first()` and asserting first candidates: `bottom-nav-publish`, `publish-type-note`, `note-title-input`, `note-body-input`, and `note-submit-button`.
- [ ] Run `PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q -k 'semantic or publish_entry'`; expect failure.
- [ ] Declare ordered candidates with stable ids first, then existing text/predicate, then module-specific XPath fallbacks. Include topic, location, allow-comments, image, and submit groups.
- [ ] For iOS, use `tap_first(..., required=False, timeout=0.8)` for optional entry/type controls and `wait_for_first(..., required=True)` for title/body before `_replace_text()`; use semantic candidates for submit/topic/location/comments, with coordinates last. Leave Android branches unchanged.
- [ ] Replace publisher-entry `sleep(0.5)` calls with state waits for form, publish sheet, or login; preserve outer recovery polling and login assertions.
- [ ] Run message-detail, photo-picker, and image-validation helper suites; expect pass.
- [ ] Commit with `git add apps/velowind-app/appium/velowind_appium/modules/message_detail.py apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py && git commit -m "perf(appium): stabilize iOS publish note locators"`.

### Task 5: Trial suite, docs, and verification

**Files:** new `test-suites/ios-publish-note.yaml`, `README.md`

- [ ] Add suite:

```yaml
tests:
  - file: message/test_ios_publish_note.py
    methods:
      - test_user_can_publish_note_for_review
pytest_args:
  - --maxfail=1
```

- [ ] Document `VW_APPIUM_PROFILE=1 pnpm appium:ios:test:suite apps/velowind-app/appium/test-suites/ios-publish-note.yaml`, simulator/device variants, and locator diagnostics/artifact behavior.
- [ ] Run unit regressions for actions, Android actions, session setup, message detail, photo picker, and image validation; run publish-note `--collect-only`.
- [ ] Run simulator validation with `VW_IOS_TARGET=simulator VW_APPIUM_PROFILE=1 VW_APPIUM_AUTO_OPEN_REPORT=false pnpm appium:ios:test:suite apps/velowind-app/appium/test-suites/ios-publish-note.yaml`; record stage durations.
- [ ] Run physical validation with the same command and `VW_IOS_TARGET=device` when WDA/RemoteXPC is available; setup failures are environment-blocked, not business failures.
- [ ] Run `git diff --check` and `git status --short`; preserve pre-existing user changes unstaged.
- [ ] Commit suite/docs with `git add apps/velowind-app/appium/test-suites/ios-publish-note.yaml apps/velowind-app/appium/README.md && git commit -m "docs(appium): add iOS publish note trial suite"`.

