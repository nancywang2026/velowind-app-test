# iOS Search Note Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split search, comment, and like/favorite coverage into focused full-regression cases, speed up search-result opening, and make centralized teardown reliably leave note detail.

**Architecture:** Keep the search-only flow in its existing file and place the two home-feed interaction cases together in a new file. Extend the shared note-card picker with a one-based ordinal API and use the existing search-specific opener. Fix the centralized top-left recovery coordinate while preserving home detection and system-back fallback.

**Tech Stack:** Python 3.9, pytest, Appium Python client, Selenium, Allure.

---

### Task 1: Indexed home-feed card selection

**Files:**
- Modify: `apps/velowind-app/appium/velowind_appium/modules/note_card_picker.py`
- Create: `apps/velowind-app/appium/tests/test_note_card_picker.py`

- [ ] Add a failing unit test proving ordinal `2` selects the second unique eligible card while ignoring duplicated ancestors.
- [ ] Run the targeted unit test and confirm it fails because the picker has no ordinal contract.
- [ ] Add a one-based `ordinal` parameter with validation and select the requested unique card.
- [ ] Run the picker helper suite and confirm it passes.

### Task 2: Reliable note-detail teardown

**Files:**
- Modify: `apps/velowind-app/appium/velowind_appium/session.py`
- Test: `apps/velowind-app/appium/tests/test_session_setup.py`

- [ ] Update the existing coordinate regression test to expect 5% screen width (`x=20` for a 402-point screen).
- [ ] Run the targeted test and confirm it fails with the current `x=40` tap.
- [ ] Change `_tap_top_back_by_coordinate` to use 5% width and retain 10% height.
- [ ] Run the session and home-feed helper suites.

### Task 3: Focus the search case

**Files:**
- Modify: `apps/velowind-app/appium/tests/message/test_ios_search_note.py`

- [ ] Replace the local generic-card opener with `open_first_note_search_result`.
- [ ] Comment out like, favorite, and comment actions plus interaction assertions, keeping moved coverage explicit.
- [ ] Collect the search test and confirm pytest still discovers exactly one search case.

### Task 4: Add independent home-note interaction cases

**Files:**
- Create: `apps/velowind-app/appium/tests/message/test_ios_home_note_interactions.py`

- [ ] Add a shared helper that prepares the home feed, opens a card by one-based ordinal, and verifies detail visibility.
- [ ] Add `test_user_can_comment_on_first_home_note`, using ordinal `1` and `submit_message_comment`.
- [ ] Add `test_user_can_like_and_favorite_second_home_note`, using ordinal `2`, `like_note`, and `favorite_note`, with both change assertions.
- [ ] Collect full tests and confirm both new cases are present and smoke cases remain excluded by the full command.

### Task 5: Verify behavior and performance

**Files:**
- Verify all files above.

- [ ] Run relevant unit suites for picker, session, home feed, and message detail.
- [ ] Run the search case on the real device and record runtime, including teardown completion.
- [ ] Run the two new home-note cases sequentially and record individual results.
- [ ] Run `git diff --check` and review the scoped diff without reverting unrelated user changes.
