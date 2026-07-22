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


TESTDATA_PATH = Path(__file__).resolve().parent.parent / "activity" / "testdata" / "publish_activity.yaml"


def test_build_activity_draft_reads_first_yaml_case():
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    assert draft.title == "张家界大环线2天1晚"
    assert draft.activity_type == "骑行"
    assert draft.province == "浙江省"
    assert draft.city == "张家界市"
    assert draft.location == "张家界西站出站口"
    assert draft.album == "张家界"
    assert draft.itinerary == [
        ActivityItineraryItem(
            title="Day1 集合与环线热身",
            subtitle="张家界西站集合",
            body="完成签到、车辆调试和安全说明，沿城市绿道热身骑行后入住武陵源。",
        ),
        ActivityItineraryItem(
            title="Day2 大环线骑行",
            subtitle="武陵源至天门山环线",
            body="完成张家界大环线主线路骑行，途经山地观景路段和补给点，返程后提交活动收尾确认。",
        ),
    ]


def test_build_activity_draft_reads_all_zhangjiajie_fields():
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    assert draft.title == "张家界大环线2天1晚"
    assert draft.activity_type == "骑行"
    assert draft.province == "浙江省"
    assert draft.city == "张家界市"
    assert draft.album == "张家界"
    assert draft.contact_name == "张家界大环线领队"
    assert draft.contact_phone == "13800138000"
    assert draft.location == "张家界西站出站口"
    assert draft.max_participants == "20"
    assert draft.fee == "0"
    assert draft.reference_duration == "2天1晚"
    assert draft.total_mileage == "128"
    assert draft.max_altitude == "1518"
    assert draft.elevation_gain == "1860"
    assert draft.scenery_tags == ["峰林", "峡谷", "山地公路"]
    assert draft.scenic_spots == ["武陵源", "天门山", "张家界国家森林公园"]
    assert draft.itinerary == [
        ActivityItineraryItem(
            title="Day1 集合与环线热身",
            subtitle="张家界西站集合",
            body="完成签到、车辆调试和安全说明，沿城市绿道热身骑行后入住武陵源。",
        ),
        ActivityItineraryItem(
            title="Day2 大环线骑行",
            subtitle="武陵源至天门山环线",
            body="完成张家界大环线主线路骑行，途经山地观景路段和补给点，返程后提交活动收尾确认。",
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


def test_activity_form_is_visible_reads_android_text_attributes():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="发布活动" />
      <android.widget.TextView text="活动名称" />
      <android.widget.TextView text="提交审核" />
    </hierarchy>
    """

    assert activity_form_is_visible(page_source) is True


def test_activity_form_is_visible_rejects_publish_type_sheet():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="选择发布类型" />
      <android.widget.TextView text="发布笔记" />
      <android.widget.TextView text="发布活动" />
    </hierarchy>
    """

    assert activity_form_is_visible(page_source) is False


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
      <XCUIElementTypeStaticText name="张家界大环线2天1晚" label="张家界大环线2天1晚" value="张家界大环线2天1晚" />
    </AppiumAUT>
    """

    assert activity_publish_success_signal(page_source, expected_title="张家界大环线2天1晚") == "我的活动列表"


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


def test_open_activity_publisher_prepares_android_publish_entry_before_loop(monkeypatch):
    events = []
    state = {"page": "form"}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "login_required_from_page_source", lambda page: False)
    monkeypatch.setattr(activity, "activity_form_is_visible", lambda page: page == "form")
    monkeypatch.setattr(
        activity,
        "_prepare_android_publish_entry",
        lambda driver: events.append("prepare-android-publish-entry"),
    )

    open_activity_publisher(FakeDriver(), ios_config=object(), timeout=5)

    assert events == ["prepare-android-publish-entry"]


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


def test_tap_plus_button_by_coordinate_verifies_android_publish_sheet_opened(monkeypatch):
    taps = []
    pages = iter(["home", "选择发布类型 发布活动"])

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1000, "height": 2000}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: next(pages))
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    assert activity._tap_plus_button_by_coordinate(FakeDriver()) is True
    assert taps == [
        ("mobile: tap", {"x": 500, "y": 1870}),
        ("mobile: tap", {"x": 500, "y": 1896}),
    ]


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
    monkeypatch.setattr(activity, "_fill_advanced_settings", lambda driver, value: events.append("fill-advanced-settings"))
    monkeypatch.setattr(
        activity,
        "_resolve_picker_fields",
        lambda driver, timeout=60: events.append("resolve-picker-fields") or state.__setitem__("resolved", True),
    )
    monkeypatch.setattr(activity, "_required_field_markers_resolved", lambda driver: state["resolved"])

    fill_activity_form(object(), draft, timeout=30)

    assert "fill-advanced-settings" in events
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


def test_fill_title_supports_android_edit_text_hint(monkeypatch):
    events = []
    placeholder = "给这场活动起一个让人想出发的名字"

    class FakeElement:
        def get_attribute(self, name):
            return {
                "value": placeholder,
                "text": placeholder,
                "hint": placeholder,
                "showing-hint": "true",
            }.get(name)

        def click(self):
            events.append("click")

        def clear(self):
            events.append("clear")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        def find_element(self, by, value):
            if "android.widget.EditText" in value and '@text' in value:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: 'text="活动名称"')
    monkeypatch.setattr(activity, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))

    _fill_title(FakeDriver(), "太行山峡谷耐力骑行挑战")

    assert events == [
        "click",
        "clear",
        ("send-keys", "太行山峡谷耐力骑行挑战"),
        "hide-keyboard",
    ]


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


def test_fill_editor_entry_supports_android_edit_text_fields():
    events = []

    class FakeElement:
        def __init__(self, field):
            self.field = field

        def click(self):
            events.append((self.field, "click"))

        def clear(self):
            events.append((self.field, "clear"))

        def send_keys(self, value):
            events.append((self.field, "send-keys", value))

    class FakeDriver:
        def find_element(self, by, value):
            if "android.widget.EditText" not in value:
                raise activity.NoSuchElementException("missing")
            if "活动概览" in value:
                return FakeElement("title")
            if "请输入正文" in value:
                return FakeElement("body")
            raise activity.NoSuchElementException("missing")

    activity._fill_editor_entry(FakeDriver(), "活动概览", "活动正文")

    assert events == [
        ("title", "click"),
        ("title", "clear"),
        ("title", "send-keys", "活动概览"),
        ("body", "click"),
        ("body", "clear"),
        ("body", "send-keys", "活动正文"),
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


def test_find_indexed_itinerary_fields_support_android_edit_text():
    class FakeElement:
        def __init__(self, name, y):
            self.name = name
            self.rect = {"x": 229, "y": y, "width": 758, "height": 73}

        def is_displayed(self):
            return True

    title = FakeElement("title", 361)
    body = FakeElement("body", 559)

    class FakeDriver:
        def find_elements(self, by, value):
            if "android.widget.EditText" not in value:
                return []
            if "标题" in value:
                return [title]
            if "正文" in value:
                return [body]
            return []

    assert activity._find_indexed_editor_text_field(FakeDriver(), "标题", 0) is title
    assert activity._find_indexed_editor_text_view(FakeDriver(), 0) is body


def test_find_add_itinerary_segment_button_supports_android_view_group():
    class FakeElement:
        rect = {"x": 930, "y": 937, "width": 82, "height": 81}

        def is_displayed(self):
            return True

    add_button = FakeElement()

    class FakeDriver:
        def find_elements(self, by, value):
            if "android.view.ViewGroup" in value:
                return [add_button]
            return []

    assert activity._find_add_itinerary_segment_button(FakeDriver()) is add_button


def test_count_itinerary_editor_sections_supports_android_title_fields():
    page_source = """
    <hierarchy>
      <node text="标题" class="android.widget.EditText" />
      <node text="副标题" class="android.widget.EditText" />
      <node text="标题" class="android.widget.EditText" />
      <node text="副标题" class="android.widget.EditText" />
    </hierarchy>
    """

    assert activity._count_itinerary_editor_sections(page_source) == 2


def test_fill_itinerary_accepts_matching_items_already_saved_in_form(monkeypatch):
    itinerary = [
        ActivityItineraryItem("Day1 集合说明", "石家庄集合签到", "完成签到、路线说明与安全须知确认。"),
        ActivityItineraryItem("Day2 主线骑行", "峡谷耐力挑战", "完成主线路骑行并设置补给点。"),
    ]
    page_source = " ".join(
        [
            "发布活动 活动行程",
            *[part for item in itinerary for part in (item.title, item.subtitle, item.body)],
            "存草稿 提交审核",
        ]
    )

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: page_source)
    monkeypatch.setattr(
        activity,
        "_open_editor",
        lambda driver, entry_text: (_ for _ in ()).throw(AssertionError("should not reopen saved itinerary")),
    )

    activity._fill_itinerary(object(), itinerary)


def test_tap_submit_taps_center_of_visible_bottom_submit_button(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    submit_button = FakeElement({"x": 145, "y": 781, "width": 244, "height": 47})

    class FakeDriver:
        def find_elements(self, by, value):
            return [submit_button]

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(activity, "tap_if_present", lambda driver, accessibility_id, timeout: False)
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout: False)

    assert activity._tap_submit(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 267.0, "y": 804.5})]


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


def test_choose_specific_overlay_option_keeps_scrolling_until_later_province_appears(monkeypatch):
    events = []
    state = {"page": "浙江省 四川省 云南省 广东省", "swipes": 0}

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=2: text in state["page"])

    def fake_swipe_vertical(driver, direction="up"):
        events.append(("swipe", direction))
        state["swipes"] += 1
        if state["swipes"] == 5:
            state["page"] = "湖北省 湖南省 广西壮族自治区 海南省"

    monkeypatch.setattr(activity, "swipe_vertical", fake_swipe_vertical)
    monkeypatch.setattr(activity, "_confirm_overlay_selection", lambda driver: events.append("confirm"))
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    assert activity._choose_specific_overlay_option(object(), ["湖南省", "湖南"]) is True
    assert events == [
        ("swipe", "up"),
        ("swipe", "up"),
        ("swipe", "up"),
        ("swipe", "up"),
        ("swipe", "up"),
        "confirm",
    ]


def test_open_advanced_settings_taps_android_row_arrow(monkeypatch):
    taps = []
    advanced_values = [(["总里程"], "128")]
    sources = iter(["发布活动 高级选项", "发布活动 总里程", "发布活动 总里程"])

    class FakeElement:
        rect = {"x": 87, "y": 2313, "width": 192, "height": 66}

    class FakeDriver:
        @staticmethod
        def get_window_rect():
            return {"width": 1280, "height": 2856}

        @staticmethod
        def find_element(by, value):
            if "高级选项" in value:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: next(sources, "发布活动 总里程"))
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    assert activity._open_advanced_settings(FakeDriver(), advanced_values) is True
    assert taps == [("mobile: tap", {"x": 1164, "y": 2346})]


def test_open_advanced_settings_taps_exact_ios_row_instead_of_page_container(monkeypatch):
    taps = []
    advanced_values = [(["总里程"], "128")]
    sources = iter(["<XCUIElementTypeOther name='发布活动 高级选项'>", "发布活动 总里程", "发布活动 总里程"])

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        @staticmethod
        def find_elements(by, value):
            assert "contains" not in value
            if "高级选项" in value:
                return [
                    FakeElement({"x": 0, "y": 0, "width": 402, "height": 874}),
                    FakeElement({"x": 13, "y": 699, "width": 376, "height": 43}),
                    FakeElement({"x": 27, "y": 710, "width": 61, "height": 21}),
                ]
            return []

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: next(sources, "发布活动 总里程"))
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    assert activity._open_advanced_settings(FakeDriver(), advanced_values) is True
    assert taps == [("mobile: tap", {"x": 361, "y": 720})]


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

    assert calls == [("choose-photo", "张家界", False, True)]


def test_tap_image_picker_uses_android_activity_image_container(monkeypatch):
    picker = object()
    center_taps = []
    coordinate_taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            if 'android.widget.TextView[@text="活动图片"]' in value:
                return picker
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            coordinate_taps.append((script, payload))

    monkeypatch.setattr(
        activity,
        "_tap_element_center",
        lambda driver, element: center_taps.append(element),
    )

    assert activity._tap_image_picker(FakeDriver()) is True
    assert center_taps == [picker]
    assert coordinate_taps == []


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

    assert calls == [("choose-photo", "张家界", False)]


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

    assert calls == [("retry", True, "张家界", False)]
