from pathlib import Path

from velowind_appium.modules.activity import (
    ActivityItineraryItem,
    activity_form_is_visible,
    activity_publish_success_signal,
    build_activity_draft,
    fill_activity_form,
    _fill_title,
    open_activity_publisher,
)
from velowind_appium.modules import activity


TESTDATA_PATH = Path(__file__).resolve().parent / "activity" / "testdata" / "publish_activity.yaml"


def test_build_activity_draft_reads_first_yaml_case():
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    assert draft.title == "太行山峡谷耐力骑行挑战"
    assert draft.activity_type == "骑行"
    assert draft.province == "浙江省"
    assert draft.city == "石家庄市"
    assert draft.location == "石家庄站东广场"
    assert draft.album == "太行山"
    assert draft.itinerary == [
        ActivityItineraryItem(
            title="Day1 集合说明",
            subtitle="石家庄集合签到",
            body="完成签到、路线说明与安全须知确认。",
        ),
        ActivityItineraryItem(
            title="Day2 主线骑行",
            subtitle="峡谷耐力挑战",
            body="完成主线路骑行并设置补给点。",
        ),
    ]


def test_activity_form_is_visible_detects_publish_form_text():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="发布活动" label="发布活动" value="发布活动" />
      <XCUIElementTypeStaticText name="活动名称" label="活动名称" value="活动名称" />
      <XCUIElementTypeStaticText name="提交审核" label="提交审核" value="提交审核" />
    </AppiumAUT>
    """

    assert activity_form_is_visible(page_source) is True


def test_activity_publish_success_signal_detects_review_success():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="提交成功" label="提交成功" value="提交成功" />
      <XCUIElementTypeStaticText name="审核中" label="审核中" value="审核中" />
    </AppiumAUT>
    """

    assert activity_publish_success_signal(page_source) == "提交成功"


def test_activity_publish_success_signal_accepts_my_activity_page_with_expected_title():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的活动" label="我的活动" value="我的活动" />
      <XCUIElementTypeStaticText name="太行山峡谷耐力骑行挑战" label="太行山峡谷耐力骑行挑战" value="太行山峡谷耐力骑行挑战" />
    </AppiumAUT>
    """

    assert activity_publish_success_signal(page_source, expected_title="太行山峡谷耐力骑行挑战") == "我的活动列表"


def test_open_activity_publisher_retries_when_publish_entry_opens_login(monkeypatch):
    state = {"page": "home"}
    login_calls = []

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "login_required_from_page_source", lambda page: page == "login")
    monkeypatch.setattr(activity, "activity_form_is_visible", lambda page: page == "form")
    monkeypatch.setattr(activity, "_tap_activity_type_if_present", lambda driver: False)

    def fake_tap_publish_entry(driver):
        if state["page"] == "home":
            state["page"] = "login"
            return True
        return False

    monkeypatch.setattr(activity, "_tap_publish_entry_if_present", fake_tap_publish_entry)
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())

    def fake_ensure_logged_in_if_needed(driver, ios_config):
        login_calls.append(ios_config)
        state["page"] = "form"
        return True

    monkeypatch.setattr(activity, "ensure_logged_in_if_needed", fake_ensure_logged_in_if_needed)
    monotonic_values = iter([0, 1, 2, 3, 4, 5])
    monkeypatch.setattr(activity.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    open_activity_publisher(object(), ios_config=object(), timeout=5)

    assert len(login_calls) == 1


def test_open_activity_publisher_aggressively_taps_activity_type_after_publish_entry(monkeypatch):
    events = []
    state = {"page": "home"}

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "login_required_from_page_source", lambda page: False)
    monkeypatch.setattr(activity, "activity_form_is_visible", lambda page: page == "form")
    monkeypatch.setattr(activity, "_publish_sheet_visible", lambda driver: (lambda: False))
    monkeypatch.setattr(
        activity,
        "_tap_activity_type_by_coordinate",
        lambda driver: events.append("tap-activity-type-by-coordinate") or state.update(page="form") or True,
    )
    monkeypatch.setattr(activity, "_tap_activity_type_if_present", lambda driver: events.append("tap-activity-type") or True)
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())

    def fake_tap_publish_entry(driver):
        events.append("tap-publish-entry")
        state["page"] = "sheet-hidden"
        return True

    monkeypatch.setattr(activity, "_tap_publish_entry_if_present", fake_tap_publish_entry)
    monotonic_values = iter([0, 1, 2, 3, 4, 5])
    monkeypatch.setattr(activity.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    open_activity_publisher(object(), ios_config=object(), timeout=5)

    assert events == ["tap-publish-entry", "tap-activity-type-by-coordinate"]


def test_open_activity_publisher_taps_activity_type_after_publish_entry_without_sheet_signal(monkeypatch):
    state = {"page": "home"}
    events = []

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "login_required_from_page_source", lambda page: False)
    monkeypatch.setattr(activity, "activity_form_is_visible", lambda page: page == "form")
    monkeypatch.setattr(activity, "_publish_sheet_visible", lambda driver: (lambda: False))

    def fake_tap_publish_entry(driver):
        events.append("tap-publish-entry")
        state["page"] = "sheet-hidden"
        return True

    def fake_tap_activity_type_by_coordinate(driver):
        events.append("tap-activity-type-by-coordinate")
        return False

    def fake_tap_activity_type(driver):
        events.append("tap-activity-type")
        if state["page"] == "sheet-hidden":
            state["page"] = "form"
            return True
        return False

    monkeypatch.setattr(activity, "_tap_publish_entry_if_present", fake_tap_publish_entry)
    monkeypatch.setattr(activity, "_tap_activity_type_by_coordinate", fake_tap_activity_type_by_coordinate)
    monkeypatch.setattr(activity, "_tap_activity_type_if_present", fake_tap_activity_type)
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())
    monotonic_values = iter([0, 1, 2, 3, 4, 5])
    monkeypatch.setattr(activity.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    open_activity_publisher(object(), ios_config=object(), timeout=5)

    assert events == ["tap-publish-entry", "tap-activity-type-by-coordinate", "tap-activity-type"]


def test_publish_sheet_visible_ignores_bottom_activity_tab(monkeypatch):
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "首页 活动 消息 我的")

    assert activity._publish_sheet_visible(object())() is False


def test_fill_activity_form_resolves_picker_placeholders_after_text_fields(monkeypatch):
    events = []
    draft = build_activity_draft()
    state = {"resolved": False}

    monkeypatch.setattr(activity, "wait_for_activity_form", lambda driver, timeout=60: True)
    monkeypatch.setattr(activity, "_upload_activity_image", lambda driver, draft: events.append("upload-image"))
    monkeypatch.setattr(activity, "_fill_title", lambda driver, value: events.append("fill-title"))
    monkeypatch.setattr(activity, "_select_activity_type", lambda driver, value: events.append("select-activity-type"))
    monkeypatch.setattr(activity, "_select_province", lambda driver, value: events.append("select-province"))
    monkeypatch.setattr(activity, "_fill_city", lambda driver, value: events.append("fill-city"))
    monkeypatch.setattr(activity, "_fill_description", lambda driver, value: events.append("fill-description"))
    monkeypatch.setattr(activity, "_fill_itinerary", lambda driver, value: events.append("fill-itinerary"))
    monkeypatch.setattr(activity, "_fill_known_text_fields", lambda driver, value: events.append("fill-known-fields"))
    monkeypatch.setattr(
        activity,
        "_resolve_picker_fields",
        lambda driver, timeout=60: events.append("resolve-picker-fields") or state.__setitem__("resolved", True),
    )
    monkeypatch.setattr(activity, "_required_field_markers_resolved", lambda driver: state["resolved"])

    fill_activity_form(object(), draft, timeout=30)

    assert events[-1] == "resolve-picker-fields"


def test_fill_title_keeps_existing_non_placeholder_value(monkeypatch):
    events = []

    monkeypatch.setattr(
        activity,
        "_fill_input_near_label",
        lambda driver, keyword, value, prefer_text_view=False, overwrite_existing=True: False,
    )

    class FakeElement:
        def get_attribute(self, name):
            if name == "value":
                return "杭州西湖徒步"
            if name == "placeholderValue":
                return "请输入活动名称"
            return ""

    monkeypatch.setattr(activity, "_find_first_title_input", lambda driver: FakeElement())
    monkeypatch.setattr(activity, "_replace_text", lambda element, value: events.append(("replace", value)))

    _fill_title(object(), "杭州西湖徒步")

    assert events == []


def test_fill_city_hides_keyboard_after_entering_value(monkeypatch):
    events = []

    monkeypatch.setattr(
        activity,
        "_fill_input_near_label",
        lambda driver, keyword, value: events.append(("fill", keyword, value)) or True,
    )
    monkeypatch.setattr(activity, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))

    activity._fill_city(object(), "石家庄市")

    assert events[-1] == "hide-keyboard"


def test_fill_description_populates_editor_title_and_body(monkeypatch):
    events = []

    monkeypatch.setattr(activity, "_open_editor", lambda driver, entry_text: True)
    monkeypatch.setattr(
        activity,
        "_fill_editor_entry",
        lambda driver, title, body: events.append(("fill-editor-entry", title, body)),
    )
    monkeypatch.setattr(activity, "_close_editor", lambda driver: events.append("close"))
    monkeypatch.setattr(activity, "_assert_editor_saved", lambda driver, placeholder, field_name: None)

    activity._fill_description(object(), "围绕太行山沿线打造的中高强度骑行活动")

    assert events == [
        ("fill-editor-entry", "活动概览", "围绕太行山沿线打造的中高强度骑行活动"),
        "close",
    ]


def test_fill_itinerary_fills_each_segment_and_taps_add_between_items(monkeypatch):
    events = []

    monkeypatch.setattr(activity, "_open_editor", lambda driver, entry_text: True)
    monkeypatch.setattr(activity, "_fill_itinerary_editor_item", lambda driver, index, item: events.append(("fill-item", index, item)))
    monkeypatch.setattr(activity, "_dismiss_editor_keyboard_fast", lambda driver: events.append("dismiss-keyboard"))
    monkeypatch.setattr(activity, "_add_itinerary_segment", lambda driver: events.append("add-segment") or True)
    monkeypatch.setattr(activity, "_close_editor", lambda driver: events.append("close"))
    monkeypatch.setattr(activity, "_assert_editor_saved", lambda driver, placeholder, field_name: None)

    activity._fill_itinerary(
        object(),
        [
            ActivityItineraryItem("Day1 集合说明", "石家庄集合签到", "完成签到、路线说明与安全须知确认。"),
            ActivityItineraryItem("Day2 主线骑行", "峡谷耐力挑战", "完成主线路骑行并设置2个补给点。"),
            ActivityItineraryItem("Day3 返程收尾", "自由骑行返程", "自由骑行返程，完成活动复盘后解散。"),
        ],
    )

    assert events == [
        ("fill-item", 0, ActivityItineraryItem("Day1 集合说明", "石家庄集合签到", "完成签到、路线说明与安全须知确认。")),
        "dismiss-keyboard",
        "add-segment",
        ("fill-item", 1, ActivityItineraryItem("Day2 主线骑行", "峡谷耐力挑战", "完成主线路骑行并设置2个补给点。")),
        "dismiss-keyboard",
        "add-segment",
        ("fill-item", 2, ActivityItineraryItem("Day3 返程收尾", "自由骑行返程", "自由骑行返程，完成活动复盘后解散。")),
        "close",
    ]


def test_fill_itinerary_editor_item_targets_title_subtitle_and_body(monkeypatch):
    events = []

    monkeypatch.setattr(
        activity,
        "_fill_indexed_editor_text_field",
        lambda driver, placeholder, value, index: events.append(("field", placeholder, value, index)),
    )
    monkeypatch.setattr(
        activity,
        "_fill_indexed_editor_text_view",
        lambda driver, value, index: events.append(("body", value, index)),
    )
    monkeypatch.setattr(activity, "_dismiss_editor_keyboard_fast", lambda driver: events.append("dismiss-keyboard"))

    activity._fill_itinerary_editor_item(
        object(),
        1,
        ActivityItineraryItem("Day2 主线骑行", "峡谷耐力挑战", "完成主线路骑行并设置2个补给点。"),
    )

    assert events == [
        ("field", "标题", "Day2 主线骑行", 1),
        "dismiss-keyboard",
        ("field", "副标题", "峡谷耐力挑战", 1),
        "dismiss-keyboard",
        ("body", "完成主线路骑行并设置2个补给点。", 1),
        "dismiss-keyboard",
    ]


def test_select_activity_type_chooses_specific_overlay_option(monkeypatch):
    selected_options = []

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: True)
    monkeypatch.setattr(
        activity,
        "_choose_specific_overlay_option",
        lambda driver, text: selected_options.append(text) or True,
    )

    activity._select_activity_type(object(), "骑行")

    assert selected_options == ["骑行"]


def test_select_province_chooses_specific_overlay_option(monkeypatch):
    selected_options = []

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: True)
    monkeypatch.setattr(
        activity,
        "_choose_specific_overlay_option",
        lambda driver, text: selected_options.append(text) or True,
    )

    activity._select_province(object(), "上海")

    assert selected_options == [["上海", "上海市", "上海省"]]


def test_choose_specific_overlay_option_scrolls_until_target_appears(monkeypatch):
    events = []
    state = {"page": "浙江省 四川省 云南省 广东省"}

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=2: text in state["page"])

    def fake_swipe_vertical(driver, direction="up"):
        events.append(("swipe", direction))
        state["page"] = "河北省 河南省 山西省"

    monkeypatch.setattr(activity, "swipe_vertical", fake_swipe_vertical)
    monkeypatch.setattr(activity, "_confirm_overlay_selection", lambda driver: events.append("confirm"))
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    assert activity._choose_specific_overlay_option(object(), ["河北省", "河北"]) is True
    assert events == [("swipe", "up"), "confirm"]


def test_close_editor_dismisses_keyboard_like_note_before_bottom_done(monkeypatch):
    events = []
    sources = iter([
        "编辑活动说明 请输入正文 完成",
        "编辑活动说明 请输入正文 完成",
        "发布活动 提交审核",
    ])

    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: next(sources))
    monkeypatch.setattr(activity, "_editor_page_visible", lambda page_source: "编辑活动说明" in page_source)
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: events.append(("tap-text", text)) or text == "完成")

    class FakeDriver:
        def back(self):
            raise activity.WebDriverException("no-back")

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))

    activity._close_editor(FakeDriver())

    assert events == [
        ("execute", "mobile: tap", {"x": 361, "y": 157}),
        ("execute", "mobile: tap", {"x": 201, "y": 95}),
        ("tap-text", "完成"),
    ]


def test_close_editor_requires_editor_to_actually_close_after_tapping_done(monkeypatch):
    events = []

    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "编辑活动说明 完成")
    monkeypatch.setattr(activity, "_editor_page_visible", lambda page_source: True)
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: False)
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: events.append(("tap-text", text)) or text == "完成")

    class FakeDriver:
        def back(self):
            raise activity.WebDriverException("no-back")

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))

        def find_element(self, by, value):
            raise activity.NoSuchElementException("missing")

    try:
        activity._close_editor(FakeDriver())
    except AssertionError as exc:
        assert str(exc) == "Unable to close the activity editor and return to the publish form"
    else:
        raise AssertionError("Expected _close_editor to fail when the editor remains visible after tapping done")

    assert events[:1] == [("execute", "mobile: tap", {"x": 361, "y": 157})]
    assert ("tap-text", "完成") in events
    assert ("execute", "mobile: tap", {"x": 82, "y": 95}) in events


def test_close_editor_uses_bottom_done_before_keyboard_fallback(monkeypatch):
    events = []
    state = {"closed": False}

    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        activity,
        "_safe_page_source",
        lambda driver: "发布活动 提交审核" if state["closed"] else "编辑活动说明 活动概览",
    )
    monkeypatch.setattr(activity, "_editor_page_visible", lambda page_source: "编辑活动说明" in page_source)
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: False)

    class FakeDriver:
        def back(self):
            events.append("back")

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))
            if payload["y"] > 700:
                state["closed"] = True

        def find_element(self, by, value):
            raise activity.NoSuchElementException("missing")

    activity._close_editor(FakeDriver())

    assert "back" not in events
    assert ("execute", "mobile: tap", {"x": 361, "y": 157}) in events
    assert ("execute", "mobile: tap", {"x": 201, "y": 95}) in events
    assert ("execute", "mobile: tap", {"x": 225, "y": 821}) in events


def test_upload_activity_image_uses_album_from_draft(monkeypatch):
    calls = []
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    monkeypatch.setattr(activity, "_tap_image_picker", lambda driver: True)
    monkeypatch.setattr(
        activity.photo_picker,
        "choose_photo_from_library",
        lambda driver, album_name=None, select_all_from_album=True, prefer_retry_sheet_option_first=False, retry_sheet_option=None: calls.append(
            (
                "choose-photo",
                album_name,
                select_all_from_album,
                retry_sheet_option is activity._tap_activity_photo_library_sheet_option,
            )
        )
        or True,
    )

    activity._upload_activity_image(object(), draft)

    assert calls == [("choose-photo", "太行山", False, True)]


def test_upload_activity_image_waits_for_photo_library_before_choosing_album(monkeypatch):
    calls = []
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    monkeypatch.setattr(activity, "_tap_image_picker", lambda driver: True)
    monkeypatch.setattr(
        activity.photo_picker,
        "choose_photo_from_library",
        lambda driver, album_name=None, select_all_from_album=True, prefer_retry_sheet_option_first=False, retry_sheet_option=None: calls.append(
            ("choose-photo", album_name, select_all_from_album)
        )
        or True,
    )

    activity._upload_activity_image(object(), draft)

    assert calls == [("choose-photo", "太行山", False)]


def test_upload_activity_image_requires_phone_photo_library_source(monkeypatch):
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    monkeypatch.setattr(activity, "_tap_image_picker", lambda driver: True)
    monkeypatch.setattr(
        activity.photo_picker,
        "choose_photo_from_library",
        lambda driver, album_name=None, select_all_from_album=True, prefer_retry_sheet_option_first=False, retry_sheet_option=None: False,
    )

    try:
        activity._upload_activity_image(object(), draft)
    except AssertionError as exc:
        assert str(exc) == "Unable to upload an activity image from the local photo library"
        return

    raise AssertionError("Expected _upload_activity_image to fail when photo source selection does not open")


def test_upload_activity_image_retries_activity_action_sheet_option_when_library_does_not_open(monkeypatch):
    calls = []
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    monkeypatch.setattr(activity, "_tap_image_picker", lambda driver: True)
    monkeypatch.setattr(
        activity.photo_picker,
        "choose_photo_from_library",
        lambda driver, album_name=None, select_all_from_album=True, prefer_retry_sheet_option_first=False, retry_sheet_option=None: (
            calls.append(
                (
                    "retry",
                    retry_sheet_option is activity._tap_activity_photo_library_sheet_option,
                    album_name,
                    select_all_from_album,
                )
            )
            or True
        ),
    )

    activity._upload_activity_image(object(), draft)

    assert calls == [("retry", True, "太行山", False)]
