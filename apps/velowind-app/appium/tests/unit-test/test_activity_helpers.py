from pathlib import Path

import pytest

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


class FakeActivityElement:
    def __init__(self, rect, *, value="", visible=True):
        self.rect = rect
        self.value = value
        self.visible = visible
        self.clicked = False
        self.cleared = False
        self.sent_keys = []

    def click(self):
        self.clicked = True

    def clear(self):
        self.cleared = True
        self.value = ""

    def send_keys(self, value):
        self.sent_keys.append(value)
        self.value = value

    def is_displayed(self):
        return self.visible

    def get_attribute(self, name):
        if name in {"value", "name", "label", "placeholderValue"}:
            return self.value
        return ""


def test_build_activity_draft_reads_first_yaml_case():
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    assert draft.title == "测试 - 张家界大环线2天1晚"
    assert draft.activity_type == "骑行"
    assert draft.province == "湖南"
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

    assert draft.title == "测试 - 张家界大环线2天1晚"
    assert draft.activity_type == "骑行"
    assert draft.province == "湖南"
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


def test_advanced_field_visible_ignores_background_activity_feed_text():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther visible="true" name="活动列表 总里程 64 时长 2天1晚" x="0" y="0" width="402" height="874" />
      <XCUIElementTypeOther visible="true" name="发布活动 活动名称 高级选项 提交审核" x="0" y="128" width="402" height="746" />
    </AppiumAUT>
    """

    assert activity._advanced_field_visible(page_source, [(["总里程", "里程"], "128")]) is False


def test_fill_ios_input_near_label_requires_visible_nearby_input(monkeypatch):
    title_field = FakeActivityElement({"x": 26, "y": 300, "width": 350, "height": 21})

    class FakeDriver:
        page_source = '<AppiumAUT><XCUIElementTypeOther visible="true" name="总里程" x="0" y="0" width="402" height="874" /></AppiumAUT>'

        def find_elements(self, _by, xpath):
            if "contains(@name" in xpath:
                return [FakeActivityElement({"x": 0, "y": 0, "width": 402, "height": 874})]
            if "XCUIElementTypeTextField" in xpath:
                return [title_field]
            return []

    monkeypatch.setattr(activity, "_hide_keyboard", lambda driver: None)

    assert activity._fill_input_near_label(FakeDriver(), "总里程", "128") is False
    assert title_field.sent_keys == []


def test_fill_ios_input_near_label_fills_nearby_visible_input(monkeypatch):
    field = FakeActivityElement({"x": 26, "y": 420, "width": 350, "height": 44})

    class FakeDriver:
        page_source = '<AppiumAUT><XCUIElementTypeStaticText visible="true" name="总里程" x="26" y="380" width="80" height="24" /></AppiumAUT>'

        def find_elements(self, _by, xpath):
            if "contains(@name" in xpath:
                return [FakeActivityElement({"x": 26, "y": 380, "width": 80, "height": 24})]
            if "XCUIElementTypeTextField" in xpath:
                return [field]
            return []

    monkeypatch.setattr(activity, "_hide_keyboard", lambda driver: None)

    assert activity._fill_input_near_label(FakeDriver(), "总里程", "128") is True
    assert field.sent_keys == ["128"]


def test_fill_advanced_field_prefers_exact_placeholder(monkeypatch):
    field = FakeActivityElement({"x": 26, "y": 337, "width": 350, "height": 21})
    calls = []

    class FakeDriver:
        def find_element(self, _by, xpath):
            calls.append(xpath)
            if '@placeholderValue="例如：68km"' in xpath:
                return field
            raise activity.NoSuchElementException("not found")

    monkeypatch.setattr(activity, "_hide_keyboard", lambda driver: None)

    assert activity._fill_advanced_field(FakeDriver(), ["总里程", "里程"], "128", ["例如：68km"]) is True
    assert field.sent_keys == ["128"]
    assert calls


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


def test_open_activity_publisher_does_not_tap_activity_type_when_publish_sheet_is_absent(monkeypatch):
    events = []
    state = {"page": "home"}

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "login_required_from_page_source", lambda page: False)
    monkeypatch.setattr(activity, "activity_form_is_visible", lambda page: page == "form")
    monkeypatch.setattr(activity, "_publish_sheet_visible", lambda driver: (lambda: False))
    monkeypatch.setattr(activity, "_tap_activity_type_by_coordinate", lambda driver: events.append("tap-activity-type-by-coordinate") or True)
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

    try:
        open_activity_publisher(object(), ios_config=object(), timeout=3)
    except AssertionError as exc:
        assert "Unable to open the activity publisher" in str(exc)

    assert events == ["tap-publish-entry"]


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


def test_tap_plus_button_by_coordinate_rejects_ios_tap_when_publish_entry_stays_closed(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        @staticmethod
        def get_window_rect():
            return {"width": 402, "height": 874}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "首页 全国 推荐 笔记 活动 消息 我的")
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())

    assert activity._tap_plus_button_by_coordinate(FakeDriver()) is False
    assert taps == [("mobile: tap", {"x": 201, "y": 812})]


def test_tap_plus_button_by_coordinate_accepts_ios_tap_after_publish_sheet_opens(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        @staticmethod
        def get_window_rect():
            return {"width": 402, "height": 874}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "选择发布类型 发布活动")
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())

    assert activity._tap_plus_button_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 201, "y": 812})]


def test_tap_publish_entry_continues_to_plus_when_id_tap_does_not_open(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(activity, "tap_if_present", lambda driver, accessibility_id, timeout=0.5: events.append(("id", accessibility_id)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "首页 全国 推荐 笔记 活动 消息 我的")
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())
    monkeypatch.setattr(activity, "_tap_plus_button_by_coordinate", lambda driver: events.append("plus") or True)

    assert activity._tap_publish_entry_if_present(FakeDriver()) is True
    assert events == [("id", "bottom-nav-publish"), "plus"]


def test_open_activity_publisher_skips_activity_type_after_unverified_publish_entry(monkeypatch):
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

    try:
        open_activity_publisher(object(), ios_config=object(), timeout=3)
    except AssertionError as exc:
        assert "Unable to open the activity publisher" in str(exc)

    assert events == ["tap-publish-entry"]


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
    monkeypatch.setattr(activity, "_select_activity_region", lambda driver, province, city: events.append("select-region"))
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


def test_fill_city_selects_city_from_region_drawer(monkeypatch):
    events = []

    monkeypatch.setattr(
        activity,
        "_safe_page_source",
        lambda driver: "发布活动 搜索省份或城市 张家界 确认地区",
    )
    monkeypatch.setattr(
        activity,
        "tap_text_if_present",
        lambda driver, text, timeout=1: events.append(("tap", text)) or text in {"张家界", "确认地区"},
    )
    monkeypatch.setattr(activity, "_fill_input_near_label", lambda driver, keyword, value: False)

    activity._fill_city(object(), "张家界市")

    assert events == [("tap", "张家界市"), ("tap", "张家界"), ("tap", "确认地区")]


def test_select_activity_region_selects_province_then_city_in_region_drawer(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 湖南 湖北 河南 确认地区"}

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: events.append(("open", text)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())

    def fake_tap_region_option(driver, texts, timeout=2):
        events.append(("tap-option", tuple(texts)))
        if "湖南" in texts:
            state["page"] = "湖南 搜索省份或城市 张家界 长沙 湘潭 确认地区"
            return True
        if "张家界" in texts:
            state["page"] = "湖南 张家界 确认地区"
            return True
        return False

    monkeypatch.setattr(activity, "_tap_region_option", fake_tap_region_option)
    def fake_tap_text(driver, text, timeout=1):
        events.append(("tap", text))
        if text == "确认地区":
            state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"
            return True
        return False

    monkeypatch.setattr(activity, "tap_text_if_present", fake_tap_text)

    activity._select_activity_region(object(), "湖南", "张家界市")

    assert events == [
        ("open", "选择所属省份"),
        ("tap-option", ("湖南", "湖南市", "湖南省")),
        ("tap-option", ("张家界市", "张家界")),
        ("tap", "确认地区"),
    ]


def test_select_activity_region_uses_placeholder_when_form_field_tap_misses(monkeypatch):
    events = []
    state = {"page": "发布活动 所属省份 选择所属省份 城市名称 例如：杭州"}

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: False)

    def fake_tap_placeholder(driver, placeholder):
        events.append(("tap-placeholder", placeholder))
        if placeholder == "选择所属省份":
            state["page"] = "选择地区 搜索省份或城市 湖南 张家界 确认地区"
            return True
        return False

    monkeypatch.setattr(activity, "_tap_placeholder", fake_tap_placeholder)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())

    def fake_tap_region_option(driver, texts, timeout=2):
        events.append(("tap-option", tuple(texts)))
        return True

    def fake_tap_text(driver, text, timeout=1):
        events.append(("tap", text))
        if text == "确认地区":
            state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"
            return True
        return False

    monkeypatch.setattr(activity, "_tap_region_option", fake_tap_region_option)
    monkeypatch.setattr(activity, "tap_text_if_present", fake_tap_text)

    activity._select_activity_region(object(), "湖南", "张家界市")

    assert events == [
        ("tap-placeholder", "选择所属省份"),
        ("tap-option", ("湖南", "湖南市", "湖南省")),
        ("tap-option", ("张家界市", "张家界")),
        ("tap", "确认地区"),
    ]


def test_select_activity_region_fails_fast_when_region_drawer_cannot_open(monkeypatch):
    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: False)
    monkeypatch.setattr(activity, "_tap_placeholder", lambda driver, placeholder: False)

    with pytest.raises(AssertionError, match="Unable to open the activity region drawer"):
        activity._select_activity_region(object(), "湖南", "张家界市")


def test_select_activity_region_waits_for_province_after_drawer_search(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 确认地区", "pending_province": False}

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: events.append(("open", text)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])

    def fake_wait_until(predicate, timeout):
        events.append(("wait", timeout))
        if state["pending_province"]:
            state["page"] = "选择地区 搜索省份或城市 湖南省 确认地区"
            state["pending_province"] = False
        return predicate()

    monkeypatch.setattr(activity, "_wait_until", fake_wait_until)

    def fake_search_region_drawer(driver, query):
        events.append(("search", query))
        state["pending_province"] = True
        return True

    def fake_tap_region_option(driver, texts, timeout=2):
        events.append(("tap-option", tuple(texts), timeout))
        if "湖南省" in state["page"] and "湖南省" in texts:
            state["page"] = "选择地区 搜索省份或城市 张家界市 确认地区"
            return True
        if "张家界市" in state["page"] and "张家界市" in texts:
            state["page"] = "选择地区 搜索省份或城市 湖南省 张家界市 确认地区"
            return True
        return False

    monkeypatch.setattr(activity, "_search_region_drawer", fake_search_region_drawer)
    monkeypatch.setattr(activity, "_tap_region_option", fake_tap_region_option)
    def fake_tap_text(driver, text, timeout=1):
        events.append(("tap", text))
        if text == "确认地区":
            state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"
            return True
        return False

    monkeypatch.setattr(activity, "tap_text_if_present", fake_tap_text)

    activity._select_activity_region(object(), "湖南", "张家界市")

    assert ("search", "张家界") in events
    assert ("wait", 3) in events
    assert any(event[:2] == ("tap-option", ("湖南", "湖南市", "湖南省")) for event in events)
    assert ("tap", "确认地区") in events


def test_select_activity_region_taps_search_result_when_confirm_button_is_absent(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"}

    class FakeElement:
        rect = {"x": 42, "y": 646, "width": 894, "height": 49}

    class FakeDriver:
        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "湖南" in xpath and "张家界" in xpath:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            events.append((script, payload))
            state["page"] = "发布活动 所属省份 湖南省 城市名称 张家界市"

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: events.append(("open", text)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: events.append(("wait", timeout)) or predicate())
    monkeypatch.setattr(activity, "_tap_region_option", lambda driver, texts, timeout=2: events.append(("tap-option", tuple(texts))) or True)
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: events.append(("tap", text)) or False)

    activity._select_activity_region(FakeDriver(), "湖南", "张家界市")

    assert any(event[0] == "mobile: tap" for event in events if isinstance(event, tuple))
    assert state["page"] == "发布活动 所属省份 湖南省 城市名称 张家界市"


def test_tap_region_search_result_uses_android_xml_bounds_fallback(monkeypatch):
    events = []
    page_source = """
    <hierarchy>
      <android.widget.TextView text="选择地区" displayed="true" bounds="[42,194][1007,256]" />
      <android.widget.EditText text="张家界" hint="搜索省份或城市" displayed="true" bounds="[140,299][978,389]" />
      <android.widget.TextView text="搜索结果" displayed="true" bounds="[42,474][981,536]" />
      <android.view.ViewGroup bounds="[0,562][1050,712]" displayed="true">
        <android.widget.TextView text="张家界" displayed="true" bounds="[42,580][936,639]" />
        <android.widget.TextView text="湖南省 · 张家界市" displayed="true" bounds="[42,646][936,695]" />
        <com.horcrux.svg.SvgView displayed="true" bounds="[955,611][1007,663]" />
      </android.view.ViewGroup>
    </hierarchy>
    """

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

        def find_element(self, _by, _xpath):
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: page_source)
    monkeypatch.setattr(activity, "_android_adb_tap", lambda driver, x, y: events.append(("adb-tap", x, y)) or True)

    assert activity._tap_region_search_result(FakeDriver(), "湖南", "张家界市") is True
    assert ("adb-tap", 981, 637) in events


def test_tap_region_search_result_prefers_semantic_android_result_row(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"}

    class FakeElement:
        rect = {"x": 0, "y": 562, "width": 1050, "height": 150}

        def click(self):
            events.append("row-click")
            state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"

    class FakeDriver:
        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "ancestor::android.view.ViewGroup" in xpath and "湖南" in xpath and "张家界" in xpath:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())

    assert activity._tap_region_search_result(FakeDriver(), "湖南", "张家界市") is True
    assert events[-1] == "row-click"
    assert not any(event[0] == "mobile: tap" for event in events if isinstance(event, tuple))


def test_tap_region_search_result_continues_when_semantic_android_row_click_is_ignored(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"}

    class FakeRow:
        rect = {"x": 0, "y": 562, "width": 1050, "height": 150}

        def click(self):
            events.append("row-click")

    class FakeCity:
        rect = {"x": 42, "y": 580, "width": 894, "height": 59}

        def click(self):
            events.append("city-click")
            state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"

    class FakeDriver:
        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "ancestor::android.view.ViewGroup" in xpath and "湖南" in xpath and "张家界" in xpath:
                return FakeRow()
            if 'android.widget.TextView[@text="张家界"]' in xpath:
                return FakeCity()
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())

    assert activity._tap_region_search_result(FakeDriver(), "湖南", "张家界市") is True
    assert "row-click" in events
    assert ("find", '//android.widget.TextView[@text="张家界"]') in events
    assert events[-1] == "city-click"


def test_tap_region_search_result_taps_android_city_title_center_when_click_is_ignored(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"}

    class FakeElement:
        rect = {"x": 42, "y": 580, "width": 894, "height": 59}

        def click(self):
            events.append("click")

    class FakeDriver:
        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "ancestor::android.view.ViewGroup" in xpath or 'android.widget.TextView[@text="张家界"]' in xpath:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            events.append((script, payload))
            if script == "mobile: tap" and payload == {"x": 489.0, "y": 609.5}:
                state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity.time, "sleep", lambda _seconds: None)

    assert activity._tap_region_search_result(FakeDriver(), "湖南", "张家界市") is True
    assert ("mobile: tap", {"x": 489.0, "y": 609.5}) in events


def test_tap_region_search_result_continues_to_android_adb_arrow_when_appium_tap_is_ignored(monkeypatch):
    events = []
    page_source = """
    <hierarchy>
      <android.widget.TextView text="选择地区" displayed="true" bounds="[42,194][1007,256]" />
      <android.widget.EditText text="张家界" hint="搜索省份或城市" displayed="true" bounds="[140,299][978,389]" />
      <android.widget.TextView text="搜索结果" displayed="true" bounds="[42,474][981,536]" />
      <android.view.ViewGroup bounds="[0,562][1050,712]" displayed="true">
        <android.widget.TextView text="张家界" displayed="true" bounds="[42,580][936,639]" />
        <android.widget.TextView text="湖南省 · 张家界市" displayed="true" bounds="[42,646][936,695]" />
        <com.horcrux.svg.SvgView displayed="true" bounds="[955,611][1007,663]" />
      </android.view.ViewGroup>
    </hierarchy>
    """

    class FakeElement:
        rect = {"x": 0, "y": 562, "width": 1050, "height": 150}

        def click(self):
            events.append("click")

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "ancestor::android.view.ViewGroup" in xpath:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: page_source)
    monkeypatch.setattr(activity.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(activity, "_android_adb_tap", lambda driver, x, y: events.append(("adb-tap", x, y)) or True)

    assert activity._tap_region_search_result(FakeDriver(), "湖南", "张家界市") is True
    assert ("mobile: tap", {"x": 966.0, "y": 637.0}) in events
    assert ("adb-tap", 981, 637) in events


def test_activity_region_selected_rejects_open_search_drawer():
    page_source = "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"

    assert activity._activity_region_selected(page_source, "湖南", "张家界市") is False


def test_select_activity_region_prefers_city_search_result(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市"}

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: events.append(("open", text)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])

    def fake_wait_until(predicate, timeout):
        events.append(("wait", timeout))
        return predicate()

    def fake_search_region_drawer(driver, query):
        events.append(("search", query))
        if query == "张家界":
            state["page"] = "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"
        return True

    def fake_tap_region_search_result(driver, province, city):
        events.append(("tap-search-result", province, city))
        state["page"] = "发布活动 所属省份 湖南省 城市名称 张家界市"
        return True

    monkeypatch.setattr(activity, "_search_region_drawer", fake_search_region_drawer)
    monkeypatch.setattr(activity, "_tap_region_search_result", fake_tap_region_search_result)
    monkeypatch.setattr(activity, "_select_province_from_open_region_drawer", lambda driver, province: events.append(("province", province)) or True)
    monkeypatch.setattr(activity, "_select_city_from_open_region_drawer", lambda driver, city: events.append(("city", city)) or True)
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: events.append(("tap", text)) or False)

    activity._select_activity_region(object(), "湖南", "张家界市")

    assert ("search", "张家界") in events
    assert ("tap-search-result", "湖南", "张家界市") in events
    assert not any(event[0] == "province" for event in events)


def test_select_activity_region_prefers_visible_recent_city_before_search(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 最近选择 张家界 确认地区"}

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: events.append(("open", text)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(activity, "_search_region_drawer", lambda driver, query: events.append(("search", query)) or True)

    def fake_tap_region_option(driver, texts, timeout=2):
        events.append(("tap-option", tuple(texts)))
        return "张家界" in texts

    def fake_tap_text(driver, text, timeout=1):
        events.append(("tap", text))
        if text == "确认地区":
            state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"
            return True
        return False

    monkeypatch.setattr(activity, "_tap_region_option", fake_tap_region_option)
    monkeypatch.setattr(activity, "tap_text_if_present", fake_tap_text)

    activity._select_activity_region(object(), "湖南", "张家界市")

    assert events == [
        ("open", "选择所属省份"),
        ("tap-option", ("张家界市", "张家界")),
        ("tap", "确认地区"),
    ]


def test_select_region_from_search_results_submits_android_keyboard_before_tapping(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市"}

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

    def fake_search(driver, query):
        events.append(("search", query))
        state["page"] = "选择地区 搜索省份或城市 张家界"
        return True

    def fake_submit(driver):
        events.append("enter")
        state["page"] = "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"
        return True

    def fake_tap_result(driver, province, city):
        events.append(("tap-result", province, city))
        state["page"] = "发布活动 所属省份 湖南省 城市名称 张家界市"
        return True

    monkeypatch.setattr(activity, "_search_region_drawer", fake_search)
    monkeypatch.setattr(activity, "_android_submit_region_search", fake_submit)
    monkeypatch.setattr(activity, "_tap_region_search_result", fake_tap_result)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())

    assert activity._select_region_from_search_results(FakeDriver(), "湖南", "张家界市") is True
    assert events == [
        ("search", "张家界"),
        "enter",
        ("tap-result", "湖南", "张家界市"),
    ]


def test_select_activity_region_on_android_uses_ios_style_confirm_after_ignored_search_result(monkeypatch):
    events = []
    state = {"page": "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市 确认地区"}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: events.append(("open", text)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: True)
    monkeypatch.setattr(activity, "_select_region_from_search_results", lambda driver, province, city: False)
    monkeypatch.setattr(
        activity,
        "_tap_region_option",
        lambda driver, texts, timeout=2: events.append(("option", tuple(texts))) or "张家界" in texts,
    )

    def fake_tap_text(driver, text, timeout=1):
        events.append(("tap", text))
        if text == "确认地区":
            state["page"] = "发布活动 所属省份 湖南省 城市名称 张家界市"
            return True
        return False

    monkeypatch.setattr(activity, "tap_text_if_present", fake_tap_text)

    activity._select_activity_region(FakeDriver(), "湖南", "张家界市")

    assert ("option", ("张家界市", "张家界")) in events
    assert ("tap", "确认地区") in events


def test_region_drawer_visible_accepts_android_displayed_attribute(monkeypatch):
    page_source = """
    <hierarchy>
      <android.widget.TextView text="选择地区" displayed="true" bounds="[42,194][1007,256]" />
      <android.widget.EditText text="搜索省份或城市" hint="搜索省份或城市" displayed="true" bounds="[140,299][978,389]" />
    </hierarchy>
    """

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: page_source)

    assert activity._region_drawer_is_visible(object()) is True


def test_search_region_drawer_uses_android_adb_text_when_send_keys_does_not_update_page(monkeypatch):
    events = []
    state = {"typed": False}

    class FakeSearchInput:
        def click(self):
            events.append("click-search")

        def clear(self):
            events.append("clear-search")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "搜索省份或城市" in xpath:
                return FakeSearchInput()
            raise activity.NoSuchElementException("missing")

    def fake_wait_until(predicate, timeout):
        events.append(("wait", timeout))
        return predicate()

    def fake_page_source(driver):
        if state["typed"]:
            return "选择地区 搜索省份或城市 搜索结果 张家界 湖南省 · 张家界市"
        return "选择地区 搜索省份或城市"

    def fake_android_adb_input_text(driver, value):
        events.append(("adb-text", value))
        if value == "张家界":
            state["typed"] = True
            return True
        return False

    monkeypatch.setattr(activity, "_safe_page_source", fake_page_source)
    monkeypatch.setattr(activity, "_wait_until", fake_wait_until)
    monkeypatch.setattr(activity, "_android_adb_input_text", fake_android_adb_input_text, raising=False)

    assert activity._search_region_drawer(FakeDriver(), "张家界") is True
    assert ("send-keys", "张家界") in events
    assert ("adb-text", "张家界") in events


def test_search_region_drawer_returns_false_when_android_text_input_never_takes(monkeypatch):
    events = []

    class FakeSearchInput:
        def click(self):
            events.append("click-search")

        def clear(self):
            events.append("clear-search")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

        def find_element(self, _by, xpath):
            if "搜索省份或城市" in xpath:
                return FakeSearchInput()
            raise activity.NoSuchElementException("missing")

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "选择地区 搜索省份或城市")
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: events.append(("wait", timeout)) or predicate())
    monkeypatch.setattr(
        activity,
        "_android_adb_input_text",
        lambda driver, value: events.append(("adb-text", value)) or False,
        raising=False,
    )

    assert activity._search_region_drawer(FakeDriver(), "张家界") is False


def test_select_activity_region_retries_android_field_container_when_drawer_does_not_open(monkeypatch):
    events = []
    state = {"page": "发布活动 所属省份 选择所属省份 城市名称 例如：杭州"}

    class FakeElement:
        rect = {"x": 42, "y": 1465, "width": 585, "height": 137}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "ancestor::android.view.ViewGroup" in xpath:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

        def execute_script(self, script, payload):
            events.append((script, payload))
            state["page"] = "选择地区 搜索省份或城市"

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: events.append(("open", text)) or True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: events.append(("wait", timeout)) or predicate())
    def fake_select_region_from_search_results(driver, province, city):
        events.append(("search-result", province, city))
        state["page"] = "发布活动 所属省份 湖南 城市名称 张家界市"
        return True

    monkeypatch.setattr(activity, "_select_region_from_search_results", fake_select_region_from_search_results)
    monkeypatch.setattr(
        activity,
        "_select_province_from_open_region_drawer",
        lambda driver, province: events.append(("province", province)) or True,
    )
    monkeypatch.setattr(
        activity,
        "_select_city_from_open_region_drawer",
        lambda driver, city: events.append(("city", city)) or True,
    )

    activity._select_activity_region(FakeDriver(), "湖南", "张家界市")

    assert any(event[0] == "mobile: tap" for event in events if isinstance(event, tuple))
    assert ("search-result", "湖南", "张家界市") in events
    assert ("province", "湖南") not in events
    assert ("city", "张家界市") not in events


def test_select_activity_region_does_not_accept_unclosed_region_drawer(monkeypatch):
    state = {"page": "选择地区 搜索省份或城市 当前选择地区 暂未选择地区 C 重庆"}

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(activity, "_select_region_from_search_results", lambda driver, province, city: False)
    monkeypatch.setattr(activity, "_select_province_from_open_region_drawer", lambda driver, province: True)
    monkeypatch.setattr(activity, "_select_city_from_open_region_drawer", lambda driver, city: True)
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: text == "确认地区")
    monkeypatch.setattr(activity, "_tap_region_search_result", lambda driver, province, city: False)

    with pytest.raises(AssertionError, match="Unable to confirm the activity region selection"):
        activity._select_activity_region(object(), "湖南", "张家界市")


def test_tap_region_option_prefers_exact_ios_visible_static_text(monkeypatch):
    taps = []

    class FakeElement:
        rect = {"x": 13, "y": 788, "width": 304, "height": 19}

        def is_displayed(self):
            return True

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, xpath):
            assert 'contains(' not in xpath
            assert '@name="重庆"' in xpath
            return [FakeElement()]

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=1: False)

    assert activity._tap_region_option(FakeDriver(), ["重庆"]) is True
    assert taps == [("mobile: tap", {"x": 165.0, "y": 797.5})]


def test_dismiss_region_search_keyboard_does_not_back_out_of_ios_drawer():
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def hide_keyboard(self, **kwargs):
            events.append(("hide", kwargs))
            raise activity.WebDriverException("keyboard command unavailable")

        def back(self):
            events.append("back")

    activity._dismiss_region_search_keyboard(FakeDriver())

    assert "back" not in events


def test_region_drawer_visible_requires_visible_search_field(monkeypatch):
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText visible="true" name="选择所属省份" label="选择所属省份" value="选择所属省份" />
      <XCUIElementTypeStaticText visible="false" name="搜索省份或城市" label="搜索省份或城市" value="搜索省份或城市" />
      <XCUIElementTypeStaticText visible="false" name="选择地区" label="选择地区" value="选择地区" />
    </AppiumAUT>
    """

    class FakeDriver:
        pass

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: page_source)

    assert activity._region_drawer_is_visible(FakeDriver()) is False


def test_select_activity_region_fails_when_fallback_does_not_select_values(monkeypatch):
    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "发布活动 所属省份 选择所属省份 城市名称 例如：杭州")
    monkeypatch.setattr(activity, "_wait_until", lambda predicate, timeout: False)
    monkeypatch.setattr(activity, "_choose_specific_overlay_option", lambda driver, texts: False)
    monkeypatch.setattr(activity, "_fill_city", lambda driver, city: None)

    with pytest.raises(AssertionError, match="Unable to select activity region"):
        activity._select_activity_region(object(), "湖南", "张家界市")


def test_tap_form_field_uses_mobile_tap_on_android_text_center(monkeypatch):
    events = []

    class FakeElement:
        rect = {"x": 84, "y": 1501, "width": 448, "height": 65}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "选择所属省份" in xpath:
                return FakeElement()
            raise activity.NoSuchElementException("missing")

        def execute_script(self, name, payload):
            events.append((name, payload))

    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=0.5: events.append(("text-click", text)) or False)

    assert activity._tap_form_field(FakeDriver(), "选择所属省份") is True
    assert ("mobile: tap", {"x": 308.0, "y": 1533.5}) in events


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


def test_tap_submit_button_center_reads_android_text_attribute():
    queries = []
    taps = []

    class FakeElement:
        rect = {"x": 752, "y": 2573, "width": 196, "height": 65}

    class FakeDriver:
        def find_elements(self, by, value):
            queries.append(value)
            return [FakeElement()]

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert activity._tap_submit_button_center(FakeDriver()) is True
    assert '@text="提交审核"' in queries[0]
    assert taps == [("mobile: tap", {"x": 850.0, "y": 2605.5})]


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


def test_select_province_searches_new_region_drawer(monkeypatch):
    events = []
    state = {"query": ""}

    class FakeSearchInput:
        def click(self):
            events.append("click-search")

        def clear(self):
            events.append("clear-search")

        def send_keys(self, value):
            events.append(("search", value))
            state["query"] = value

    class FakeDriver:
        def find_element(self, _by, xpath):
            events.append(("find", xpath))
            if "搜索省份或城市" in xpath:
                return FakeSearchInput()
            raise activity.NoSuchElementException("missing")

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: f"选择地区 搜索省份或城市 {state['query']}")
    monkeypatch.setattr(
        activity,
        "_choose_specific_overlay_option",
        lambda driver, texts: events.append(("fallback", texts)) or False,
    )
    monkeypatch.setattr(
        activity,
        "tap_text_if_present",
        lambda driver, text, timeout=1: events.append(("tap", text)) or (text == "湖南" and ("search", "湖南") in events),
    )
    monkeypatch.setattr(activity, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))

    activity._select_province(FakeDriver(), "湖南")

    assert ("search", "湖南") in events
    assert ("tap", "湖南") in events
    assert not any(event == ("fallback", ["湖南", "湖南市", "湖南省"]) for event in events)


def test_select_province_waits_for_region_drawer_before_scroll_fallback(monkeypatch):
    events = []
    page_sources = iter(["发布活动 选择所属省份", "选择地区 搜索省份或城市"])

    class FakeSearchInput:
        def click(self):
            events.append("click-search")

        def clear(self):
            events.append("clear-search")

        def send_keys(self, value):
            events.append(("search", value))

    class FakeDriver:
        def find_element(self, _by, xpath):
            if "搜索省份或城市" in xpath:
                return FakeSearchInput()
            raise activity.NoSuchElementException("missing")

    def fake_wait_until(predicate, timeout):
        events.append(("wait", timeout))
        return predicate()

    monkeypatch.setattr(activity, "_tap_form_field", lambda driver, text, fallback_point=None: True)
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: next(page_sources, "选择地区 搜索省份或城市 湖南 确认地区"))
    monkeypatch.setattr(activity, "_wait_until", fake_wait_until)
    monkeypatch.setattr(
        activity,
        "_choose_specific_overlay_option",
        lambda driver, texts: events.append(("fallback", texts)) or False,
    )
    monkeypatch.setattr(
        activity,
        "tap_text_if_present",
        lambda driver, text, timeout=1: events.append(("tap", text)) or (text == "湖南" and ("search", "湖南") in events),
    )
    monkeypatch.setattr(activity, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))

    activity._select_province(FakeDriver(), "湖南")

    assert ("wait", 3) in events
    assert ("search", "湖南") in events
    assert not any(event == ("fallback", ["湖南", "湖南市", "湖南省"]) for event in events)


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


def test_tap_image_picker_uses_visible_ios_card_center_when_shifted_by_error_banner(monkeypatch):
    taps = []
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText value="Network Error" name="Network Error" visible="true" x="27" y="138" width="348" height="21" />
      <XCUIElementTypeStaticText value="活动图片" name="活动图片" visible="true" x="13" y="181" width="61" height="21" />
      <XCUIElementTypeOther enabled="true" visible="true" x="13" y="214" width="94" height="94">
        <XCUIElementTypeOther enabled="true" visible="true" x="45" y="246" width="26" height="26" />
      </XCUIElementTypeOther>
    </AppiumAUT>
    """

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def __init__(self):
            self.page_source = page_source

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert activity._tap_image_picker(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 60, "y": 261})]


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
