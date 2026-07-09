from velowind_appium.modules.activity import (
    activity_form_is_visible,
    activity_publish_success_signal,
    build_activity_draft,
    fill_activity_form,
    _fill_title,
    open_activity_publisher,
)
from velowind_appium.modules import activity


def test_build_activity_draft_embeds_timestamp_in_description():
    draft = build_activity_draft()

    assert draft.title == "杭州西湖徒步"
    assert "创建时间：" in draft.description
    assert "自动化测试活动描述" in draft.description


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


def test_open_activity_publisher_does_not_tap_activity_type_before_publish_sheet(monkeypatch):
    events = []

    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "home")
    monkeypatch.setattr(activity, "login_required_from_page_source", lambda page: False)
    monkeypatch.setattr(activity, "activity_form_is_visible", lambda page: False)
    monkeypatch.setattr(activity, "_publish_sheet_visible", lambda driver: (lambda: False))
    monkeypatch.setattr(activity, "_tap_activity_type_if_present", lambda driver: events.append("tap-activity-type") or True)
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: False)

    def fake_tap_publish_entry(driver):
        events.append("tap-publish-entry")
        raise AssertionError("stop-after-publish-entry")

    monkeypatch.setattr(activity, "_tap_publish_entry_if_present", fake_tap_publish_entry)
    monotonic_values = iter([0, 1, 2, 3, 4, 5])
    monkeypatch.setattr(activity.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    try:
        open_activity_publisher(object(), ios_config=object(), timeout=5)
    except AssertionError as exc:
        assert str(exc) == "stop-after-publish-entry"

    assert events == ["tap-publish-entry"]


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

    def fake_tap_activity_type(driver):
        events.append("tap-activity-type")
        if state["page"] == "sheet-hidden":
            state["page"] = "form"
            return True
        return False

    monkeypatch.setattr(activity, "_tap_publish_entry_if_present", fake_tap_publish_entry)
    monkeypatch.setattr(activity, "_tap_activity_type_if_present", fake_tap_activity_type)
    monkeypatch.setattr(activity, "_wait_until", lambda condition, timeout: condition())
    monotonic_values = iter([0, 1, 2, 3, 4, 5])
    monkeypatch.setattr(activity.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(activity.time, "sleep", lambda seconds: None)

    open_activity_publisher(object(), ios_config=object(), timeout=5)

    assert events == ["tap-publish-entry", "tap-activity-type"]


def test_publish_sheet_visible_ignores_bottom_activity_tab(monkeypatch):
    monkeypatch.setattr(activity, "_safe_page_source", lambda driver: "首页 活动 消息 我的")

    assert activity._publish_sheet_visible(object())() is False


def test_fill_activity_form_resolves_picker_placeholders_after_text_fields(monkeypatch):
    events = []
    draft = build_activity_draft()
    state = {"resolved": False}

    monkeypatch.setattr(activity, "wait_for_activity_form", lambda driver, timeout=60: True)
    monkeypatch.setattr(activity, "_upload_activity_image", lambda driver: events.append("upload-image"))
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


def test_upload_activity_image_opens_local_library_before_confirming(monkeypatch):
    calls = []

    monkeypatch.setattr(activity, "_tap_image_picker", lambda driver: True)
    monkeypatch.setattr(activity, "tap_text_if_present", lambda driver, text, timeout=2: calls.append(("tap", text)) or False)
    monkeypatch.setattr(activity, "_choose_photo_library_source", lambda driver: calls.append(("choose-source", None)) or True)
    monkeypatch.setattr(activity, "_choose_local_photo", lambda driver: calls.append(("choose-photo", None)) or True)

    activity._upload_activity_image(object())

    assert ("choose-source", None) in calls
    assert calls[-1] == ("choose-photo", None)
