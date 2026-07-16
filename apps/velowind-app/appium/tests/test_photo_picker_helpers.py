from velowind_appium.modules import photo_picker


def test_dismiss_photo_permission_alerts_accepts_android_english_allow_all(monkeypatch):
    taps = []

    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: "Allow 寻风集 to access photos and videos on this device? Allow limited access Allow all Don’t allow",
    )
    monkeypatch.setattr(
        photo_picker,
        "tap_text_if_present",
        lambda driver, text, timeout: taps.append((text, timeout)) or text == "Allow all",
    )

    photo_picker.dismiss_photo_permission_alerts(object())

    assert ("Allow all", 0.5) in taps


def test_choose_photo_from_library_retries_sheet_option_before_selecting_album(monkeypatch):
    calls = []
    visibility_checks = iter([False, True])

    monkeypatch.setattr(photo_picker, "choose_photo_library_source", lambda driver: calls.append("choose-source") or True)
    monkeypatch.setattr(photo_picker, "dismiss_photo_permission_alerts", lambda driver: calls.append("dismiss-alerts"))
    monkeypatch.setattr(photo_picker, "photo_library_visible", lambda driver, timeout=5: calls.append(("visible", timeout)) or next(visibility_checks))
    monkeypatch.setattr(
        photo_picker,
        "choose_local_photo",
        lambda driver, album_name=None, select_all_from_album=True: calls.append(
            ("choose-photo", album_name, select_all_from_album)
        )
        or True,
    )
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
        ("choose-photo", "长白山", True),
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


def test_open_photo_album_enters_android_google_photos_device_folder(monkeypatch):
    taps = []

    class FakeElement:
        rect = {"x": 189, "y": 493, "width": 168, "height": 66}

    class FakeDriver:
        capabilities = {"platformName": "Android"}
        page_source = "Select a photo Device folders 云南洱海 1 item"

        def find_element(self, by, value):
            if value == '//*[@text="云南洱海"]':
                return FakeElement()
            raise photo_picker.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(photo_picker, "find_photo_grid_candidates", lambda driver: [object()])
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())

    assert photo_picker.open_photo_album(FakeDriver(), "云南洱海") is True
    assert taps == [("mobile: tap", {"x": 273.0, "y": 526.0})]


def test_photo_library_visible_does_not_accept_generic_photo_text(monkeypatch):
    monkeypatch.setattr(photo_picker.time, "monotonic", iter([0, 1]).__next__)
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    class FakeDriver:
        page_source = "发布笔记 选择照片"

        def find_element(self, by, value):
            raise photo_picker.NoSuchElementException()

    assert photo_picker.photo_library_visible(FakeDriver(), timeout=1) is False


def test_photo_library_visible_accepts_android_google_photos_picker(monkeypatch):
    monkeypatch.setattr(photo_picker.time, "monotonic", iter([0, 0, 2]).__next__)
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    class FakeDriver:
        page_source = "Select photos Device folders 云南洱海 1 item"

        def find_element(self, by, value):
            raise photo_picker.NoSuchElementException()

    assert photo_picker.photo_library_visible(FakeDriver(), timeout=1) is True


def test_find_photo_grid_candidates_supports_android_google_photos():
    class FakeElement:
        rect = {"x": 0, "y": 493, "width": 264, "height": 264}

    candidate = FakeElement()

    class FakeDriver:
        def find_elements(self, by, value):
            if value == '//android.widget.ImageView[@clickable="true" and contains(@content-desc, "Photo")]':
                return [candidate]
            return []

    assert photo_picker.find_photo_grid_candidates(FakeDriver()) == [candidate]


def test_choose_album_photo_confirms_android_system_selection_before_cropper(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(photo_picker, "open_photo_album", lambda driver, album_name: True)
    monkeypatch.setattr(photo_picker, "select_all_album_photos", lambda driver: True)
    monkeypatch.setattr(
        photo_picker,
        "confirm_note_image_cropper",
        lambda driver: events.append("cropper") or False,
    )
    monkeypatch.setattr(
        photo_picker,
        "confirm_system_photo_picker_selection",
        lambda driver: events.append("system") or True,
    )

    assert photo_picker.choose_local_photo(FakeDriver(), album_name="云南洱海") is True
    assert events == ["system"]


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


def test_photo_picker_transition_waits_while_android_google_photos_is_visible(monkeypatch):
    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: "Select a photo Device folders Done Photo taken on May 15",
    )

    assert photo_picker._photo_picker_transition_completed(object()) is False


def test_photo_picker_transition_waits_while_android_google_photos_folder_is_exiting(monkeypatch):
    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'package="com.google.android.apps.photos" pane-title="云南洱海"',
    )

    assert photo_picker._photo_picker_transition_completed(object()) is False


def test_photo_picker_transition_waits_for_cropper_from_publish_form(monkeypatch):
    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: "发布笔记 标题 正文",
    )

    assert photo_picker._photo_picker_transition_completed(object()) is False


def test_photo_picker_transition_confirms_new_cropper_despite_prior_upload(monkeypatch):
    driver = type("FakeDriver", (), {"_cropper_confirmed_once": True})()
    confirmations = []

    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: "裁剪图片 确认裁剪")
    monkeypatch.setattr(
        photo_picker,
        "confirm_note_image_cropper",
        lambda driver, timeout=5: confirmations.append(driver) or True,
    )

    assert photo_picker._photo_picker_transition_completed(driver) is True
    assert confirmations == [driver]


def test_photo_picker_transition_does_not_accept_empty_page_source(monkeypatch):
    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: "")

    assert photo_picker._photo_picker_transition_completed(object()) is False


def test_tap_photo_picker_done_button_taps_visible_enabled_add_center():
    taps = []

    class FakeElement:
        rect = {"x": 346, "y": 92, "width": 36, "height": 36}

    class FakeDriver:
        def find_element(self, by, value):
            if value in {"Add", 'name IN {"完成", "添加"} OR label IN {"完成", "添加"} OR value IN {"完成", "添加"}'}:
                raise photo_picker.NoSuchElementException()
            assert value == '//*[@name="Add" and @enabled="true" and @visible="true"]'
            return FakeElement()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_photo_picker_done_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 364.0, "y": 110.0})]


def test_tap_photo_picker_done_button_supports_android_google_photos_done(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(
        photo_picker,
        "tap_text_if_present",
        lambda driver, text, timeout: taps.append((text, timeout)) or text == "Done",
    )

    assert photo_picker._tap_photo_picker_done_button(FakeDriver()) is True
    assert taps == [("Done", 1)]
