# iOS Note Location Keyboard Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent keyboard dismissal after note topic entry from reopening an image cropper, then continue into the existing location picker flow.

**Architecture:** Keep the change inside the iOS note publishing helper. Replace the unsafe editor-dismiss coordinate tap with a keyboard `完成`-first strategy and add an explicit cropper-state guard before location selection; leave photo selection and location result selection unchanged.

**Tech Stack:** Python 3, pytest, Appium Python Client

---

### Task 1: Lock the keyboard-dismiss regression

**Files:**

- Modify: `apps/velowind-app/appium/tests/test_message_detail_helpers.py`
- Modify: `apps/velowind-app/appium/velowind_appium/modules/message_detail.py`

- [ ] **Step 1: Write the failing tests**

Add tests that call `_dismiss_editor_keyboard()` and assert that `完成` is tried
before native keyboard dismissal and that no `mobile: tap` coordinate event is
emitted after dismissal. Add a location preparation test whose page source exposes
a visible cropper and assert that it fails before any swipe or location tap.

```python
def test_dismiss_editor_keyboard_prefers_done_without_coordinate_tap(monkeypatch):
    events = []
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        message_detail,
        "tap_text_if_present",
        lambda driver, text, timeout=1: events.append(("tap-text", text)) or text == "完成",
    )

    class FakeDriver:
        def hide_keyboard(self, **kwargs):
            events.append(("hide-keyboard", kwargs))

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))

    message_detail._dismiss_editor_keyboard(FakeDriver())

    assert events == [("tap-text", "完成")]


def test_prepare_note_location_section_rejects_visible_cropper(monkeypatch):
    monkeypatch.setattr(message_detail, "_dismiss_editor_keyboard", lambda driver: None)
    monkeypatch.setattr(
        message_detail,
        "_safe_page_source",
        lambda driver: 'name="裁剪图片" label="裁剪图片" enabled="true" visible="true"',
    )

    with pytest.raises(AssertionError, match="cropper"):
        message_detail._prepare_note_location_section(object())
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
/Users/test/Documents/velowind-app-dev-test/.venv/bin/python -m pytest \
  tests/test_message_detail_helpers.py \
  -k 'dismiss_editor_keyboard or prepare_note_location_section' -q
```

Expected: the new tests fail because the current helper still taps the thumbnail
coordinate and does not reject the cropper state.

- [ ] **Step 3: Implement the minimal fix**

Update `_dismiss_editor_keyboard()` to tap `完成` first, then use Appium keyboard
dismissal only as a fallback, without calling `_tap_outside_editor()`. Update
`_prepare_note_location_section()` to raise a state-specific assertion when
`_cropper_visible()` is true.

```python
def _dismiss_editor_keyboard(driver: WebDriver) -> None:
    if tap_text_if_present(driver, "完成", timeout=1):
        time.sleep(0.2)
        return
    for kwargs in [{}, {"key_name": "Done"}, {"key_name": "Return"}]:
        try:
            driver.hide_keyboard(**kwargs)
            break
        except WebDriverException:
            continue
    time.sleep(0.2)


def _prepare_note_location_section(driver: WebDriver) -> None:
    _dismiss_editor_keyboard(driver)
    page_source = _safe_page_source(driver)
    if _cropper_visible(page_source):
        raise AssertionError("Unable to prepare note location while the image cropper is visible")
    if _location_section_visible(page_source):
        return
    for _ in range(3):
        _dismiss_editor_keyboard(driver)
        page_source = _safe_page_source(driver)
        if _cropper_visible(page_source):
            raise AssertionError("Unable to prepare note location while the image cropper is visible")
        if _location_section_visible(page_source):
            return
        try:
            swipe_vertical(driver, direction="up")
        except WebDriverException:
            pass
        time.sleep(0.3)
        page_source = _safe_page_source(driver)
        if _cropper_visible(page_source):
            raise AssertionError("Unable to prepare note location while the image cropper is visible")
        if _location_section_visible(page_source):
            return
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
/Users/test/Documents/velowind-app-dev-test/.venv/bin/python -m pytest \
  tests/test_message_detail_helpers.py \
  -k 'dismiss_editor_keyboard or prepare_note_location_section or fill_note_location or choose_note_location' -q
```

Expected: all selected tests pass.

### Task 2: Verify the note helper integration surface

**Files:**

- Verify: `apps/velowind-app/appium/tests/test_message_detail_helpers.py`
- Verify: `apps/velowind-app/appium/velowind_appium/modules/message_detail.py`

- [ ] **Step 1: Run the relevant note form and location tests**

Run:

```bash
/Users/test/Documents/velowind-app-dev-test/.venv/bin/python -m pytest \
  tests/test_message_detail_helpers.py \
  -k 'fill_message_note_form or append_note_topics or dismiss_editor_keyboard or prepare_note_location_section or fill_note_location or choose_note_location or location_picker' -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Review the scoped diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only the design, plan, note helper, and its helper
tests are changed.
