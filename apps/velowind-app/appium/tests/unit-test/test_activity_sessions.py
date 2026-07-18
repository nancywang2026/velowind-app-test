from datetime import date

from velowind_appium.modules import activity_sessions


class FakeDriver:
    def __init__(self, page_source="", *, width=402, height=874):
        self.page_source = page_source
        self.width = width
        self.height = height
        self.scripts = []
        self.capabilities = {"platformName": "Android"}

    def get_window_rect(self):
        return {"width": self.width, "height": self.height}

    def execute_script(self, script, payload):
        self.scripts.append((script, payload))


class FakeElement:
    def __init__(self, rect):
        self.rect = rect


class FakeWheel:
    def __init__(self, *, on_send_keys=None):
        self.clicked = False
        self.sent_keys = []
        self.on_send_keys = on_send_keys

    def click(self):
        self.clicked = True

    def send_keys(self, value):
        self.sent_keys.append(value)
        if self.on_send_keys is not None:
            self.on_send_keys(value)


def test_tap_session_datetime_field_prefers_the_field_container(monkeypatch):
    driver = FakeDriver("新增场次 报名截止时间 活动名额 开始时间 结束时间")
    tapped = []

    def fake_find_element(by, xpath):
        tapped.append((by, xpath))
        return FakeElement({"x": 42, "y": 753, "width": 585, "height": 138})

    monkeypatch.setattr(driver, "find_element", fake_find_element, raising=False)

    assert activity_sessions._tap_session_datetime_field(driver, "报名截止时间") is True
    assert tapped
    assert driver.scripts == [("mobile: tap", {"x": 334.5, "y": 822.0})]


def test_write_android_datetime_picker_value_only_adjusts_day_and_confirms(monkeypatch):
    current = {"month": "07", "day": "18", "hour": "10", "minute": "17"}
    driver = FakeDriver("已选择时间 07.18 10:17 取消 确认 月 日 时 分 报名截止时间", width=1280, height=2856)

    def update_page_source():
        driver.page_source = (
            f"已选择时间 {current['month']}.{current['day']} "
            f"{current['hour']}:{current['minute']} 取消 确认 月 日 时 分 报名截止时间"
        )

    tapped = []
    confirmed = []

    def fake_tap(driver, field, direction):
        tapped.append((field, direction))
        if field == "day":
            current["day"] = "23"
        update_page_source()

    monkeypatch.setattr(activity_sessions, "_tap_android_datetime_picker_wheel_step", fake_tap)
    monkeypatch.setattr(activity_sessions, "_confirm_session_picker", lambda driver: confirmed.append(True))

    assert activity_sessions._write_android_datetime_picker_value(driver, "报名截止时间", "2026-07-23 18:00") is True
    assert tapped == [("day", "next")]
    assert confirmed == [True]


def test_write_android_datetime_picker_value_confirms_even_when_day_readback_does_not_change(monkeypatch):
    driver = FakeDriver("已选择时间 07.18 10:17 取消 确认 月 日 时 分 报名截止时间", width=1280, height=2856)
    confirmed = []

    monkeypatch.setattr(activity_sessions, "_fill_android_datetime_picker_wheels", lambda *args, **kwargs: False)
    monkeypatch.setattr(activity_sessions, "_confirm_session_picker", lambda driver: confirmed.append(True))

    assert activity_sessions._write_android_datetime_picker_value(driver, "报名截止时间", "2026-07-23 18:00") is True
    assert confirmed == [True]


def test_android_datetime_picker_wheel_locators_try_id_then_xpath():
    locators = activity_sessions._android_datetime_picker_wheel_locators(
        "activity-session-create-deadline-picker-month-wheel"
    )

    assert locators == [
        (activity_sessions.AppiumBy.ID, "activity-session-create-deadline-picker-month-wheel"),
        (
            activity_sessions.AppiumBy.XPATH,
            '//*[@resource-id="activity-session-create-deadline-picker-month-wheel"]',
        ),
        (
            activity_sessions.AppiumBy.XPATH,
            '//*[@resource-id="activity-session-create-deadline-picker-month-wheel"]/android.widget.ScrollView[1]',
        ),
    ]


def test_android_datetime_picker_current_parts_reads_selected_time():
    driver = FakeDriver("报名截止时间 已选择时间 07.18 10:17 月 日 时 分")

    assert activity_sessions._android_datetime_picker_current_parts(driver) == {
        "month": "07",
        "day": "18",
        "hour": "10",
        "minute": "17",
    }


def test_confirm_session_picker_taps_bottom_right_confirm_area_first(monkeypatch):
    driver = FakeDriver("报名截止时间 已选择时间 07.18 10:17 取消 确认 月 日 时 分", width=1280, height=2856)
    text_taps = []

    monkeypatch.setattr(activity_sessions, "tap_text_if_present", lambda driver, text, timeout=0.5: text_taps.append(text) or False)

    assert activity_sessions._confirm_session_picker(driver) is True
    assert driver.scripts == [("mobile: tap", {"x": 960, "y": 2656})]
    assert text_taps == []


def test_fill_android_datetime_picker_wheels_drags_when_direct_set_does_not_change_value(monkeypatch):
    driver = FakeDriver("已选择时间 07.18 10:17 月 日 时 分", width=1280, height=2856)
    calls = []
    current = {"month": "07"}

    monkeypatch.setattr(activity_sessions, "_android_datetime_picker_current_parts", lambda received: dict(current))
    monkeypatch.setattr(
        activity_sessions,
        "_tap_android_datetime_picker_wheel_step",
        lambda received, field, direction: calls.append((field, direction)) or current.update(month="08"),
    )

    assert activity_sessions._fill_android_datetime_picker_wheels(
        driver,
        {"month": "activity-session-create-deadline-picker-month-wheel"},
        ["month"],
        {"month": "08"},
    ) is True
    assert calls == [("month", "next")]


def test_fill_android_datetime_picker_wheels_prefers_direct_day_set(monkeypatch):
    driver = FakeDriver("已选择时间 07.18 10:17 月 日 时 分", width=1280, height=2856)
    calls = []
    current = {"day": "18"}

    def fake_set(received, wheel_id, field, value):
        calls.append((wheel_id, field, value))
        current[field] = value
        return True

    monkeypatch.setattr(activity_sessions, "_android_datetime_picker_current_parts", lambda received: dict(current))
    monkeypatch.setattr(activity_sessions, "_set_android_datetime_picker_wheel_value", fake_set)
    monkeypatch.setattr(activity_sessions, "_drag_android_datetime_picker_wheel_to_target", lambda *args, **kwargs: calls.append(("drag",)) or False)

    assert activity_sessions._fill_android_datetime_picker_wheels(
        driver,
        {"day": "activity-session-create-deadline-picker-day-wheel"},
        ["day"],
        {"day": "23"},
    ) is True
    assert calls == [("activity-session-create-deadline-picker-day-wheel", "day", "23")]


def test_build_activity_session_draft_uses_required_relative_dates():
    draft = activity_sessions.build_activity_session_draft(today=date(2026, 7, 17))

    assert draft.signup_deadline == "2026-07-22 18:00"
    assert draft.start_time == "2026-07-22 09:00"
    assert draft.end_time == "2026-07-27 18:00"
    assert draft.meeting_point == "张家界景区"
    assert draft.max_participants == "20"
    assert draft.fee == "0.01"
    assert draft.contact_name == "张家界大环线领队"
    assert draft.contact_phone == "13800138000"
    assert draft.notes == "保险"


def test_session_flow_does_not_force_home_when_already_on_my_page():
    assert activity_sessions._session_flow_is_already_open("我的笔记 我的活动 我的租车 我的卡券")
    assert activity_sessions._session_flow_is_already_open("我的活动 发布 显示下架活动")
    assert not activity_sessions._session_flow_is_already_open("首页 活动 消息 我的")


def test_add_activity_session_retries_current_page_when_home_recovery_fails(monkeypatch):
    driver = object()
    draft = activity_sessions.build_activity_session_draft(today=date(2026, 7, 18))
    config = object()
    events = []
    attempts = {"open": 0}

    def fake_open_my_activity(driver, timeout=30):
        attempts["open"] += 1
        events.append(("open", attempts["open"]))
        if attempts["open"] == 1:
            raise AssertionError("first navigation failed")

    monkeypatch.setattr(activity_sessions, "dismiss_common_system_alerts", lambda received: events.append("dismiss"))
    monkeypatch.setattr(activity_sessions, "open_my_activity_publish_list", fake_open_my_activity)
    monkeypatch.setattr(activity_sessions, "ensure_logged_in_on_home", lambda *args, **kwargs: events.append("ensure-home") or (_ for _ in ()).throw(RuntimeError("home timeout")))
    monkeypatch.setattr(activity_sessions, "open_manage_sessions_for_approved_activity", lambda *args, **kwargs: events.append("manage"))
    monkeypatch.setattr(activity_sessions, "open_create_session_form", lambda *args, **kwargs: events.append("create"))
    monkeypatch.setattr(activity_sessions, "fill_session_form", lambda *args, **kwargs: events.append("fill"))
    monkeypatch.setattr(activity_sessions, "submit_session_form", lambda *args, **kwargs: "创建成功")

    assert activity_sessions.add_activity_session(driver, draft, config) == "创建成功"

    assert events == ["dismiss", ("open", 1), "ensure-home", ("open", 2), "manage", "create", "fill"]


def test_fill_session_form_requires_each_visible_field(monkeypatch):
    draft = activity_sessions.build_activity_session_draft(today=date(2026, 7, 17))
    filled = []

    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: "新增场次 场次名称 报名截止 开始时间 结束时间")
    monkeypatch.setattr(
        activity_sessions,
        "_fill_session_field",
        lambda driver, keywords, value: filled.append((keywords[0], value)) or True,
    )
    monkeypatch.setattr(
        activity_sessions,
        "_fill_session_datetime_field",
        lambda driver, keywords, value: filled.append((keywords[0], value)) or True,
    )
    monkeypatch.setattr(
        activity_sessions,
        "_fill_session_location_field",
        lambda driver, keywords, value: filled.append((keywords[0], value)) or True,
    )

    activity_sessions.fill_session_form(object(), draft)

    assert filled == [
        ("场次展示文案", draft.title),
        ("报名截止时间", draft.signup_deadline),
        ("活动名额", draft.max_participants),
        ("开始时间", draft.start_time),
        ("结束时间", draft.end_time),
        ("集合地点", draft.meeting_point),
        ("金额", draft.fee),
        ("配套服务", draft.notes),
    ]


def test_fill_session_form_uses_special_datetime_helper_for_dates(monkeypatch):
    draft = activity_sessions.build_activity_session_draft(today=date(2026, 7, 17))
    calls = []

    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: "新增场次 场次展示文案 报名截止时间 活动名额 开始时间 结束时间 集合地点 金额 配套服务")
    monkeypatch.setattr(activity_sessions, "_fill_session_field", lambda driver, keywords, value: calls.append(("field", keywords[0], value)) or True)
    monkeypatch.setattr(activity_sessions, "_fill_session_datetime_field", lambda driver, keywords, value: calls.append(("datetime", keywords[0], value)) or True)
    monkeypatch.setattr(activity_sessions, "_fill_session_location_field", lambda driver, keywords, value: calls.append(("location", keywords[0], value)) or True)

    activity_sessions.fill_session_form(object(), draft)

    assert calls == [
        ("field", "场次展示文案", draft.title),
        ("datetime", "报名截止时间", draft.signup_deadline),
        ("field", "活动名额", draft.max_participants),
        ("datetime", "开始时间", draft.start_time),
        ("datetime", "结束时间", draft.end_time),
        ("location", "集合地点", draft.meeting_point),
        ("field", "金额", draft.fee),
        ("field", "配套服务", draft.notes),
    ]


def test_fill_session_form_resets_scroll_to_top_before_filling(monkeypatch):
    draft = activity_sessions.build_activity_session_draft(today=date(2026, 7, 17))
    events = []

    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: "新增场次 场次展示文案 报名截止时间 活动名额 开始时间 结束时间 集合地点 金额 配套服务")
    monkeypatch.setattr(activity_sessions.activity, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))
    monkeypatch.setattr(activity_sessions, "swipe_vertical", lambda driver, direction="up": events.append(("swipe", direction)))
    monkeypatch.setattr(activity_sessions, "_fill_session_field", lambda driver, keywords, value: events.append(("field", keywords[0])) or True)
    monkeypatch.setattr(activity_sessions, "_fill_session_datetime_field", lambda driver, keywords, value: events.append(("datetime", keywords[0])) or True)
    monkeypatch.setattr(activity_sessions, "_fill_session_location_field", lambda driver, keywords, value: events.append(("location", keywords[0])) or True)

    activity_sessions.fill_session_form(object(), draft)

    assert events[:4] == [
        "hide-keyboard",
        ("swipe", "down"),
        ("swipe", "down"),
        ("swipe", "down"),
    ]


def test_fill_session_location_field_does_not_reopen_when_modal_is_visible(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点")
    events = []

    monkeypatch.setattr(activity_sessions.activity, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))
    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: "集合地点 搜索地点")
    monkeypatch.setattr(activity_sessions, "_session_location_modal_visible", lambda page_source: True)
    monkeypatch.setattr(activity_sessions, "_tap_session_location_field", lambda driver, keywords, placeholders: events.append("tap-entry") or True)
    monkeypatch.setattr(activity_sessions, "_choose_session_location", lambda driver, value: events.append(("choose", value)) or False)
    monkeypatch.setattr(activity_sessions, "swipe_vertical", lambda driver, direction="up": events.append(("swipe", direction)))

    assert activity_sessions._fill_session_location_field(driver, ["集合地点"], "张家界景区") is False

    assert events == [
        "hide-keyboard",
        ("choose", "张家界景区"),
    ]


def test_tap_session_location_field_requires_location_modal_to_open(monkeypatch):
    driver = FakeDriver("新增场次 集合地点 点击选择或搜索集合地点", width=1280, height=2856)
    events = []

    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda received: driver.page_source)
    monkeypatch.setattr(activity_sessions.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        activity_sessions,
        "tap_text_if_present",
        lambda received, text, timeout=0.5: events.append(("tap-text", text)) or True,
    )
    monkeypatch.setattr(
        activity_sessions,
        "_tap_session_location_container",
        lambda received, keyword: events.append(("tap-container", keyword)) or False,
    )

    assert activity_sessions._tap_session_location_field(
        driver,
        ["集合地点"],
        ["点击选择或搜索集合地点"],
    ) is False

    assert ("tap-text", "点击选择或搜索集合地点") in events


def test_choose_session_location_waits_for_picker_to_close_without_pressing_back(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区")
    events = []

    monkeypatch.setattr(activity_sessions, "_search_session_location", lambda driver, value: events.append(("search", value)) or True)
    monkeypatch.setattr(activity_sessions, "_session_location_results_visible", lambda page_source: True)
    monkeypatch.setattr(activity_sessions, "_tap_session_location_result", lambda driver, value: events.append(("tap-result", value)) or True)
    monkeypatch.setattr(activity_sessions, "_session_location_selected", lambda page_source: events.append("selected-check") or True)
    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: driver.page_source)
    monkeypatch.setattr(activity_sessions, "_dismiss_session_location_modal", lambda driver: events.append("dismiss"))

    assert activity_sessions._choose_session_location(driver, "张家界景区") is True

    assert events == [
        ("search", "张家界景区"),
        ("tap-result", "张家界景区"),
        "selected-check",
    ]


def test_choose_session_location_dismisses_picker_when_selection_is_visible_behind_modal(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区")
    events = []
    dismissed = {"value": False}

    monkeypatch.setattr(activity_sessions, "_search_session_location", lambda driver, value: events.append(("search", value)) or True)
    monkeypatch.setattr(activity_sessions, "_session_location_results_visible", lambda page_source: True)
    monkeypatch.setattr(activity_sessions, "_tap_session_location_result", lambda driver, value: events.append(("tap-result", value)) or True)
    monkeypatch.setattr(
        activity_sessions,
        "_session_location_selected",
        lambda page_source: events.append("selected-check") or dismissed["value"],
    )
    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: driver.page_source)
    monkeypatch.setattr(activity_sessions, "_wait_until", lambda predicate, timeout=5: predicate())

    def fake_dismiss(driver):
        events.append("dismiss")
        dismissed["value"] = True

    monkeypatch.setattr(activity_sessions, "_dismiss_session_location_modal", fake_dismiss)

    assert activity_sessions._choose_session_location(driver, "张家界景区") is True

    assert events == [
        ("search", "张家界景区"),
        ("tap-result", "张家界景区"),
        "selected-check",
        "dismiss",
        "selected-check",
    ]


def test_session_location_selected_requires_create_form_to_still_be_visible():
    assert not activity_sessions._session_location_selected("管理场次 张家界大环线2天1晚 当前还没有场次")


def test_session_location_modal_visible_does_not_match_plain_form_input():
    page_source = '新增场次 集合地点 <android.widget.EditText input-type="16385" text="自动化场次" />'

    assert activity_sessions._session_location_modal_visible(page_source) is False


def test_session_location_modal_visible_matches_search_drawer_without_title_text():
    page_source = '<android.widget.EditText text="搜索地点" hint="搜索地点" /> 未获取到当前位置，请输入关键词搜索地点'

    assert activity_sessions._session_location_modal_visible(page_source) is True


def test_session_location_results_visible_waits_for_search_results():
    page_source = '<android.widget.EditText text="搜索地点" hint="搜索地点" /> 未获取到当前位置，请输入关键词搜索地点'

    assert activity_sessions._session_location_results_visible(page_source) is False


def test_tap_session_location_result_prefers_second_title_center(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区", width=1280, height=2856)

    def fake_find_elements(by, xpath):
        if "android.widget.TextView[1]" in xpath:
            return [
                FakeElement({"x": 278, "y": 390, "width": 954, "height": 66}),
                FakeElement({"x": 278, "y": 603, "width": 954, "height": 66}),
            ]
        return []

    monkeypatch.setattr(driver, "find_elements", fake_find_elements, raising=False)

    assert activity_sessions._tap_session_location_result(driver, "张家界景区") is True

    assert driver.scripts == [
        ("mobile: tap", {"x": 755.0, "y": 636.0}),
    ]


def test_tap_session_location_result_uses_second_row_coordinate_when_title_locator_fails(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区", width=1280, height=2856)

    def fake_find_elements(by, xpath):
        if "android.widget.TextView[1]" in xpath:
            return []
        if "android.widget.TextView[2]" in xpath:
            return [
            FakeElement({"x": 0, "y": 360, "width": 854, "height": 225}),
            FakeElement({"x": 0, "y": 585, "width": 854, "height": 225}),
            ]
        return []

    monkeypatch.setattr(driver, "find_elements", fake_find_elements, raising=False)
    monkeypatch.setattr(
        activity_sessions.activity,
        "_tap_element_center",
        lambda received_driver, element: received_driver.execute_script("mobile: tap", {"x": 427, "y": 697}),
    )

    assert activity_sessions._tap_session_location_result(driver, "张家界景区") is True

    assert driver.scripts == [
        ("mobile: clickGesture", {"x": 755, "y": 636}),
    ]


def test_submit_session_form_does_not_treat_expected_title_on_create_page_as_success(monkeypatch):
    driver = object()
    page_sources = iter([
        "新增场次 自动化场次 0718 确认创建 集合地点 金额",
        "新增场次 自动化场次 0718 确认创建 集合地点 金额",
    ])

    monkeypatch.setattr(activity_sessions, "_tap_submit", lambda received: True)
    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda received: next(page_sources))
    monkeypatch.setattr(activity_sessions.time, "sleep", lambda seconds: None)

    ticks = iter([0.0, 0.1, 31.0])
    monkeypatch.setattr(activity_sessions.time, "monotonic", lambda: next(ticks))

    try:
        activity_sessions.submit_session_form(driver, expected_title="自动化场次 0718", timeout=30)
    except AssertionError as error:
        assert "did not expose a success signal" in str(error)
    else:
        raise AssertionError("submit_session_form should not accept the draft title alone on the create form")


def test_open_my_activity_publish_list_taps_my_activity_when_already_on_me_page(monkeypatch):
    driver = FakeDriver("Nancy 我的笔记 我的活动 我的租车 我的卡券")
    events = []
    list_page = {"visible": False}

    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda received: driver.page_source)
    monkeypatch.setattr(activity_sessions, "_tap_me_tab", lambda received: events.append("tap-me") or True)
    monkeypatch.setattr(activity_sessions, "_tap_publish_tab", lambda received: events.append("tap-publish") or True)
    monkeypatch.setattr(activity_sessions, "_toggle_show_delisted", lambda received: events.append("toggle-delisted") or True)

    def fake_tap_text(driver, text, timeout=1):
        events.append(("tap-text", text))
        if text == "我的活动":
            list_page["visible"] = True
            driver.page_source = "我的活动 发布 报名 显示下架活动"
            return True
        return False

    monkeypatch.setattr(activity_sessions, "tap_text_if_present", fake_tap_text)
    monkeypatch.setattr(activity_sessions, "_my_activity_list_visible", lambda page_source: list_page["visible"])

    activity_sessions.open_my_activity_publish_list(driver, timeout=1)

    assert events == [
        ("tap-text", "我的活动"),
        "tap-publish",
        "toggle-delisted",
    ]


def test_tap_more_for_approved_activity_uses_right_side_of_top_approved_card(monkeypatch):
    page_source = "我的活动 发布 显示下架活动 张家界大环线2天1晚 通过 未发布"
    driver = FakeDriver(page_source, width=402, height=874)

    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda received: page_source)
    monkeypatch.setattr(activity_sessions, "tap_text_if_present", lambda driver, text, timeout=0.5: False)

    assert activity_sessions._tap_more_for_approved_activity(driver) is True
    assert driver.scripts == [
        ("mobile: tap", {"x": 366, "y": 262}),
    ]
