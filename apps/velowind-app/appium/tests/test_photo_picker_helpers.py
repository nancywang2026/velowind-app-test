from velowind_appium.modules import photo_picker


def test_choose_photo_from_library_retries_sheet_option_before_selecting_album(monkeypatch):
    calls = []
    visibility_checks = iter([False, True])

    monkeypatch.setattr(photo_picker, "choose_photo_library_source", lambda driver: calls.append("choose-source") or True)
    monkeypatch.setattr(photo_picker, "dismiss_photo_permission_alerts", lambda driver: calls.append("dismiss-alerts"))
    monkeypatch.setattr(photo_picker, "photo_library_visible", lambda driver, timeout=5: calls.append(("visible", timeout)) or next(visibility_checks))
    monkeypatch.setattr(photo_picker, "choose_local_photo", lambda driver, album_name=None: calls.append(("choose-photo", album_name)) or True)
    monkeypatch.setattr(photo_picker, "_choose_first_option", lambda driver, preferred_texts: False)

    assert photo_picker.choose_photo_from_library(
        object(),
        album_name="长白山",
        retry_sheet_option=lambda driver: calls.append("retry-sheet") or True,
    ) is True

    assert calls == [
        "choose-source",
        "dismiss-alerts",
        ("visible", 5),
        "retry-sheet",
        "dismiss-alerts",
        ("visible", 5),
        ("choose-photo", "长白山"),
    ]


def test_open_photo_album_goes_back_before_switching_from_other_album(monkeypatch):
    events = []
    titles = iter(["云南洱海", None, None, "长白山"])

    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(photo_picker, "_tap_photo_picker_back", lambda driver: events.append("back") or True)
    monkeypatch.setattr(photo_picker, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "精选集")
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("tap-album", text)) or text == "长白山")
    monkeypatch.setattr(photo_picker, "swipe_vertical", lambda driver, direction="up": events.append(("swipe", direction)))
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker.open_photo_album(object(), "长白山") is True
    assert events == [
        "back",
        ("tap-text", "精选集"),
        ("tap-album", "长白山"),
    ]


def test_photo_library_visible_does_not_accept_generic_photo_text(monkeypatch):
    monkeypatch.setattr(photo_picker.time, "monotonic", iter([0, 1]).__next__)
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    class FakeDriver:
        page_source = "发布笔记 选择照片"

        def find_element(self, by, value):
            raise photo_picker.NoSuchElementException()

    assert photo_picker.photo_library_visible(FakeDriver(), timeout=1) is False


def test_confirm_system_photo_picker_selection_retries_when_done_tap_does_not_exit(monkeypatch):
    taps = []
    wait_results = iter([False, True])

    monkeypatch.setattr(photo_picker.time, "monotonic", iter([0, 1, 2]).__next__)
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: "照片")
    monkeypatch.setattr(photo_picker, "_tap_photo_picker_done_button", lambda driver: taps.append("done") or True)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: next(wait_results))

    assert photo_picker.confirm_system_photo_picker_selection(object(), timeout=10) is True
    assert taps == ["done", "done"]


def test_tap_photo_picker_done_button_taps_visible_enabled_add_center():
    taps = []

    class FakeElement:
        rect = {"x": 346, "y": 92, "width": 36, "height": 36}

    class FakeDriver:
        def find_element(self, by, value):
            assert value == '//*[@name="Add" and @enabled="true" and @visible="true"]'
            return FakeElement()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_photo_picker_done_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 364.0, "y": 110.0})]
