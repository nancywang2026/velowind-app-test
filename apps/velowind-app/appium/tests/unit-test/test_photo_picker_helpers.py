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
        lambda driver, album_name=None, picture_index=1, select_all_from_album=True: calls.append(
            ("choose-photo", album_name, picture_index, select_all_from_album)
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
        ("choose-photo", "长白山", 1, True),
    ]


def test_open_photo_album_goes_back_before_switching_from_other_album(monkeypatch):
    events = []
    titles = iter(["云南洱海", None, None, "长白山", "长白山", "长白山"])

    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(photo_picker, "_tap_photo_picker_back", lambda driver: events.append("back") or True)
    monkeypatch.setattr(photo_picker, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "精选集")
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("tap-album", text)) or text == "长白山")
    monkeypatch.setattr(photo_picker, "_visible_text_present", lambda driver, text: text == "精选集")
    monkeypatch.setattr(photo_picker, "swipe_vertical", lambda driver, direction="up": events.append(("swipe", direction)))
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker.open_photo_album(object(), "长白山") is True
    assert events == [
        "back",
        ("tap-text", "精选集"),
        ("tap-album", "长白山"),
    ]


def test_open_photo_album_waits_for_back_to_leave_current_album(monkeypatch):
    events = []
    titles = iter(["北京", "北京", None, "长白山", "长白山", "长白山", "长白山"])

    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(photo_picker, "_tap_photo_picker_back", lambda driver: events.append("back") or True)
    monkeypatch.setattr(photo_picker, "_photo_picker_collections_visible", lambda driver: False)
    monkeypatch.setattr(photo_picker, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "精选集")
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("tap-album", text)) or text == "长白山")
    monkeypatch.setattr(photo_picker, "_visible_text_present", lambda driver, text: text == "精选集")
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker.open_photo_album(object(), "长白山") is True
    assert events == [
        "back",
        "back",
        ("tap-text", "精选集"),
        ("tap-album", "长白山"),
    ]


def test_open_photo_album_leaves_ios_multi_select_grid_before_selecting_target(monkeypatch):
    events = []
    titles = iter([
        "选择最多9张照片。",
        "北京",
        "北京",
        None,
        "长白山",
        "长白山",
        "长白山",
        "长白山",
    ])

    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(photo_picker, "_tap_photo_picker_back", lambda driver: events.append("back") or True)
    monkeypatch.setattr(photo_picker, "_photo_picker_collections_visible", lambda driver: False)
    monkeypatch.setattr(photo_picker, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "精选集")
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("tap-album", text)) or text == "长白山")
    monkeypatch.setattr(photo_picker, "_visible_text_present", lambda driver, text: text == "精选集")
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker.open_photo_album(object(), "长白山") is True
    assert events == [
        "back",
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


def test_tap_photo_grid_candidate_clicks_ios_photo_and_waits_for_done_enable(monkeypatch):
    events = []
    selection_state = {"selected": False}

    class FakeElement:
        rect = {"x": 0, "y": 141, "width": 133, "height": 134}

        def click(self):
            events.append("click")
            selection_state["selected"] = True

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(photo_picker, "find_photo_grid_candidates", lambda driver: [FakeElement()])
    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'name="完成" label="完成" enabled="true"' if selection_state["selected"] else 'name="完成" label="完成" enabled="false"',
    )

    assert photo_picker.tap_photo_grid_candidate(FakeDriver(), 1) is True
    assert events == ["click"]


def test_tap_photo_grid_candidate_retries_ios_hotspots_until_done_enables(monkeypatch):
    taps = []
    selection_state = {"selected": False}

    class FakeElement:
        rect = {"x": 0, "y": 141, "width": 133, "height": 134}

        def click(self):
            raise photo_picker.WebDriverException()

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            taps.append((script, payload))
            if len(taps) == 2:
                selection_state["selected"] = True

    monkeypatch.setattr(photo_picker, "find_photo_grid_candidates", lambda driver: [FakeElement()])
    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'name="完成" label="完成" enabled="true"' if selection_state["selected"] else 'name="完成" label="完成" enabled="false"',
    )

    assert photo_picker.tap_photo_grid_candidate(FakeDriver(), 1) is True
    assert taps == [
        ("mobile: tap", {"x": 66.5, "y": 208.0}),
        ("mobile: tap", {"x": 46.55, "y": 208.0}),
    ]


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


def test_choose_local_photo_reopens_requested_ios_album_when_title_mismatches(monkeypatch):
    events = []
    titles = iter(["北京", "长白山", "长白山"])

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(photo_picker, "open_photo_album", lambda driver, album_name: True)
    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(photo_picker, "_return_photo_picker_to_collections", lambda driver, current_title: events.append(("back-to-collections", current_title)) or True)
    monkeypatch.setattr(photo_picker, "switch_photo_picker_to_collections", lambda driver, current_title=None: events.append(("switch", current_title)) or True)
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("tap-album", text)) or True)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(photo_picker, "tap_photo_grid_candidate", lambda driver, picture_index: events.append(("tap-photo", picture_index)) or True)
    monkeypatch.setattr(photo_picker, "confirm_note_image_cropper", lambda driver: False)
    monkeypatch.setattr(photo_picker, "confirm_system_photo_picker_selection", lambda driver: events.append("confirm") or True)
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker.choose_local_photo(FakeDriver(), album_name="长白山", select_all_from_album=False) is True
    assert events == [
        ("back-to-collections", "北京"),
        ("switch", None),
        ("tap-album", "长白山"),
        ("tap-photo", 1),
        "confirm",
    ]


def test_choose_local_photo_uses_gallery3d_fallback_on_android(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(photo_picker, "_is_android_gallery3d_picker", lambda driver: True)
    monkeypatch.setattr(
        photo_picker,
        "_choose_local_photo_from_android_gallery3d",
        lambda driver, preferred_album_name=None, picture_index=1: events.append(("gallery3d", preferred_album_name, picture_index)) or True,
    )

    assert photo_picker.choose_local_photo(FakeDriver(), album_name="云南洱海") is True
    assert events == [("gallery3d", "云南洱海", 1)]


def test_android_gallery3d_picker_detects_gallery_package_and_title(monkeypatch):
    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'package="com.android.gallery3d" text="选择照片"',
    )

    assert photo_picker._is_android_gallery3d_picker(FakeDriver()) is True


def test_android_gallery3d_album_index_uses_local_media_dir(monkeypatch, tmp_path):
    (tmp_path / "长白山").mkdir()
    (tmp_path / "云南洱海").mkdir()
    monkeypatch.setenv("VW_ANDROID_MEDIA_DIR", str(tmp_path))

    assert photo_picker._android_gallery3d_album_index("云南洱海") == 0


def test_choose_local_photo_from_android_gallery3d_taps_album_then_photo(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_size(self):
            return {"width": 1000, "height": 2000}

        def execute_script(self, script, payload):
            taps.append((script, payload))

        def find_element(self, by, value):
            raise photo_picker.NoSuchElementException()

    wait_results = iter([False, True])
    monkeypatch.setattr(photo_picker, "_preferred_android_gallery3d_album_name", lambda: "云南洱海")
    monkeypatch.setattr(photo_picker, "_android_gallery3d_album_index", lambda album_name: 1)
    monkeypatch.setattr(photo_picker, "_photo_picker_transition_completed", lambda driver: next(wait_results))
    monkeypatch.setattr(photo_picker, "_cropper_visible", lambda page_source, driver=None, allow_generic_text_fallback=True: False)
    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: "选择照片 云南洱海")
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker._choose_local_photo_from_android_gallery3d(FakeDriver(), preferred_album_name="云南洱海") is True
    assert taps[:2] == [
        ("mobile: tap", {"x": 500.0, "y": 1520.0}),
        ("mobile: tap", {"x": 180.0, "y": 560.0}),
    ]


def test_choose_local_photo_from_android_gallery3d_retries_with_adb_when_photo_tap_does_not_transition(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "udid": "emulator-5554"}

        def get_window_size(self):
            return {"width": 1000, "height": 2000}

        def execute_script(self, script, payload):
            events.append((script, payload))

        def find_element(self, by, value):
            raise photo_picker.NoSuchElementException()

    wait_results = iter([False, True])
    monkeypatch.setattr(photo_picker, "_preferred_android_gallery3d_album_name", lambda: None)
    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: "")
    monkeypatch.setattr(photo_picker, "_cropper_visible", lambda page_source, driver=None, allow_generic_text_fallback=True: False)
    monkeypatch.setattr(photo_picker, "_photo_picker_transition_completed", lambda driver: False)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: next(wait_results))
    monkeypatch.setattr(photo_picker, "_adb_tap_by_ratio", lambda driver, x_ratio, y_ratio, size: events.append(("adb", x_ratio, y_ratio)) or True)
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker._choose_local_photo_from_android_gallery3d(FakeDriver()) is True
    assert events[:2] == [
        ("mobile: tap", {"x": 180.0, "y": 560.0}),
        ("adb", 0.18, 0.28),
    ]


def test_choose_local_photo_from_android_gallery3d_accepts_delayed_return_to_publish_form(monkeypatch):
    events = []
    page_sources = iter([
        "",
        "",
        'text="发布笔记" text="添加标题" resource-id="image"',
    ])

    class FakeDriver:
        capabilities = {"platformName": "Android", "udid": "emulator-5554"}

        def get_window_size(self):
            return {"width": 1000, "height": 2000}

        def execute_script(self, script, payload):
            events.append((script, payload))

        def find_element(self, by, value):
            raise photo_picker.NoSuchElementException()

    monkeypatch.setattr(photo_picker, "_preferred_android_gallery3d_album_name", lambda: None)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: False)
    monkeypatch.setattr(photo_picker, "_cropper_visible", lambda page_source, driver=None, allow_generic_text_fallback=True: False)
    monkeypatch.setattr(photo_picker, "_adb_tap_by_ratio", lambda driver, x_ratio, y_ratio, size: events.append(("adb", x_ratio, y_ratio)) or True)
    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: next(page_sources))
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker._choose_local_photo_from_android_gallery3d(FakeDriver()) is True
    assert events[:2] == [
        ("mobile: tap", {"x": 180.0, "y": 560.0}),
        ("adb", 0.18, 0.28),
    ]


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


def test_photo_picker_transition_accepts_android_publish_form_with_selected_image(monkeypatch):
    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'text="发布笔记" text="添加标题" resource-id="image"',
    )

    assert photo_picker._photo_picker_transition_completed(FakeDriver()) is True


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
            if value in {
                "Add",
                'visible == 1 AND (name IN {"完成", "添加"} OR label IN {"完成", "添加"} OR value IN {"完成", "添加"})',
            }:
                raise photo_picker.NoSuchElementException()
            assert value == '//*[@name="Add" and @enabled="true" and @visible="true"]'
            return FakeElement()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_photo_picker_done_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 364.0, "y": 110.0})]


def test_tap_named_element_center_prefers_visible_ios_match():
    taps = []

    class HiddenElement:
        rect = {"x": 0, "y": 0, "width": 0, "height": 0}

        def click(self):
            raise photo_picker.WebDriverException()

    class VisibleElement:
        rect = {"x": 120, "y": 240, "width": 80, "height": 32}

    class FakeDriver:
        def find_element(self, by, value):
            if value == '//*[@visible="true" and (@name="长白山" or @label="长白山" or @value="长白山")]':
                return VisibleElement()
            if value == '//*[@name="长白山" or @label="长白山" or @value="长白山"]':
                return HiddenElement()
            raise photo_picker.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_named_element_center(FakeDriver(), "长白山") is True
    assert taps == [("mobile: tap", {"x": 160.0, "y": 256.0})]


def test_tap_named_element_center_skips_offscreen_ios_album_card():
    taps = []

    class OffscreenElement:
        rect = {"x": 512, "y": 405, "width": 110, "height": 111}

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def get_window_size(self):
            return {"width": 402, "height": 874}

        def find_element(self, by, value):
            if value == '//*[@visible="true" and (@name="长白山" or @label="长白山" or @value="长白山")]':
                return OffscreenElement()
            raise photo_picker.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_named_element_center(FakeDriver(), "长白山") is False
    assert taps == []


def test_swipe_ios_album_carousel_left_drags_album_shelf():
    events = []

    class FakeDriver:
        def get_window_size(self):
            return {"width": 402, "height": 874}

        def execute_script(self, script, payload):
            events.append((script, payload))

    assert photo_picker._swipe_ios_album_carousel_left(FakeDriver()) is True
    assert events == [
        (
            "mobile: dragFromToForDuration",
            {
                "duration": 0.35,
                "fromX": 345.71999999999997,
                "fromY": 454.48,
                "toX": 64.32000000000001,
                "toY": 454.48,
            },
        )
    ]


def test_tap_photo_picker_done_button_supports_android_google_photos_done(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(
        photo_picker,
        "tap_text_if_present",
        lambda driver, text, timeout: taps.append((text, timeout)) or text == "Done",
    )


def test_tap_cropper_confirm_button_supports_android_text_locator():
    taps = []

    class FakeElement:
        rect = {"x": 738, "y": 2314, "width": 642, "height": 168}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_size(self):
            return {"width": 1440, "height": 2560}

        def find_element(self, by, value):
            if value == '//*[@text="确认裁剪"]/..':
                return FakeElement()
            raise photo_picker.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch = None

    from velowind_appium.modules import photo_picker as module
    original_wait_until = module._wait_until
    original_cropper_exit_confirmed = module._cropper_exit_confirmed
    try:
        module._wait_until = lambda predicate, timeout: True
        module._cropper_exit_confirmed = lambda page_source, driver: True
        assert photo_picker._tap_cropper_confirm_button(FakeDriver()) is True
    finally:
        module._wait_until = original_wait_until
        module._cropper_exit_confirmed = original_cropper_exit_confirmed
    assert taps == [("mobile: tap", {"x": 1059.0, "y": 2398.0})]


def test_tap_cropper_confirm_button_uses_android_hotspots_after_center_tap(monkeypatch):
    taps = []
    wait_results = iter([False, True])

    class FakeElement:
        rect = {"x": 738, "y": 2314, "width": 642, "height": 168}

        def click(self):
            raise photo_picker.WebDriverException()

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            if value == '//*[@text="确认裁剪"]/..':
                return FakeElement()
            raise photo_picker.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: "裁剪图片 确认裁剪")
    monkeypatch.setattr(photo_picker, "_android_publish_form_visible", lambda page_source: False)
    monkeypatch.setattr(photo_picker, "_cropper_visible", lambda page_source, driver=None, allow_generic_text_fallback=True: True)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: next(wait_results))

    assert photo_picker._tap_cropper_confirm_button(FakeDriver()) is True
    assert taps == [
        ("mobile: tap", {"x": 1059.0, "y": 2398.0}),
        ("mobile: tap", {"x": 1264.44, "y": 2398.0}),
    ]


def test_confirm_note_image_cropper_accepts_android_publish_form(monkeypatch):
    page_sources = iter([
        "裁剪图片 确认裁剪",
        'text="发布笔记" text="添加标题" resource-id="image"',
    ])
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monotonic_values = iter([0, 0, 0.2, 0.4, 0.6, 1.0])
    monkeypatch.setattr(photo_picker.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: next(page_sources))
    monkeypatch.setattr(photo_picker, "_cropper_visible", lambda page_source, driver=None, allow_generic_text_fallback=True: "裁剪图片" in page_source)
    monkeypatch.setattr(photo_picker, "_tap_cropper_confirm_button", lambda driver: taps.append("tap") or True)

    assert photo_picker.confirm_note_image_cropper(FakeDriver(), timeout=5) is True
    assert taps == ["tap"]


def test_tap_android_cropper_confirm_fallbacks_uses_adb_after_appium_tap(monkeypatch):
    taps = []
    adb_taps = []
    wait_results = iter([False, True])

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "127.0.0.1:16385"}

    monkeypatch.setattr(
        photo_picker,
        "_tap_by_ratio",
        lambda driver, x_ratio, y_ratio, size=None: taps.append((x_ratio, y_ratio)) or True,
    )
    monkeypatch.setattr(
        photo_picker,
        "_adb_tap_by_ratio",
        lambda driver, x_ratio, y_ratio, size: adb_taps.append((x_ratio, y_ratio)) or True,
    )
    monkeypatch.setattr(photo_picker, "_safe_page_source", lambda driver: "裁剪图片 确认裁剪")
    monkeypatch.setattr(photo_picker, "_android_publish_form_visible", lambda page_source: False)
    monkeypatch.setattr(photo_picker, "_cropper_visible", lambda page_source, driver=None, allow_generic_text_fallback=True: True)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: next(wait_results))

    assert photo_picker._tap_android_cropper_confirm_fallbacks(
        FakeDriver(),
        size={"width": 1440, "height": 2560},
        is_android=True,
    ) is True
    assert taps == [(0.735, 0.9375)]
    assert adb_taps == [(0.735, 0.9375)]
