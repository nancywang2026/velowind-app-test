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

    def tap(self, positions, duration=None):
        self.scripts.append(("w3c tap", {"positions": positions, "duration": duration}))

    def swipe(self, start_x, start_y, end_x, end_y, duration=None):
        self.scripts.append(
            (
                "swipe",
                {
                    "start_x": start_x,
                    "start_y": start_y,
                    "end_x": end_x,
                    "end_y": end_y,
                    "duration": duration,
                },
            )
        )


class FakeElement:
    def __init__(self, rect, *, displayed=True, name=""):
        self.rect = rect
        self.clicked = False
        self.displayed = displayed
        self.name = name

    def click(self):
        self.clicked = True

    def is_displayed(self):
        return self.displayed

    def get_attribute(self, name):
        if name in {"name", "label", "value"}:
            return self.name
        return ""


class FakeTextField:
    def __init__(self, *, displayed, rect, value="搜索地点"):
        self.displayed = displayed
        self.rect = rect
        self.value = value
        self.clicked = False
        self.cleared = False
        self.sent_keys = []

    def is_displayed(self):
        return self.displayed

    def click(self):
        self.clicked = True

    def clear(self):
        self.cleared = True

    def set_value(self, value):
        self.sent_keys.append(("set_value", value))
        self.value = value

    def send_keys(self, value):
        self.sent_keys.append(("send_keys", value))
        self.value = value

    def get_attribute(self, name):
        if name in {"value", "name", "label", "placeholderValue"}:
            return self.value
        return ""


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


class FakePickerValueElement:
    def __init__(self, field, value, rect):
        self.field = field
        self.value = value
        self.rect = rect

    def is_displayed(self):
        return True


class FakeIosPickerDriver(FakeDriver):
    def __init__(self, current):
        super().__init__(width=402, height=874)
        self.capabilities = {"platformName": "iOS"}
        self.current = dict(current)
        self.picker_values = []
        for field, x in [("month", 86), ("day", 201), ("hour", 316)]:
            upper = {"month": 12, "day": 31, "hour": 23}[field]
            start = 0 if field == "hour" else 1
            for value in range(start, upper + 1):
                text = f"{value:02d}"
                self.picker_values.append(
                    FakePickerValueElement(
                        field,
                        text,
                        {"x": x - 14, "y": 420 + value * 12, "width": 28, "height": 22},
                    )
                )

    @property
    def page_source(self):
        return (
            "报名截止时间 2026年 已选择时间 "
            f"{int(self.current['month'])}月{int(self.current['day'])}日 {int(self.current['hour'])}点 "
            "月 01 02 03 04 05 06 07 08 09 10 11 12 "
            "日 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 "
            "时 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 "
            "取消 确认"
        )

    @page_source.setter
    def page_source(self, value):
        self._initial_page_source = value

    def find_elements(self, by, xpath):
        matches = []
        for element in self.picker_values:
            quoted = f'"{element.value}"'
            if quoted in xpath:
                matches.append(element)
        return matches

    def execute_script(self, script, payload):
        super().execute_script(script, payload)
        if script != "mobile: tap":
            return
        x = payload["x"]
        y = payload["y"]
        for element in self.picker_values:
            rect = element.rect
            if rect["x"] <= x <= rect["x"] + rect["width"] and rect["y"] <= y <= rect["y"] + rect["height"]:
                self.current[element.field] = element.value
                return


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


def test_tap_session_datetime_field_uses_ios_calendar_icon_coordinates(monkeypatch):
    driver = FakeDriver("新增场次 报名截止时间 活动名额 开始时间 结束时间", width=402, height=874)
    driver.capabilities = {"platformName": "iOS"}
    container_calls = []

    monkeypatch.setattr(driver, "find_elements", lambda *args: [], raising=False)
    monkeypatch.setattr(
        activity_sessions,
        "_tap_session_datetime_container",
        lambda received, keyword: container_calls.append(keyword) or True,
    )
    monkeypatch.setattr(
        activity_sessions,
        "_safe_page_source",
        lambda received: '<XCUIElementTypePickerWheel value="7月23日"/>',
    )

    assert activity_sessions._tap_session_datetime_field(driver, "报名截止时间") is True

    assert container_calls == []
    assert driver.scripts == [
        ("w3c tap", {"positions": [(177, 268)], "duration": 100}),
    ]


def test_tap_session_datetime_field_clicks_ios_small_field_element(monkeypatch):
    driver = FakeDriver("新增场次 报名截止时间 活动名额 开始时间 结束时间", width=402, height=874)
    driver.capabilities = {"platformName": "iOS"}
    field = FakeElement({"x": 13, "y": 218, "width": 184, "height": 69})

    monkeypatch.setattr(driver, "find_elements", lambda *args: [field], raising=False)
    monkeypatch.setattr(
        activity_sessions,
        "_safe_page_source",
        lambda received: '<XCUIElementTypePickerWheel value="7月23日"/>',
    )

    assert activity_sessions._tap_session_datetime_field(driver, "报名截止时间") is True

    assert field.clicked is True
    assert driver.scripts == []


def test_tap_session_datetime_field_tries_ios_field_points_when_element_click_does_not_open_picker(monkeypatch):
    driver = FakeDriver("新增场次 报名截止时间 活动名额 开始时间 结束时间", width=402, height=874)
    driver.capabilities = {"platformName": "iOS"}
    field = FakeElement({"x": 13, "y": 218, "width": 184, "height": 69})

    monkeypatch.setattr(driver, "find_elements", lambda *args: [field], raising=False)
    monkeypatch.setattr(
        activity_sessions,
        "_safe_page_source",
        lambda received: '<XCUIElementTypePickerWheel value="7月23日"/>' if len(driver.scripts) >= 2 else "新增场次",
    )
    monkeypatch.setattr(activity_sessions, "_wait_until", lambda predicate, timeout=1, interval=0.2: predicate())

    assert activity_sessions._tap_session_datetime_field(driver, "报名截止时间") is True

    assert field.clicked is True
    assert driver.scripts[:2] == [
        ("w3c tap", {"positions": [(177, 268)], "duration": 100}),
        ("w3c tap", {"positions": [(105, 268)], "duration": 100}),
    ]


def test_reset_session_form_to_top_skips_swipes_when_top_fields_visible(monkeypatch):
    driver = FakeDriver("新增场次 场次展示文案 报名截止时间 活动名额 开始时间 结束时间")
    swipes = []

    monkeypatch.setattr(activity_sessions.activity, "_hide_keyboard", lambda received: None)
    monkeypatch.setattr(activity_sessions, "swipe_vertical", lambda *args, **kwargs: swipes.append(kwargs))

    activity_sessions._reset_session_form_to_top(driver)

    assert swipes == []


def test_leave_stale_session_form_keeps_backing_out_until_form_is_gone(monkeypatch):
    class StaleFormDriver(FakeDriver):
        def __init__(self):
            super().__init__("新增场次 场次展示文案 报名截止时间 活动名额")
            self.back_count = 0

        def press_keycode(self, keycode):
            self.back_count += 1
            if self.back_count >= 2:
                self.page_source = "场次管理 自动化场次 0719"

    driver = StaleFormDriver()
    taps = []

    monkeypatch.setattr(activity_sessions, "tap_text_if_present", lambda received, text, timeout=0.5: taps.append(text) or False)

    activity_sessions._leave_stale_session_form(driver)

    assert driver.back_count == 2
    assert activity_sessions._session_form_visible(driver.page_source) is False


def test_fill_session_form_does_not_accept_stale_android_datetime_value(monkeypatch):
    draft = activity_sessions.build_activity_session_draft(today=date(2026, 7, 20))
    driver = FakeDriver("新增场次 场次展示文案 报名截止时间 07.08 10:38 活动名额 开始时间 结束时间")
    events = []

    monkeypatch.setattr(activity_sessions, "_reset_session_form_to_top", lambda received: None)
    monkeypatch.setattr(activity_sessions, "_is_android_driver", lambda received: True)
    monkeypatch.setattr(activity_sessions, "_fill_session_field", lambda *args, **kwargs: True)
    monkeypatch.setattr(activity_sessions, "_fill_session_location_field", lambda *args, **kwargs: True)
    monkeypatch.setattr(activity_sessions, "_fill_session_datetime_field", lambda *args, **kwargs: False)
    monkeypatch.setattr(activity_sessions, "_dismiss_session_datetime_picker", lambda received: events.append("dismiss-picker"))

    try:
        activity_sessions.fill_session_form(driver, draft)
    except AssertionError as error:
        assert str(error) == "Unable to fill activity session field: 报名截止时间"
    else:
        raise AssertionError("fill_session_form accepted a stale Android datetime value")

    assert events == ["dismiss-picker"]


def test_write_android_datetime_picker_value_adjusts_day_hour_minute_and_confirms(monkeypatch):
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
        elif field == "hour":
            current["hour"] = "18"
        elif field == "minute":
            current["minute"] = "00"
        update_page_source()

    monkeypatch.setattr(activity_sessions, "_tap_android_datetime_picker_wheel_step", fake_tap)
    monkeypatch.setattr(activity_sessions, "_confirm_session_picker", lambda driver: confirmed.append(True) or True)

    assert activity_sessions._write_android_datetime_picker_value(driver, "报名截止时间", "2026-07-23 18:00") is True
    assert tapped == [("day", "next"), ("hour", "next"), ("minute", "previous")]
    assert confirmed == [True]


def test_write_android_datetime_picker_value_rejects_current_picker_value_when_wheel_write_fails(monkeypatch):
    driver = FakeDriver("已选择时间 07.18 10:17 取消 确认 月 日 时 分 报名截止时间", width=1280, height=2856)
    dismissed = []

    monkeypatch.setattr(activity_sessions, "_fill_android_datetime_picker_wheels", lambda *args, **kwargs: False)
    monkeypatch.setattr(activity_sessions, "_dismiss_session_datetime_picker", lambda received: dismissed.append(True))

    assert activity_sessions._write_android_datetime_picker_value(driver, "报名截止时间", "2026-07-23 18:00") is False
    assert dismissed == [True]


def test_write_android_end_time_adjusts_day_hour_and_minute(monkeypatch):
    driver = FakeDriver("已选择时间 07.18 10:17 取消 确认 月 日 时 分 结束时间", width=1280, height=2856)
    captured = []
    confirmed = []

    def fake_fill(received, wheel_ids, field_order, parts):
        captured.append((field_order, parts))
        return True

    monkeypatch.setattr(activity_sessions, "_fill_android_datetime_picker_wheels", fake_fill)
    monkeypatch.setattr(activity_sessions, "_confirm_session_picker", lambda received: confirmed.append(True))

    assert activity_sessions._write_android_datetime_picker_value(driver, "结束时间", "2026-07-29 18:00") is True
    assert captured == [(["day", "hour", "minute"], {"month": "07", "day": "29", "hour": "18", "minute": "00"})]
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


def test_android_datetime_picker_current_parts_prefers_selected_time_over_background_form_values():
    driver = FakeDriver("报名截止时间 07.24 22:22 开始时间 07.24 22:22 已选择时间 07.10 22:22 取消 确认 月 日 时 分")

    assert activity_sessions._android_datetime_picker_current_parts(driver) == {
        "month": "07",
        "day": "10",
        "hour": "22",
        "minute": "22",
    }


def test_ios_datetime_picker_visible_accepts_custom_session_picker():
    page_source = "报名截止时间 已选择时间 7月18日 22点 取消 确认 月 日 时"

    assert activity_sessions._ios_datetime_picker_visible(page_source) is True


def test_ios_datetime_picker_current_parts_reads_selected_time():
    page_source = "报名截止时间 已选择时间 7月18日 22点 取消 确认 月 日 时"

    assert activity_sessions._ios_datetime_picker_current_parts_from_source(page_source) == {
        "month": "07",
        "day": "18",
        "hour": "22",
        "minute": "00",
    }


def test_write_session_datetime_value_routes_ios_picker_to_ios_writer(monkeypatch):
    driver = FakeDriver("报名截止时间 已选择时间 7月18日 22点 取消 确认 月 日 时")
    driver.capabilities = {"platformName": "iOS"}
    calls = []

    monkeypatch.setattr(
        activity_sessions,
        "_write_ios_datetime_picker_value",
        lambda received, keyword, value: calls.append((keyword, value)) or True,
        raising=False,
    )
    monkeypatch.setattr(
        activity_sessions,
        "_write_android_datetime_picker_value",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Android writer should not run for iOS")),
    )

    assert activity_sessions._write_session_datetime_value(driver, "报名截止时间", "2026-07-23 18:00") is True
    assert calls == [("报名截止时间", "2026-07-23 18:00")]


def test_write_session_datetime_value_does_not_route_android_to_ios_writer(monkeypatch):
    driver = FakeDriver("报名截止时间 已选择时间 07.18 10:17 取消 确认 月 日 时 分", width=1280, height=2856)
    calls = []

    monkeypatch.setattr(
        activity_sessions,
        "_write_ios_datetime_picker_value",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("iOS writer should not run for Android")),
        raising=False,
    )
    monkeypatch.setattr(
        activity_sessions,
        "_write_android_datetime_picker_value",
        lambda received, keyword, value: calls.append((keyword, value)) or True,
    )

    assert activity_sessions._write_session_datetime_value(driver, "报名截止时间", "2026-07-23 18:00") is True
    assert calls == [("报名截止时间", "2026-07-23 18:00")]


def test_search_ios_session_location_uses_visible_search_text_field(monkeypatch):
    hidden_title_field = FakeTextField(displayed=False, rect={"x": 13, "y": 140, "width": 376, "height": 42}, value="")
    visible_search_field = FakeTextField(displayed=True, rect={"x": 69, "y": 120, "width": 316, "height": 42})
    driver = FakeDriver("集合地点 搜索地点")
    driver.capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(driver, "find_elements", lambda *args: [hidden_title_field, visible_search_field], raising=False)

    assert activity_sessions._search_ios_session_location(driver, "张家界景区") is True
    assert hidden_title_field.sent_keys == []
    assert visible_search_field.clicked is True
    assert visible_search_field.cleared is True
    assert visible_search_field.sent_keys == [("set_value", "张家界景区")]


def test_tap_ios_session_location_result_taps_first_visible_result(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界国家森林公园")
    driver.capabilities = {"platformName": "iOS"}
    first_result = FakeElement({"x": 52, "y": 175, "width": 350, "height": 71})
    second_result = FakeElement({"x": 52, "y": 246, "width": 350, "height": 71})

    monkeypatch.setattr(driver, "find_elements", lambda *args: [second_result, first_result], raising=False)

    def fake_tap_element_center(received, element):
        rect = element.rect
        driver.execute_script(
            "mobile: tap",
            {"x": rect["x"] + rect["width"] / 2, "y": rect["y"] + rect["height"] / 2},
        )
        driver.page_source = "新增场次 集合地点 张家界国家森林公园"

    monkeypatch.setattr(activity_sessions.activity, "_tap_element_center", fake_tap_element_center)

    assert activity_sessions._tap_ios_session_location_result(driver, "张家界景区") is True
    assert first_result.clicked is True
    assert driver.scripts == [("mobile: tap", {"x": 227.0, "y": 210.5})]


def test_tap_ios_session_location_result_tries_next_candidate_until_modal_closes(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界国家森林公园")
    driver.capabilities = {"platformName": "iOS"}
    first_result = FakeElement({"x": 52, "y": 175, "width": 350, "height": 71})
    second_result = FakeElement({"x": 52, "y": 246, "width": 350, "height": 71})
    center_taps = []

    def fake_tap_element_center(received, element):
        center_taps.append(element)
        if element is second_result:
            driver.page_source = "新增场次 集合地点 张家界国家森林公园"

    monkeypatch.setattr(driver, "find_elements", lambda *args: [first_result, second_result], raising=False)
    monkeypatch.setattr(activity_sessions.activity, "_tap_element_center", fake_tap_element_center)

    assert activity_sessions._tap_ios_session_location_result(driver, "张家界景区") is True
    assert first_result.clicked is True
    assert second_result.clicked is True
    assert center_taps == [first_result, second_result]


def test_tap_ios_session_location_result_prefers_title_match_over_address_match(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界国家森林公园")
    driver.capabilities = {"platformName": "iOS"}
    address_only_match = FakeElement(
        {"x": 52, "y": 175, "width": 350, "height": 71},
        name="武陵源风景名胜区 湖南省张家界市武陵源区军地坪",
    )
    title_match = FakeElement(
        {"x": 52, "y": 246, "width": 350, "height": 71},
        name="张家界国家森林公园 湖南省张家界市武陵源区金鞭路279号",
    )
    tapped = []

    def fake_tap_element_center(received, element):
        tapped.append(element)
        driver.page_source = "新增场次 集合地点 张家界国家森林公园"

    monkeypatch.setattr(driver, "find_elements", lambda *args: [address_only_match, title_match], raising=False)
    monkeypatch.setattr(activity_sessions.activity, "_tap_element_center", fake_tap_element_center)

    assert activity_sessions._tap_ios_session_location_result(driver, "张家界景区") is True
    assert tapped == [title_match]
    assert address_only_match.clicked is False
    assert title_match.clicked is True


def test_write_ios_datetime_picker_value_taps_target_values_by_column():
    driver = FakeIosPickerDriver({"month": "07", "day": "18", "hour": "22"})

    assert activity_sessions._write_ios_datetime_picker_value(driver, "报名截止时间", "2026-07-23 18:00") is True

    assert driver.current == {"month": "07", "day": "23", "hour": "18"}
    assert ("mobile: tap", {"x": 201.0, "y": 707.0}) in driver.scripts
    assert ("mobile: tap", {"x": 316.0, "y": 647.0}) in driver.scripts


def test_tap_ios_datetime_picker_wheel_step_swipes_between_visible_rows():
    driver = FakeDriver(width=402, height=874)
    driver.capabilities = {"platformName": "iOS"}

    activity_sessions._tap_ios_datetime_picker_wheel_step(driver, "day", "next")

    assert driver.scripts == [
        (
            "swipe",
            {
                "start_x": 201,
                "start_y": 714,
                "end_x": 201,
                "end_y": 638,
                "duration": 300,
            },
        )
    ]


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


def test_fill_android_datetime_picker_wheels_uses_step_fallback_for_day(monkeypatch):
    driver = FakeDriver("已选择时间 07.31 22:22 月 日 时 分", width=1280, height=2856)
    calls = []
    current = {"day": "31"}

    def fake_tap(received, field, direction):
        calls.append((field, direction))
        current["day"] = "23"

    monkeypatch.setattr(activity_sessions, "_android_datetime_picker_current_parts", lambda received: dict(current))
    monkeypatch.setattr(activity_sessions, "_set_android_datetime_picker_wheel_value", lambda *args, **kwargs: False)
    monkeypatch.setattr(activity_sessions, "_tap_android_datetime_picker_wheel_step", fake_tap)

    assert activity_sessions._fill_android_datetime_picker_wheels(
        driver,
        {"day": "activity-session-create-deadline-picker-day-wheel"},
        ["day"],
        {"day": "23"},
    ) is True
    assert calls == [("day", "previous")]


def test_android_datetime_picker_taps_visible_value_in_scoped_wheel(monkeypatch):
    current = {"day": "25"}
    driver = FakeDriver("已选择时间 07.25 22:22 月 日 时 分", width=1280, height=2856)
    tapped = []

    class VisibleValue:
        rect = {"x": 352, "y": 2163, "width": 273, "height": 92}

        def is_displayed(self):
            return True

    def fake_find_elements(by, xpath):
        if '@resource-id="activity-session-create-deadline-picker-day-wheel"' in xpath and '@text="24"' in xpath:
            return [VisibleValue()]
        return []

    driver.find_elements = fake_find_elements

    def fake_tap_element_center(received, element):
        tapped.append(element.rect)
        current["day"] = "24"

    monkeypatch.setattr(activity_sessions.activity, "_tap_element_center", fake_tap_element_center)
    monkeypatch.setattr(activity_sessions, "_android_datetime_picker_current_parts", lambda received: dict(current))

    assert activity_sessions._tap_android_datetime_picker_visible_wheel_value(
        driver,
        "activity-session-create-deadline-picker-day-wheel",
        "day",
        "24",
    ) is True
    assert tapped == [{"x": 352, "y": 2163, "width": 273, "height": 92}]


def test_android_datetime_picker_taps_visible_value_from_page_source(monkeypatch):
    current = {"day": "25"}
    page_source = """
    <hierarchy>
      <android.view.ViewGroup resource-id="activity-session-create-deadline-picker-day-wheel" bounds="[352,2163][625,2481]">
        <android.widget.TextView text="24" bounds="[352,2163][625,2255]" />
        <android.widget.TextView text="25" bounds="[352,2256][625,2388]" />
        <android.widget.TextView text="26" bounds="[352,2389][625,2481]" />
      </android.view.ViewGroup>
    </hierarchy>
    """

    class TapDriver(FakeDriver):
        def execute_script(self, script, payload):
            super().execute_script(script, payload)
            current["day"] = "24"

    driver = TapDriver(page_source, width=1280, height=2856)

    monkeypatch.setattr(activity_sessions, "_android_datetime_picker_current_parts", lambda received: dict(current))

    assert activity_sessions._tap_android_datetime_picker_visible_wheel_value(
        driver,
        "activity-session-create-deadline-picker-day-wheel",
        "day",
        "24",
    ) is True
    assert driver.scripts == [("mobile: tap", {"x": 488, "y": 2209})]


def test_drag_android_datetime_picker_wheel_moves_down_direction_toward_previous_value():
    driver = FakeDriver(width=1280, height=2856)

    activity_sessions._drag_android_datetime_picker_wheel(driver, "day", "down", steps=1)

    assert driver.scripts == [
        (
            "mobile: dragGesture",
            {
                "startX": 485,
                "startY": 2321,
                "endX": 485,
                "endY": 2463,
                "speed": 1800,
            },
        )
    ]


def test_tap_android_datetime_picker_wheel_step_uses_bottom_row_for_next_value():
    driver = FakeDriver(width=1280, height=2856)

    activity_sessions._tap_android_datetime_picker_wheel_step(driver, "hour", "next")

    assert driver.scripts == [("mobile: tap", {"x": 784, "y": 2435})]


def test_drag_android_datetime_picker_wheel_to_target_drags_when_step_does_not_change_value(monkeypatch):
    driver = FakeDriver(width=1280, height=2856)
    current = {"hour": "22"}
    calls = []

    def fake_drag(received, field, direction, steps=1):
        calls.append(("drag", field, direction, steps))
        current["hour"] = "18"

    monkeypatch.setattr(activity_sessions, "_android_datetime_picker_current_parts", lambda received: dict(current))
    monkeypatch.setattr(activity_sessions, "_tap_android_datetime_picker_wheel_step", lambda received, field, direction: calls.append(("tap", field, direction)))
    monkeypatch.setattr(activity_sessions, "_drag_android_datetime_picker_wheel", fake_drag)

    assert activity_sessions._drag_android_datetime_picker_wheel_to_target(driver, "hour", "18") is True
    assert calls == [
        ("tap", "hour", "previous"),
        ("drag", "hour", "down", 1),
    ]


def test_build_activity_session_draft_uses_required_relative_dates():
    draft = activity_sessions.build_activity_session_draft(today=date(2026, 7, 17))

    assert draft.signup_deadline == "2026-07-22 18:00"
    assert draft.start_time == "2026-07-23 09:00"
    assert draft.end_time == "2026-07-23 18:00"
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


def test_fill_session_form_skips_reset_swipes_when_top_fields_are_visible(monkeypatch):
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
        ("field", "场次展示文案"),
        ("datetime", "报名截止时间"),
        ("field", "活动名额"),
    ]
    assert ("swipe", "down") not in events


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


def test_choose_session_location_retries_android_selection_before_dismissing(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区")
    events = []
    waits = []
    selected_attempts = {"value": 0}

    monkeypatch.setattr(activity_sessions, "_search_session_location", lambda driver, value: events.append(("search", value)) or True)
    monkeypatch.setattr(activity_sessions, "_session_location_results_visible", lambda page_source: True)
    monkeypatch.setattr(activity_sessions, "_tap_session_location_result", lambda driver, value: events.append(("tap-result", value)) or True)
    monkeypatch.setattr(
        activity_sessions,
        "_session_location_selected",
        lambda page_source: events.append("selected-check") or selected_attempts.__setitem__("value", selected_attempts["value"] + 1) or selected_attempts["value"] >= 2,
    )
    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: driver.page_source)

    def fake_wait_until(predicate, timeout):
        waits.append(timeout)
        if timeout == 5:
            return predicate()
        if timeout == 6:
            return False
        if timeout == 4:
            return predicate() or predicate()
        return predicate()

    monkeypatch.setattr(activity_sessions, "_wait_until", fake_wait_until)
    monkeypatch.setattr(activity_sessions, "_dismiss_session_location_modal", lambda driver: events.append("dismiss"))

    assert activity_sessions._choose_session_location(driver, "张家界景区") is True

    assert waits == [5, 6, 4]
    assert events == [
        ("search", "张家界景区"),
        ("tap-result", "张家界景区"),
        ("tap-result", "张家界景区"),
        "selected-check",
        "selected-check",
    ]
    assert "dismiss" not in events


def test_choose_session_location_keeps_ios_short_wait_path(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区")
    driver.capabilities = {"platformName": "iOS"}
    events = []
    waits = []

    monkeypatch.setattr(activity_sessions, "_search_session_location", lambda driver, value: events.append(("search", value)) or True)
    monkeypatch.setattr(activity_sessions, "_session_location_results_visible", lambda page_source: True)
    monkeypatch.setattr(activity_sessions, "_tap_session_location_result", lambda driver, value: events.append(("tap-result", value)) or True)
    monkeypatch.setattr(activity_sessions, "_session_location_selected", lambda page_source: events.append("selected-check") or True)
    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: driver.page_source)
    monkeypatch.setattr(activity_sessions, "_dismiss_session_location_modal", lambda driver: events.append("dismiss"))

    def fake_wait_until(predicate, timeout):
        waits.append(timeout)
        return predicate()

    monkeypatch.setattr(activity_sessions, "_wait_until", fake_wait_until)

    assert activity_sessions._choose_session_location(driver, "张家界景区") is True

    assert waits == [5, 2]
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


def test_tap_session_location_result_prefers_matching_title_text_over_plain_second_row(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区", width=1280, height=2856)

    def fake_find_elements(by, xpath):
        if "android.widget.TextView[1]" in xpath:
            return [
                FakeElement({"x": 278, "y": 390, "width": 954, "height": 66}, name="当前位置"),
                FakeElement({"x": 278, "y": 603, "width": 954, "height": 66}, name="武陵源风景名胜区"),
                FakeElement({"x": 278, "y": 816, "width": 954, "height": 66}, name="张家界景区"),
            ]
        return []

    monkeypatch.setattr(driver, "find_elements", fake_find_elements, raising=False)

    assert activity_sessions._tap_session_location_result(driver, "张家界景区") is True

    assert driver.scripts == [
        ("mobile: tap", {"x": 755.0, "y": 849.0}),
    ]


def test_tap_session_location_result_prefers_matching_result_card_over_title_text(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区", width=1280, height=2856)
    title = FakeElement({"x": 278, "y": 603, "width": 954, "height": 66}, name="张家界国家森林公园")
    card = FakeElement({"x": 0, "y": 540, "width": 1280, "height": 180})

    def fake_find_elements(by, xpath):
        if "android.widget.TextView[1]" in xpath:
            return [title]
        return []

    def fake_find_element(by, xpath):
        if 'contains(@text, "张家界国家森林公园")' in xpath and "ancestor::android.view.ViewGroup" in xpath:
            return card
        raise activity_sessions.NoSuchElementException()

    monkeypatch.setattr(driver, "find_elements", fake_find_elements, raising=False)
    monkeypatch.setattr(driver, "find_element", fake_find_element, raising=False)

    assert activity_sessions._tap_session_location_result(driver, "张家界景区") is True

    assert driver.scripts == [
        ("mobile: tap", {"x": 640.0, "y": 630.0}),
    ]


def test_tap_session_location_result_prefers_matching_result_address_lower_hit_area(monkeypatch):
    driver = FakeDriver("集合地点 搜索地点 张家界景区", width=1280, height=2856)
    title = FakeElement({"x": 278, "y": 603, "width": 954, "height": 66}, name="张家界国家森林公园")
    address = FakeElement({"x": 278, "y": 681, "width": 954, "height": 60}, name="湖南省张家界市武陵源区金鞭路279号")
    card = FakeElement({"x": 230, "y": 567, "width": 1050, "height": 210})

    def fake_find_elements(by, xpath):
        if "android.widget.TextView[1]" in xpath:
            return [title]
        return []

    def fake_find_element(by, xpath):
        if 'contains(@text, "张家界国家森林公园")' in xpath and "following-sibling::android.widget.TextView[1]" in xpath:
            return address
        if 'contains(@text, "张家界国家森林公园")' in xpath and "ancestor::android.view.ViewGroup" in xpath:
            return card
        raise activity_sessions.NoSuchElementException()

    monkeypatch.setattr(driver, "find_elements", fake_find_elements, raising=False)
    monkeypatch.setattr(driver, "find_element", fake_find_element, raising=False)

    assert activity_sessions._tap_session_location_result(driver, "张家界景区") is True

    assert driver.scripts == [
        ("mobile: tap", {"x": 755.0, "y": 714.0}),
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


def test_top_approved_badge_center_y_ignores_ios_page_container(monkeypatch):
    driver = FakeDriver("我的活动 发布 显示下架活动 黄山 通过 未发布", width=402, height=874)

    monkeypatch.setattr(
        driver,
        "find_elements",
        lambda by, xpath: [
            FakeElement({"x": 0, "y": 0, "width": 402, "height": 874}),
            FakeElement({"x": 1, "y": 312, "width": 34, "height": 20}),
            FakeElement({"x": 1, "y": 406, "width": 34, "height": 20}),
        ],
        raising=False,
    )

    assert activity_sessions._top_approved_badge_center_y(driver) == 322
