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


def test_choose_photo_from_library_fallback_retries_without_album_name(monkeypatch):
    calls = []

    monkeypatch.setattr(photo_picker, "choose_photo_library_source", lambda driver: calls.append("choose-source") or True)
    monkeypatch.setattr(photo_picker, "dismiss_photo_permission_alerts", lambda driver: calls.append("dismiss-alerts"))
    monkeypatch.setattr(photo_picker, "photo_library_visible", lambda driver, timeout=5: calls.append(("visible", timeout)) or True)
    monkeypatch.setattr(
        photo_picker,
        "choose_local_photo",
        lambda driver, album_name=None, picture_index=1, select_all_from_album=True: calls.append(
            ("choose-photo", album_name, picture_index, select_all_from_album)
        )
        or (album_name is None),
    )
    monkeypatch.setattr(photo_picker, "_choose_first_option", lambda driver, preferred_texts: calls.append(("fallback-option", tuple(preferred_texts))) or True)

    assert photo_picker.choose_photo_from_library(object(), album_name="图片") is True
    assert calls == [
        "choose-source",
        "dismiss-alerts",
        ("visible", 5),
        ("choose-photo", "图片", 1, True),
        ("fallback-option", ("最近项目", "照片图库", "照片", "所有照片")),
        ("choose-photo", None, 1, True),
    ]


def test_photo_library_sheet_fallback_does_not_tap_xiaomi_quicksearch(monkeypatch):
    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}
        page_source = 'package="com.android.quicksearchbox" text="应用推荐"'

        def get_window_size(self):
            raise AssertionError("quicksearch search bar must not be tapped")

    assert photo_picker._tap_photo_library_sheet_option(FakeDriver()) is False


def test_tap_photo_library_sheet_option_uses_row_center(monkeypatch):
    taps = []

    class FakeDriver:
        def get_window_size(self):
            return {"width": 440, "height": 956}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_photo_library_sheet_option(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 220.0, "y": 889.08})]


def test_tap_named_element_center_supports_android_content_desc():
    taps = []

    class FakeElement:
        rect = {"x": 63, "y": 1698, "width": 359, "height": 487}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            if value == '//*[@content-desc="其他相册"]':
                return FakeElement()
            raise photo_picker.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_named_element_center(FakeDriver(), "其他相册") is True
    assert taps == [("mobile: tap", {"x": 242.5, "y": 1941.5})]


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


def test_open_photo_album_taps_ios_target_album_from_source_before_xpath(monkeypatch):
    taps = []
    titles = iter([None, "图片", "图片"])

    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = """
        <AppiumAUT>
          <XCUIElementTypeStaticText visible="true" enabled="true" name="精选集" x="80" y="820" width="96" height="32" />
          <XCUIElementTypeCell visible="true" enabled="true" name="图片" x="16" y="330" width="110" height="120" />
        </AppiumAUT>
        """

        def get_window_size(self):
            return {"width": 402, "height": 874}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(photo_picker, "_tap_texts_by_predicate", lambda driver, texts: False)
    monkeypatch.setattr(photo_picker, "_tap_ios_text_from_source", lambda driver, text: text == "精选集")
    monkeypatch.setattr(photo_picker, "_photo_picker_collections_visible", lambda driver: True)
    monkeypatch.setattr(
        photo_picker,
        "_tap_named_element_center",
        lambda driver, text: (_ for _ in ()).throw(AssertionError("target album should use XML rect before XPath")),
    )

    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())

    assert photo_picker.open_photo_album(FakeDriver(), "图片") is True
    assert taps == [("mobile: tap", {"x": 71.0, "y": 390.0})]


def test_open_photo_album_uses_source_before_predicate_for_numeric_ios_album_name(monkeypatch):
    events = []
    titles = iter([None, None, "0424", "0424"])

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(photo_picker, "_tap_texts_by_predicate", lambda driver, texts: events.append(("predicate", texts)) or True)
    monkeypatch.setattr(photo_picker, "_tap_ios_text_from_source", lambda driver, text: events.append(("source", text)) or text == "精选集")
    monkeypatch.setattr(photo_picker, "_tap_ios_named_element_from_source", lambda driver, text: events.append(("source-album", text)) or text == "0424")
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("center", text)) or False)
    monkeypatch.setattr(photo_picker, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "精选集")
    monkeypatch.setattr(photo_picker, "_photo_picker_collections_visible", lambda driver: True)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())

    assert photo_picker.open_photo_album(FakeDriver(), "0424") is True
    assert events == [("source", "精选集"), ("source-album", "0424")]


def test_open_photo_album_prefers_exact_ios_button_for_numeric_album_name(monkeypatch):
    events = []
    titles = iter([None, "0424", "0424"])

    class FakeElement:
        def click(self):
            events.append("button-click")

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_element(self, by, value):
            if by == photo_picker.AppiumBy.XPATH and "XCUIElementTypeButton" in value and "0424" in value:
                return FakeElement()
            raise photo_picker.NoSuchElementException()

    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(
        photo_picker,
        "_tap_ios_text_from_source",
        lambda driver, text: events.append(("source", text)) or text == "精选集",
    )
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("center", text)) or False)
    monkeypatch.setattr(photo_picker, "_tap_texts_by_predicate", lambda driver, texts: events.append(("predicate", texts)) or False)
    monkeypatch.setattr(photo_picker, "_tap_text_or_contains", lambda driver, text: False)
    monkeypatch.setattr(photo_picker, "_photo_picker_collections_visible", lambda driver: True)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())

    assert photo_picker.open_photo_album(FakeDriver(), "0424") is True
    assert events == [("source", "精选集"), "button-click"]


def test_choose_video_from_library_selects_first_video_without_collections(monkeypatch):
    calls = []
    monkeypatch.setattr(photo_picker, "choose_photo_library_source", lambda driver: calls.append("source") or True)
    monkeypatch.setattr(photo_picker, "dismiss_photo_permission_alerts", lambda driver: calls.append("dismiss"))
    monkeypatch.setattr(photo_picker, "photo_library_visible", lambda driver, timeout=5: calls.append("visible") or True)
    monkeypatch.setattr(photo_picker, "_select_ios_video_filter", lambda driver: calls.append("video-filter") or True)
    monkeypatch.setattr(photo_picker, "tap_photo_grid_candidate", lambda driver, index: calls.append(("video", index)) or True)
    monkeypatch.setattr(photo_picker, "_confirm_video_picker_selection", lambda driver: calls.append("confirm") or True)

    assert photo_picker.choose_video_from_library(object()) is True
    assert calls == ["visible", "dismiss", "video-filter", ("video", 1), "confirm"]


def test_choose_video_from_library_opens_album_before_selecting_video(monkeypatch):
    calls = []

    monkeypatch.setattr(photo_picker, "choose_photo_library_source", lambda driver: calls.append("source") or True)
    monkeypatch.setattr(photo_picker, "dismiss_photo_permission_alerts", lambda driver: calls.append("dismiss"))
    monkeypatch.setattr(photo_picker, "photo_library_visible", lambda driver, timeout=5: calls.append("visible") or True)
    monkeypatch.setattr(photo_picker, "open_photo_album", lambda driver, album_name: calls.append(("open-album", album_name)) or True)
    monkeypatch.setattr(photo_picker, "_ensure_ios_photo_album_active", lambda driver, album_name: calls.append(("ensure-album", album_name)) or True)
    monkeypatch.setattr(photo_picker, "_tap_album_ios_video_candidate", lambda driver, video_index=1: calls.append(("video", video_index)) or True)
    monkeypatch.setattr(photo_picker, "_confirm_video_picker_selection", lambda driver: calls.append("confirm") or True)

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    assert photo_picker.choose_video_from_library(FakeDriver(), album_name="0424", video_index=10) is True
    assert calls == ["visible", "dismiss", ("open-album", "0424"), ("ensure-album", "0424"), ("video", 10), "confirm"]


def test_tap_first_ios_video_candidate_uses_single_image_query(monkeypatch):
    calls = []

    class FakeElement:
        rect = {"x": 12, "y": 160, "width": 190, "height": 190}

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, value):
            calls.append((by, value))
            return [FakeElement()]

        def execute_script(self, script, payload):
            calls.append((script, payload))

    monkeypatch.setattr(photo_picker, "_wait_for_ios_video_preview", lambda driver, timeout: True)

    assert photo_picker._tap_first_ios_video_candidate(FakeDriver()) is True
    assert len([item for item in calls if item[0] == photo_picker.AppiumBy.XPATH]) == 1


def test_confirm_video_picker_confirms_immediately_when_preview_action_is_ready(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: True)
    monkeypatch.setattr(photo_picker, "_visible_text_present", lambda driver, text: text in {"预览视频", "确认"})

    assert photo_picker._confirm_video_picker_selection(FakeDriver()) is True
    assert events == [("mobile: tap", {"x": 298, "y": 806})]


def test_confirm_video_picker_does_not_tap_when_preview_is_not_visible(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(photo_picker, "_visible_text_present", lambda driver, text: False)

    assert photo_picker._confirm_video_picker_selection(FakeDriver()) is False
    assert events == []


def test_tap_ios_text_from_source_uses_visible_rect():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = """
        <AppiumAUT>
          <XCUIElementTypeStaticText visible="true" enabled="true" name="精选集" x="80" y="820" width="96" height="32" />
        </AppiumAUT>
        """

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert photo_picker._tap_ios_text_from_source(FakeDriver(), "精选集") is True
    assert taps == [("mobile: tap", {"x": 128, "y": 836})]


def test_switch_photo_picker_to_collections_uses_ios_source_fast_path(monkeypatch):
    taps = []
    state = {"collections": False}

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        @property
        def page_source(self):
            if state["collections"]:
                return """
                <AppiumAUT>
                  <XCUIElementTypeNavigationBar visible="true">
                    <XCUIElementTypeStaticText visible="true" enabled="true" name="精选集" />
                  </XCUIElementTypeNavigationBar>
                </AppiumAUT>
                """
            return """
            <AppiumAUT>
              <XCUIElementTypeStaticText visible="true" enabled="true" name="精选集" x="80" y="820" width="96" height="32" />
            </AppiumAUT>
            """

        def execute_script(self, script, payload):
            taps.append((script, payload))
            state["collections"] = True

    assert photo_picker.switch_photo_picker_to_collections(FakeDriver(), current_title="照片") is True
    assert taps == [("mobile: tap", {"x": 128, "y": 836})]


def test_switch_photo_picker_to_collections_uses_short_wait(monkeypatch):
    waits = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(photo_picker, "_tap_ios_text_from_source", lambda driver, text: True)
    monkeypatch.setattr(photo_picker, "_tap_text_or_contains", lambda driver, text: False)
    monkeypatch.setattr(photo_picker, "_photo_picker_collections_visible", lambda driver: True)
    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: "精选集")
    monkeypatch.setattr(photo_picker, "_visible_text_present", lambda driver, text: False)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: waits.append(timeout) or predicate())

    assert photo_picker.switch_photo_picker_to_collections(FakeDriver(), current_title="照片") is True
    assert waits == [1]


def test_return_photo_picker_to_collections_uses_short_wait(monkeypatch):
    waits = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(photo_picker, "_photo_picker_collections_visible", lambda driver: False)
    monkeypatch.setattr(photo_picker, "_tap_photo_picker_back", lambda driver: True)
    monkeypatch.setattr(photo_picker, "photo_album_title", lambda driver: "照片")
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: waits.append(timeout) or True)

    assert photo_picker._return_photo_picker_to_collections(FakeDriver(), current_title="照片") is True
    assert waits == [1]


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


def test_find_photo_grid_candidates_supports_miui_gallery_picker():
    class FakeElement:
        rect = {"x": 0, "y": 639, "width": 317, "height": 317}

    candidate = FakeElement()

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}
        page_source = 'package="com.miui.gallery" resource-id="com.miui.gallery:id/micro_thumb"'

        def find_elements(self, by, value):
            if value == '//android.widget.ImageView[@resource-id="com.miui.gallery:id/micro_thumb"]':
                return [candidate]
            return []

    assert photo_picker.find_photo_grid_candidates(FakeDriver()) == [candidate]


def test_find_photo_grid_candidates_supports_ios_cells():
    class FakeElement:
        rect = {"x": 18, "y": 148, "width": 72, "height": 72}

    candidate = FakeElement()

    class FakeDriver:
        def find_elements(self, by, value):
            if value == "//XCUIElementTypeCell":
                return [candidate]
            return []

    assert photo_picker.find_photo_grid_candidates(FakeDriver()) == [candidate]


def test_find_photo_grid_selection_badges_supports_miui_gallery_checkboxes():
    class FakeElement:
        rect = {"x": 236, "y": 875, "width": 70, "height": 70}

    badge = FakeElement()

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}
        page_source = 'package="com.miui.gallery" resource-id="com.miui.gallery:id/micro_thumb"'

        def find_elements(self, by, value):
            if value == '//android.widget.CheckBox[@resource-id="android:id/checkbox" and @clickable="true"]':
                return [badge]
            return []

    assert photo_picker.find_photo_grid_selection_badges(FakeDriver()) == [badge]


def test_miui_gallery_picker_is_treated_as_android_photo_picker(monkeypatch):
    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}

    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'package="com.miui.gallery" resource-id="com.miui.gallery:id/micro_thumb" text="请选择项目"',
    )

    assert photo_picker._is_android_gallery3d_picker(FakeDriver()) is True


def test_miui_gallery_picker_is_ignored_on_android_emulator(monkeypatch):
    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "emulator-5554", "appium:deviceName": "Android Emulator"}

    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'package="com.miui.gallery" resource-id="com.miui.gallery:id/micro_thumb" text="请选择项目"',
    )

    assert photo_picker._is_android_gallery3d_picker(FakeDriver()) is False


def test_choose_local_photo_from_miui_gallery_opens_target_album_before_selecting(monkeypatch):
    events = []

    class FakeBadge:
        rect = {"x": 236, "y": 875, "width": 70, "height": 70}

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}

        def get_window_size(self):
            return {"width": 1280, "height": 2772}

    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'package="com.miui.gallery" resource-id="com.miui.gallery:id/micro_thumb" text="请选择项目"',
    )
    monkeypatch.setattr(photo_picker, "_open_miui_gallery_target_album", lambda driver, album_name: events.append(("album", album_name)) or True)
    monkeypatch.setattr(photo_picker, "find_photo_grid_selection_badges", lambda driver: [FakeBadge()])
    monkeypatch.setattr(photo_picker, "_tap_rect_center", lambda driver, rect: events.append(("badge", rect)) or True)
    monkeypatch.setattr(photo_picker, "_tap_photo_picker_done_button", lambda driver: events.append("confirm") or True)
    monkeypatch.setattr(photo_picker, "_photo_picker_transition_completed", lambda driver: True)
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker._choose_local_photo_from_android_gallery3d(FakeDriver(), preferred_album_name="长白山") is True
    assert events == [
        ("album", "长白山"),
        ("badge", {"x": 236.0, "y": 875.0, "width": 70.0, "height": 70.0}),
        "confirm",
    ]


def test_open_miui_gallery_target_album_uses_other_albums_fallback(monkeypatch):
    events = []
    visible_sources = [
        'package="com.miui.gallery" text="照片" text="影集" text="其他相册"',
        'package="com.miui.gallery" text="照片" text="影集" text="其他相册"',
        'package="com.miui.gallery" text="影集" text="其他相册"',
        'package="com.miui.gallery" text="其他相册" text="长白山"',
    ]
    source_index = {"value": 0}

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}

    def fake_page_source(driver):
        index = min(source_index["value"], len(visible_sources) - 1)
        source_index["value"] += 1
        return visible_sources[index]

    monkeypatch.setattr(photo_picker, "_safe_page_source", fake_page_source)
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("tap", text)) or text in {"影集", "其他相册", "长白山"})
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker._open_miui_gallery_target_album(FakeDriver(), "长白山") is True
    assert events == [
        ("tap", "影集"),
        ("tap", "其他相册"),
        ("tap", "长白山"),
    ]


def test_open_miui_gallery_target_album_accepts_map_album_prompt(monkeypatch):
    events = []
    page_sources = [
        'package="com.miui.gallery" text="地图相册服务" text="同意"',
        'package="com.miui.gallery" text="照片" text="影集" text="长白山"',
        'package="com.miui.gallery" text="影集" text="长白山"',
    ]
    source_index = {"value": 0}

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}

    def fake_page_source(driver):
        index = min(source_index["value"], len(page_sources) - 1)
        source_index["value"] += 1
        return page_sources[index]

    monkeypatch.setattr(photo_picker, "_safe_page_source", fake_page_source)
    monkeypatch.setattr(photo_picker, "_tap_named_element_center", lambda driver, text: events.append(("tap", text)) or text in {"同意", "影集", "长白山"})
    monkeypatch.setattr(photo_picker, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(photo_picker.time, "sleep", lambda seconds: None)

    assert photo_picker._open_miui_gallery_target_album(FakeDriver(), "长白山") is True
    assert events == [
        ("tap", "同意"),
        ("tap", "影集"),
        ("tap", "长白山"),
    ]


def test_choose_local_photo_from_miui_gallery_does_not_select_when_album_missing(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X", "appium:deviceName": "25060RK16C"}

        def get_window_size(self):
            return {"width": 1280, "height": 2772}

    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'package="com.miui.gallery" resource-id="com.miui.gallery:id/micro_thumb" text="请选择项目"',
    )
    monkeypatch.setattr(photo_picker, "_open_miui_gallery_target_album", lambda driver, album_name: events.append(("album", album_name)) or False)
    monkeypatch.setattr(photo_picker, "_tap_android_photo_selection_badges", lambda driver, indexes: events.append(("select", indexes)) or True)
    monkeypatch.setattr(photo_picker, "confirm_system_photo_picker_selection", lambda driver: events.append("confirm") or True)

    assert photo_picker._choose_local_photo_from_android_gallery3d(FakeDriver(), preferred_album_name="长白山") is False
    assert events == [("album", "长白山")]


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
    monkeypatch.setattr(photo_picker, "_tap_rect_center", lambda driver, rect: False)
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


def test_tap_photo_grid_candidate_prefers_rect_tap_before_ios_element_click(monkeypatch):
    events = []
    selection_state = {"selected": False}

    class FakeElement:
        rect = {"x": 0, "y": 141, "width": 133, "height": 134}

        def click(self):
            raise AssertionError("slow iOS element click should be skipped after rect tap")

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            events.append((script, payload))
            selection_state["selected"] = True

    monkeypatch.setattr(photo_picker, "find_photo_grid_candidates", lambda driver: [FakeElement()])
    monkeypatch.setattr(
        photo_picker,
        "_safe_page_source",
        lambda driver: 'name="Add" label="完成" enabled="true" visible="true"'
        if selection_state["selected"]
        else 'name="Add" label="完成" enabled="false" visible="true"',
    )

    assert photo_picker.tap_photo_grid_candidate(FakeDriver(), 1) is True
    assert events == [("mobile: tap", {"x": 66.5, "y": 208.0})]


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
    clock = iter(range(100))

    monkeypatch.setattr(photo_picker.time, "monotonic", clock.__next__)
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


def test_photo_picker_done_button_enabled_returns_false_for_disabled_ios_button_without_xpath_lookup():
    class FakeDriver:
        def find_element(self, by, value):
            raise AssertionError("disabled Add button in XML should not fall back to slow XPath lookup")

    page_source = """
    <AppiumAUT>
      <XCUIElementTypeButton name="Add" label="完成" enabled="false" visible="true" x="346" y="92" width="36" height="36" />
    </AppiumAUT>
    """

    assert photo_picker._photo_picker_done_button_enabled(FakeDriver(), page_source=page_source) is False


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
