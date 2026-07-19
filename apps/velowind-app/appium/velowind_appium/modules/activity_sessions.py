from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta
import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import swipe_vertical, tap_text_if_present
from velowind_appium.config import IosAppiumConfig
import velowind_appium.modules.activity as activity
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


@dataclass(frozen=True)
class ActivitySessionDraft:
    title: str
    signup_deadline: str
    start_time: str
    end_time: str
    meeting_point: str
    max_participants: str
    fee: str
    contact_name: str
    contact_phone: str
    notes: str


def build_activity_session_draft(*, today: date | None = None) -> ActivitySessionDraft:
    base_date = today or date.today()
    return ActivitySessionDraft(
        title=f"自动化场次 {base_date:%m%d}",
        signup_deadline=_format_datetime(base_date + timedelta(days=4), datetime_time(18, 0)),
        start_time=_format_datetime(base_date + timedelta(days=5), datetime_time(9, 0)),
        end_time=_format_datetime(base_date + timedelta(days=10), datetime_time(18, 0)),
        meeting_point="张家界景区",
        max_participants="20",
        fee="0.01",
        contact_name="张家界大环线领队",
        contact_phone="13800138000",
        notes="保险",
    )


def _format_datetime(day: date, clock: datetime_time) -> str:
    return datetime.combine(day, clock).strftime("%Y-%m-%d %H:%M")


def add_activity_session(driver: WebDriver, draft: ActivitySessionDraft, config: IosAppiumConfig, *, timeout: int = 60) -> str:
    dismiss_common_system_alerts(driver)
    try:
        open_my_activity_publish_list(driver, timeout=min(timeout, 20))
    except AssertionError:
        try:
            ensure_logged_in_on_home(driver, config)
        except Exception:
            open_my_activity_publish_list(driver, timeout=timeout)
        else:
            open_my_activity_publish_list(driver, timeout=timeout)
    open_manage_sessions_for_approved_activity(driver, timeout=timeout)
    open_create_session_form(driver, timeout=timeout)
    fill_session_form(driver, draft, timeout=timeout)
    return submit_session_form(driver, expected_title=draft.title, timeout=timeout)


def open_my_activity_publish_list(driver: WebDriver, timeout: int = 30) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _session_form_visible(page_source) or "管理场次" in page_source:
            return
        if _my_activity_list_visible(page_source):
            _tap_publish_tab(driver)
            _toggle_show_delisted(driver)
            return
        if tap_text_if_present(driver, "我的活动", timeout=1):
            if _wait_until(lambda: _my_activity_list_visible(_safe_page_source(driver)), timeout=6):
                _tap_publish_tab(driver)
                _toggle_show_delisted(driver)
                return
        if _tap_my_activity_entry(driver):
            if _wait_until(lambda: _my_activity_list_visible(_safe_page_source(driver)), timeout=6):
                _tap_publish_tab(driver)
                _toggle_show_delisted(driver)
                return
        _tap_me_tab(driver)
        if tap_text_if_present(driver, "我的活动", timeout=1):
            if _wait_until(lambda: _my_activity_list_visible(_safe_page_source(driver)), timeout=6):
                _tap_publish_tab(driver)
                _toggle_show_delisted(driver)
                return
        if _tap_my_activity_entry(driver):
            if _wait_until(lambda: _my_activity_list_visible(_safe_page_source(driver)), timeout=6):
                _tap_publish_tab(driver)
                _toggle_show_delisted(driver)
                return
        time.sleep(0.5)
    raise AssertionError("Unable to open My Activity publish list")


def open_manage_sessions_for_approved_activity(driver: WebDriver, timeout: int = 30) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _session_form_visible(page_source):
            return
        if "管理场次" in page_source:
            if tap_text_if_present(driver, "管理场次", timeout=1):
                return
        if _tap_more_for_approved_activity(driver):
            if _wait_until(lambda: "管理场次" in _safe_page_source(driver), timeout=5):
                if tap_text_if_present(driver, "管理场次", timeout=1):
                    return
        _scroll_my_activity_list(driver)
        time.sleep(0.5)
    raise AssertionError("Unable to open Manage Sessions for an approved activity")


def open_create_session_form(driver: WebDriver, timeout: int = 20) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _session_form_visible(page_source):
            return
        if _tap_top_right_plus(driver) or tap_text_if_present(driver, "+", timeout=0.5) or tap_text_if_present(driver, "新增场次", timeout=0.5):
            if _wait_until(lambda: _session_form_visible(_safe_page_source(driver)), timeout=6):
                return
        time.sleep(0.5)
    raise AssertionError("Unable to open create activity session form")


def fill_session_form(driver: WebDriver, draft: ActivitySessionDraft, timeout: int = 60) -> None:
    if not _session_form_visible(_safe_page_source(driver)):
        raise AssertionError("Activity session form is not visible")

    _reset_session_form_to_top(driver)

    fields = [
        (["场次展示文案", "场次名称", "场次标题", "名称"], draft.title),
        (["报名截止时间", "报名截止"], draft.signup_deadline),
        (["活动名额", "人数上限", "报名人数", "人数"], draft.max_participants),
        (["开始时间", "活动开始"], draft.start_time),
        (["结束时间", "活动结束"], draft.end_time),
        (["集合地点", "集合地址", "地点"], draft.meeting_point),
        (["金额", "费用", "报名费", "价格"], draft.fee),
        (["配套服务", "场次说明", "说明", "备注"], draft.notes),
    ]
    for keywords, value in fields:
        is_datetime = keywords[0] in {"报名截止时间", "开始时间", "结束时间"}
        is_location = keywords[0] in {"集合地点", "集合地址", "地点"}
        filled = (
            _fill_session_datetime_field(driver, keywords, value)
            if is_datetime
            else _fill_session_location_field(driver, keywords, value)
            if is_location
            else _fill_session_field(driver, keywords, value)
        )
        if not filled:
            raise AssertionError(f"Unable to fill activity session field: {keywords[0]}")
        if is_location:
            if not _wait_until(lambda: _session_location_selected(_safe_page_source(driver)), timeout=5):
                raise AssertionError("Activity session location modal did not close with a selected value")


def _reset_session_form_to_top(driver: WebDriver) -> None:
    try:
        activity._hide_keyboard(driver)
    except (WebDriverException, AttributeError):
        pass
    page_source = _safe_page_source(driver)
    if all(token in page_source for token in ["新增场次", "场次展示文案", "报名截止时间", "活动名额"]):
        return
    for _ in range(3):
        try:
            swipe_vertical(driver, direction="down")
        except (WebDriverException, AttributeError):
            return
        time.sleep(0.15)


def submit_session_form(driver: WebDriver, *, expected_title: str, timeout: int = 30) -> str:
    if not _tap_submit(driver):
        raise AssertionError("Unable to submit activity session form")
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        for token in ["保存成功", "新增成功", "创建成功", "提交成功"]:
            if token in page_source:
                return token
        if "场次管理" in page_source and not _session_form_visible(page_source):
            return "场次管理"
        if expected_title in page_source and not _session_form_visible(page_source):
            return expected_title
        time.sleep(0.5)
    raise AssertionError("Activity session creation did not expose a success signal")


def _fill_session_field(driver: WebDriver, keywords: list[str], value: str) -> bool:
    for _ in range(5):
        for keyword in keywords:
            if activity._fill_input_near_label(driver, keyword, value):
                return True
        swipe_vertical(driver, direction="up")
        time.sleep(0.2)
    return False


def _fill_session_location_field(driver: WebDriver, keywords: list[str], value: str) -> bool:
    placeholders = ["点击选择或搜索集合地点", "点击选择集合地点", "搜索集合地点", "搜索地点"]
    try:
        activity._hide_keyboard(driver)
    except (WebDriverException, AttributeError):
        pass

    if _session_location_modal_visible(_safe_page_source(driver)):
        return _choose_session_location(driver, value)

    for _ in range(3):
        if _tap_session_location_field(driver, keywords, placeholders):
            time.sleep(0.5)
            return _choose_session_location(driver, value)
        swipe_vertical(driver, direction="up")
        time.sleep(0.2)
    return False


def _fill_session_datetime_field(driver: WebDriver, keywords: list[str], value: str) -> bool:
    for keyword in keywords:
        activity._hide_keyboard(driver)
        if _tap_session_datetime_field(driver, keyword):
            if _write_session_datetime_value(driver, keyword, value):
                _confirm_session_picker(driver)
                return True
    return False


def _tap_session_location_field(driver: WebDriver, keywords: list[str], placeholders: list[str]) -> bool:
    for keyword in keywords:
        if tap_text_if_present(driver, keyword, timeout=0.5):
            time.sleep(0.2)
            if _session_location_modal_visible(_safe_page_source(driver)):
                return True
            if _tap_session_location_container(driver, keyword):
                time.sleep(0.4)
                if _session_location_modal_visible(_safe_page_source(driver)):
                    return True
        if _tap_session_location_container(driver, keyword):
            time.sleep(0.4)
            if _session_location_modal_visible(_safe_page_source(driver)):
                return True

    for placeholder in placeholders:
        if tap_text_if_present(driver, placeholder, timeout=0.5):
            time.sleep(0.5)
            if _session_location_modal_visible(_safe_page_source(driver)):
                return True

    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: clickGesture",
            {
                "x": int(rect["width"] * 0.50),
                "y": int(rect["height"] * 0.56),
            },
        )
        time.sleep(0.5)
        return _session_location_modal_visible(_safe_page_source(driver))
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return False


def _tap_session_location_container(driver: WebDriver, keyword: str) -> bool:
    for xpath in [
        f'//*[contains(@text, "{keyword}")]/following-sibling::*[1]',
        f'//*[contains(@text, "{keyword}")]/following-sibling::*[2]',
        f'//*[contains(@text, "{keyword}")]/following::android.view.ViewGroup[1]',
        f'//*[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]/following-sibling::*[1]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            activity._tap_element_center(driver, element)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return False


def _choose_session_location(driver: WebDriver, value: str) -> bool:
    if _search_session_location(driver, value):
        if not _wait_until(lambda: _session_location_results_visible(_safe_page_source(driver)), timeout=5):
            return False
        if _tap_session_location_result(driver, value):
            if _wait_until(lambda: _session_location_selected(_safe_page_source(driver)), timeout=2):
                return True
            _dismiss_session_location_modal(driver)
            return _wait_until(lambda: _session_location_selected(_safe_page_source(driver)), timeout=5)

    return False


def _search_session_location(driver: WebDriver, value: str) -> bool:
    if _is_ios_driver(driver):
        return _search_ios_session_location(driver, value)

    for xpath in [
        '//android.widget.EditText',
        '//*[contains(@text, "搜索")]/following::android.widget.EditText[1]',
        '//*[contains(@content-desc, "搜索")]/following::android.widget.EditText[1]',
        '//XCUIElementTypeSearchField[1]',
        '//XCUIElementTypeTextField[1]',
    ]:
        try:
            field = driver.find_element(AppiumBy.XPATH, xpath)
            field.click()
            try:
                field.clear()
            except WebDriverException:
                pass
            if _paste_android_text(driver, value):
                try:
                    typed_value = str(field.get_attribute("text") or "")
                except (WebDriverException, AttributeError):
                    typed_value = ""
                if typed_value == value:
                    time.sleep(0.5)
                    return True
            try:
                field.set_value(value)
            except (WebDriverException, AttributeError):
                field.send_keys(value)
            time.sleep(0.5)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return False


def _search_ios_session_location(driver: WebDriver, value: str) -> bool:
    xpaths = [
        (
            '//XCUIElementTypeTextField['
            '@value="搜索地点" or @name="搜索地点" or @label="搜索地点" or @placeholderValue="搜索地点"'
            ']'
        ),
        '//*[contains(@name, "搜索地点") or contains(@label, "搜索地点")]/descendant::XCUIElementTypeTextField[1]',
        '//XCUIElementTypeTextField',
    ]
    candidates = []
    for xpath in xpaths:
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except (WebDriverException, AttributeError):
            continue
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                rect = element.rect
            except (WebDriverException, AttributeError):
                continue
            try:
                y = int(rect["y"])
                height = int(rect["height"])
            except (KeyError, TypeError, ValueError):
                y = 9999
                height = 9999
            candidates.append((y, height, element))
        if candidates:
            break

    for _y, _height, field in sorted(candidates, key=lambda item: (item[0], item[1])):
        try:
            field.click()
            try:
                field.clear()
            except WebDriverException:
                pass
            try:
                field.set_value(value)
            except (WebDriverException, AttributeError):
                field.send_keys(value)
            time.sleep(0.8)
            return True
        except (WebDriverException, AttributeError):
            continue
    return False


def _paste_android_text(driver: WebDriver, value: str) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    try:
        driver.set_clipboard_text(value)
        driver.press_keycode(279)
        return True
    except (WebDriverException, AttributeError):
        return False


def _tap_session_location_result(driver: WebDriver, value: str) -> bool:
    if _is_ios_driver(driver) and _tap_ios_session_location_result(driver, value):
        return True

    try:
        second_row_titles = driver.find_elements(
            AppiumBy.XPATH,
            '//android.widget.ScrollView/android.view.ViewGroup/android.view.ViewGroup/android.widget.TextView[1]',
        )
    except (WebDriverException, AttributeError):
        second_row_titles = []
    if len(second_row_titles) >= 2:
        try:
            activity._tap_element_center(driver, second_row_titles[1])
            time.sleep(0.6)
            return True
        except (WebDriverException, AttributeError):
            pass

    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: clickGesture",
            {
                "x": int(rect["width"] * 0.59),
                "y": int(rect["height"] * 0.223),
            },
        )
        time.sleep(0.6)
        return True
    except (WebDriverException, KeyError, TypeError, AttributeError):
        pass

    try:
        second_row_cards = driver.find_elements(
            AppiumBy.XPATH,
            '//android.widget.ScrollView/android.view.ViewGroup/android.view.ViewGroup[android.widget.TextView[2]]',
        )
    except (WebDriverException, AttributeError):
        second_row_cards = []
    if len(second_row_cards) >= 2:
        try:
            activity._tap_element_center(driver, second_row_cards[1])
            time.sleep(0.6)
            return True
        except (WebDriverException, AttributeError):
            pass

    container_xpaths = [
        f'(//android.widget.ScrollView//*[contains(@text, "{value}") and not(self::android.widget.EditText)]/ancestor::android.view.ViewGroup[1])[1]',
        f'(//android.widget.ScrollView//*[contains(@text, "{value}") and not(self::android.widget.EditText)]/ancestor::android.view.ViewGroup[2])[1]',
        '(//android.widget.ScrollView/android.view.ViewGroup/android.view.ViewGroup[android.widget.TextView])[1]',
    ]
    for xpath in container_xpaths:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            activity._tap_element_center(driver, element)
            time.sleep(0.6)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue

    result_xpaths = [
        f'//android.widget.ScrollView//*[contains(@text, "{value}") and not(self::android.widget.EditText)]',
        f'//*[contains(@text, "{value}") and not(self::android.widget.EditText) and not(@hint="搜索地点")]',
    ]
    for xpath in result_xpaths:
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except (WebDriverException, AttributeError):
            continue
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                activity._tap_element_center(driver, element)
                time.sleep(0.6)
                return True
            except (WebDriverException, AttributeError):
                continue
    return False


def _tap_ios_session_location_result(driver: WebDriver, value: str) -> bool:
    search_terms = _ios_session_location_search_terms(value)
    xpaths = []
    for term in search_terms:
        term = term.strip()
        if not term:
            continue
        escaped = term.replace('"', '\\"')
        xpaths.append(
            '//XCUIElementTypeScrollView//XCUIElementTypeStaticText['
            f'(contains(@name, "{escaped}") or contains(@label, "{escaped}") or contains(@value, "{escaped}"))'
            ']'
        )
        xpaths.append(
            '//XCUIElementTypeScrollView//XCUIElementTypeOther['
            f'(contains(@name, "{escaped}") or contains(@label, "{escaped}") or contains(@value, "{escaped}"))'
            ']'
        )

    candidates = []
    seen_elements = set()
    for xpath in xpaths:
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except (WebDriverException, AttributeError):
            continue
        for element in elements:
            element_key = getattr(element, "id", None) or id(element)
            if element_key in seen_elements:
                continue
            seen_elements.add(element_key)
            try:
                if not element.is_displayed():
                    continue
                rect = element.rect
                width = int(rect["width"])
                height = int(rect["height"])
                y = int(rect["y"])
            except (WebDriverException, KeyError, TypeError, ValueError, AttributeError):
                continue
            if width < 250 or height < 48 or height > 130 or y < 150:
                continue
            score = _ios_session_location_result_score(element, search_terms)
            candidates.append((score, y, height, element))

    for _score, _y, _height, element in sorted(candidates, key=lambda item: (item[0], item[1], item[2])):
        try:
            try:
                element.click()
                if _wait_until(lambda: not _session_location_modal_visible(_safe_page_source(driver)), timeout=1):
                    return True
            except (WebDriverException, AttributeError):
                pass
            activity._tap_element_center(driver, element)
            if _wait_until(lambda: not _session_location_modal_visible(_safe_page_source(driver)), timeout=1):
                return True
        except (WebDriverException, AttributeError):
            continue
    return False


def _ios_session_location_search_terms(value: str) -> list[str]:
    terms = []
    for term in [value, value.replace("景区", "")]:
        term = term.strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def _ios_session_location_result_score(element, search_terms: list[str]) -> int:
    text = _ios_session_location_result_text(element)
    title = text.split(" ")[0].strip()
    if title.startswith("湖南省"):
        title = ""
    for term in search_terms:
        if term and term in title:
            return 0
    for term in search_terms:
        if term and text.startswith(term):
            return 1
    for term in search_terms:
        if term and term in text:
            return 2
    return 3


def _ios_session_location_result_text(element) -> str:
    for attr in ["name", "label", "value"]:
        try:
            text = str(element.get_attribute(attr) or "").strip()
        except (WebDriverException, AttributeError):
            text = ""
        if text:
            return text
    return ""


def _dismiss_session_location_modal(driver: WebDriver) -> None:
    try:
        activity._hide_keyboard(driver)
    except (WebDriverException, AttributeError):
        pass
    if _session_location_modal_visible(_safe_page_source(driver)):
        try:
            rect = driver.get_window_rect()
            driver.execute_script(
                "mobile: clickGesture",
                {
                    "x": int(rect["width"] * 0.19),
                    "y": int(rect["height"] * 0.05),
                },
            )
            time.sleep(0.5)
        except (WebDriverException, KeyError, TypeError, AttributeError):
            pass
    for _ in range(2):
        if not _session_location_modal_visible(_safe_page_source(driver)):
            return
        try:
            driver.press_keycode(4)
        except (WebDriverException, AttributeError):
            break
        time.sleep(0.4)
    if _session_location_modal_visible(_safe_page_source(driver)):
        try:
            rect = driver.get_window_rect()
            driver.execute_script(
                "mobile: clickGesture",
                {
                    "x": int(rect["width"] * 0.19),
                    "y": int(rect["height"] * 0.05),
                },
            )
            time.sleep(0.4)
        except (WebDriverException, KeyError, TypeError, AttributeError):
            return


def _session_location_selected(page_source: str) -> bool:
    return (
        _session_form_visible(page_source)
        and not _session_location_modal_visible(page_source)
        and "点击选择或搜索集合地点" not in page_source
        and "点击选择集合地点" not in page_source
    )


def _session_location_results_visible(page_source: str) -> bool:
    return _session_location_modal_visible(page_source) and not any(
        token in page_source
        for token in [
            "正在获取当前位置",
            "获取当前位置...",
            "获取当前位置…",
            "未获取到当前位置",
            "请输入关键词搜索地点",
        ]
    )


def _session_location_value_present(page_source: str, value: str) -> bool:
    return value in page_source and not _session_location_modal_visible(page_source)


def _session_location_modal_visible(page_source: str) -> bool:
    return any(
        token in page_source
        for token in ["搜索地点", 'hint="搜索地点"', "搜索中", "地址搜索"]
    )


def _tap_session_datetime_field(driver: WebDriver, keyword: str) -> bool:
    if _is_ios_driver(driver):
        if _tap_ios_session_datetime_field(driver, keyword):
            time.sleep(0.3)
            return True
        return False

    if _tap_ios_session_datetime_field(driver, keyword):
        time.sleep(0.3)
        return True

    if _tap_session_datetime_container(driver, keyword):
        time.sleep(0.3)
        return True

    try:
        rect = driver.get_window_rect()
        if keyword in {"报名截止时间", "报名截止"}:
            points = [(0.41, 0.28), (0.46, 0.28)]
        elif keyword in {"开始时间", "活动开始"}:
            points = [(0.41, 0.38), (0.46, 0.38)]
        else:
            points = [(0.82, 0.38), (0.89, 0.38)]
        for x_ratio, y_ratio in points:
            driver.execute_script(
                "mobile: tap",
                {
                    "x": round(rect["width"] * x_ratio),
                    "y": round(rect["height"] * y_ratio),
                },
            )
            time.sleep(0.15)
        time.sleep(0.3)
        return True
    except (WebDriverException, KeyError, TypeError):
        pass

    placeholders = {
        "报名截止时间": ["例如：06.29 20:00"],
        "报名截止": ["例如：06.29 20:00"],
        "开始时间": ["例如：06.30 06:45"],
        "活动开始": ["例如：06.30 06:45"],
        "结束时间": ["例如：06.30 10:30"],
        "活动结束": ["例如：06.30 10:30"],
    }
    for placeholder in placeholders.get(keyword, []):
        if tap_text_if_present(driver, placeholder, timeout=0.5):
            time.sleep(0.3)
            return True

    return False


def _tap_ios_session_datetime_field(driver: WebDriver, keyword: str) -> bool:
    if not _is_ios_driver(driver):
        return False

    if _tap_ios_session_datetime_element(driver, keyword):
        return True

    points = {
        "报名截止时间": [(0.44, 0.307), (0.26, 0.307), (0.16, 0.307), (0.44, 0.285)],
        "报名截止": [(0.44, 0.307), (0.26, 0.307), (0.16, 0.307), (0.44, 0.285)],
        "开始时间": [(0.44, 0.398), (0.26, 0.398), (0.16, 0.398), (0.44, 0.376)],
        "活动开始": [(0.44, 0.398), (0.26, 0.398), (0.16, 0.398), (0.44, 0.376)],
        "结束时间": [(0.92, 0.398), (0.74, 0.398), (0.64, 0.398), (0.92, 0.376)],
        "活动结束": [(0.92, 0.398), (0.74, 0.398), (0.64, 0.398), (0.92, 0.376)],
    }
    field_points = points.get(keyword)
    if field_points is None:
        return False
    try:
        rect = driver.get_window_rect()
        for x_ratio, y_ratio in field_points:
            _tap_ios_point(driver, round(rect["width"] * x_ratio), round(rect["height"] * y_ratio))
            if _wait_until(lambda: _ios_datetime_picker_visible(_safe_page_source(driver)), timeout=1):
                return True
        return False
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return False


def _tap_ios_session_datetime_element(driver: WebDriver, keyword: str) -> bool:
    escaped = keyword.replace('"', '\\"')
    xpaths = [
        (
            '//XCUIElementTypeOther['
            f'contains(@name, "{escaped}") and contains(@name, "月") '
            'and @width <= 230 and @height <= 100'
            ']'
        ),
        (
            '//XCUIElementTypeOther['
            f'contains(@label, "{escaped}") and contains(@label, "月") '
            'and @width <= 230 and @height <= 100'
            ']'
        ),
    ]
    for xpath in xpaths:
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except (WebDriverException, AttributeError):
            continue
        candidates = []
        for element in elements:
            try:
                rect = element.rect
                if not element.is_displayed():
                    continue
            except AttributeError:
                rect = getattr(element, "rect", {}) or {}
            except WebDriverException:
                continue
            candidates.append((rect.get("width", 9999) * rect.get("height", 9999), rect, element))
        for _area, _rect, element in sorted(candidates, key=lambda item: item[0]):
            try:
                element.click()
            except (WebDriverException, AttributeError):
                pass
            if _wait_until(lambda: _ios_datetime_picker_visible(_safe_page_source(driver)), timeout=1):
                return True
            for x, y in _ios_datetime_field_points(_rect):
                try:
                    _tap_ios_point(driver, x, y)
                except (WebDriverException, AttributeError):
                    continue
                if _wait_until(lambda: _ios_datetime_picker_visible(_safe_page_source(driver)), timeout=1):
                    return True
    return False


def _ios_datetime_field_points(rect: dict) -> list[tuple[int, int]]:
    try:
        left = int(rect["x"])
        top = int(rect["y"])
        width = int(rect["width"])
        height = int(rect["height"])
    except (KeyError, TypeError, ValueError):
        return []
    value_y = top + round(height * 0.72)
    return [
        (left + width - 20, value_y),
        (left + int(width * 0.50), value_y),
        (left + int(width * 0.50), top + int(height * 0.50)),
        (left + int(width * 0.25), value_y),
        (left + width - 12, top + int(height * 0.50)),
    ]


def _tap_ios_point(driver: WebDriver, x: int, y: int) -> None:
    try:
        driver.tap([(x, y)], 100)
        return
    except (WebDriverException, AttributeError):
        pass
    driver.execute_script("mobile: tap", {"x": x, "y": y})


def _is_ios_driver(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    return str(capabilities.get("platformName", "")).lower() == "ios"


def _ios_datetime_picker_visible(page_source: str) -> bool:
    if "XCUIElementTypePickerWheel" in page_source:
        return True
    return all(token in page_source for token in ["已选择时间", "取消", "确认", "月", "日", "时"])


def _ios_datetime_picker_current_parts_from_source(page_source: str) -> dict[str, str] | None:
    match = re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2})点", page_source)
    if not match:
        return None
    month, day, hour = match.groups()
    return {
        "month": f"{int(month):02d}",
        "day": f"{int(day):02d}",
        "hour": f"{int(hour):02d}",
        "minute": "00",
    }


def _tap_session_datetime_container(driver: WebDriver, keyword: str) -> bool:
    for xpath in [
        f'//*[contains(@text, "{keyword}")]/following-sibling::*[2]',
        f'//*[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]/following-sibling::*[2]',
        f'//*[contains(@text, "{keyword}")]/following::android.view.ViewGroup[2]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            activity._tap_element_center(driver, element)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return False


def _write_session_datetime_value(driver: WebDriver, keyword: str, value: str) -> bool:
    expected = _session_datetime_target_rect(keyword)
    if _is_ios_driver(driver):
        if _ios_datetime_picker_visible(_safe_page_source(driver)):
            return _write_ios_datetime_picker_value(driver, keyword, value)
    else:
        if _write_android_datetime_picker_value(driver, keyword, value):
            return True
    try:
        active = driver.switch_to.active_element
        active_class = str(active.get_attribute("class") or "")
        active_rect = getattr(active, "rect", {}) or {}
        if ("EditText" in active_class or "TextField" in active_class) and _rect_matches_target(active_rect, expected):
            try:
                active.clear()
            except WebDriverException:
                pass
            active.send_keys(value)
            return True
    except (WebDriverException, AttributeError):
        pass

    try:
        elements = driver.find_elements(AppiumBy.XPATH, "//android.widget.EditText | //XCUIElementTypeTextField")
    except (WebDriverException, AttributeError):
        elements = []
    candidates = []
    for element in elements:
        try:
            if not element.is_displayed():
                continue
            rect = element.rect
            if not _rect_matches_target(rect, expected):
                continue
            candidates.append((rect, element))
        except (WebDriverException, AttributeError):
            continue

    for _rect, element in sorted(
        candidates,
        key=lambda item: abs((item[0]["y"] + item[0]["height"] / 2) - expected["y"]) + abs((item[0]["x"] + item[0]["width"] / 2) - expected["x"]),
    ):
        try:
            element.click()
            try:
                element.clear()
            except WebDriverException:
                pass
            element.send_keys(value)
            return True
        except (WebDriverException, AttributeError):
            continue

    return False


def _write_ios_datetime_picker_value(driver: WebDriver, keyword: str, value: str) -> bool:
    if not _is_ios_driver(driver):
        return False
    parts = _parse_session_datetime(value)
    if parts is None:
        return False
    if not _wait_until(lambda: _ios_datetime_picker_visible(_safe_page_source(driver)), timeout=3):
        return False
    return _fill_ios_datetime_picker_fields(driver, ["month", "day", "hour"], parts)


def _fill_ios_datetime_picker_fields(driver: WebDriver, field_order: list[str], parts: dict[str, str]) -> bool:
    for field in field_order:
        target = parts[field]
        current = _ios_datetime_picker_current_parts(driver)
        if current is None:
            return False
        if current.get(field) == target:
            continue
        if _tap_ios_datetime_picker_value(driver, field, target):
            if _wait_until(
                lambda: ((_ios_datetime_picker_current_parts(driver) or {}).get(field) == target),
                timeout=1.5,
            ):
                continue
        if not _tap_ios_datetime_picker_wheel_to_target(driver, field, target):
            return False
    current = _ios_datetime_picker_current_parts(driver)
    return bool(current and all(current.get(field) == parts[field] for field in field_order))


def _ios_datetime_picker_current_parts(driver: WebDriver) -> dict[str, str] | None:
    return _ios_datetime_picker_current_parts_from_source(_safe_page_source(driver))


def _tap_ios_datetime_picker_value(driver: WebDriver, field: str, value: str) -> bool:
    escaped = value.replace('"', '\\"')
    try:
        rect = driver.get_window_rect()
        expected_x, _expected_y = _ios_datetime_picker_wheel_center(rect, field)
        min_y = int(rect["height"] * 0.52)
        max_y = int(rect["height"] * 0.92)
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return False

    try:
        elements = driver.find_elements(
            AppiumBy.XPATH,
            f'//*[@name="{escaped}" or @label="{escaped}" or @value="{escaped}"]',
        )
    except (WebDriverException, AttributeError):
        elements = []

    candidates = []
    for element in elements:
        try:
            element_rect = element.rect
            center_x = element_rect["x"] + element_rect["width"] / 2
            center_y = element_rect["y"] + element_rect["height"] / 2
        except (WebDriverException, KeyError, TypeError, AttributeError):
            continue
        if not min_y <= center_y <= max_y:
            continue
        candidates.append((abs(center_x - expected_x), element))

    for _distance, element in sorted(candidates, key=lambda item: item[0]):
        try:
            activity._tap_element_center(driver, element)
            return True
        except (WebDriverException, AttributeError):
            continue
    return False


def _tap_ios_datetime_picker_wheel_to_target(driver: WebDriver, field: str, target: str) -> bool:
    for _ in range(36):
        current = _ios_datetime_picker_current_parts(driver)
        if current is None:
            return False
        current_value = current.get(field)
        if current_value == target:
            return True
        direction = _android_datetime_picker_step_direction(field, current_value, target)
        if direction is None:
            return False
        _tap_ios_datetime_picker_wheel_step(driver, field, direction)
        time.sleep(0.1)
    current = _ios_datetime_picker_current_parts(driver)
    return bool(current and current.get(field) == target)


def _tap_ios_datetime_picker_wheel_step(driver: WebDriver, field: str, direction: str) -> None:
    try:
        rect = driver.get_window_rect()
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return
    center_x, center_y = _ios_datetime_picker_wheel_center(rect, field)
    offset = max(30, int(rect["height"] * 0.0435))
    start_y = center_y + offset if direction == "next" else center_y - offset
    end_y = center_y - offset if direction == "next" else center_y + offset
    try:
        driver.swipe(center_x, start_y, center_x, end_y, duration=300)
        return
    except (WebDriverException, AttributeError):
        pass
    try:
        driver.execute_script("mobile: tap", {"x": center_x, "y": start_y})
    except WebDriverException:
        pass


def _ios_datetime_picker_wheel_center(rect: dict, field: str) -> tuple[int, int]:
    x_ratio, y_ratio = {
        "month": (0.214, 0.774),
        "day": (0.500, 0.774),
        "hour": (0.786, 0.774),
    }.get(field, (0.500, 0.774))
    return int(rect["width"] * x_ratio), int(rect["height"] * y_ratio)



def _write_android_datetime_picker_value(driver: WebDriver, keyword: str, value: str) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    parts = _parse_session_datetime(value)
    if parts is None:
        return False
    if not _wait_until(lambda: _android_datetime_picker_visible(_safe_page_source(driver), keyword), timeout=3):
        return False
    field_order = {
        "报名截止时间": ["day"],
        "报名截止": ["day"],
        "开始时间": ["day"],
        "活动开始": ["day"],
        "结束时间": ["day"],
        "活动结束": ["day"],
    }.get(keyword)
    if field_order is None:
        return False

    wheel_ids = {
        "month": "activity-session-create-deadline-picker-month-wheel",
        "day": "activity-session-create-deadline-picker-day-wheel",
        "hour": "activity-session-create-deadline-picker-hour-wheel",
        "minute": "activity-session-create-deadline-picker-minute-wheel",
    }
    _fill_android_datetime_picker_wheels(driver, wheel_ids, field_order, parts)
    _confirm_session_picker(driver)
    return True


def _fill_android_datetime_picker_wheels(
    driver: WebDriver,
    wheel_ids: dict[str, str],
    field_order: list[str],
    parts: dict[str, str],
) -> bool:
    for field in field_order:
        wheel_id = wheel_ids.get(field)
        if wheel_id and _set_android_datetime_picker_wheel_value(driver, wheel_id, field, parts[field]):
            continue
        if field == "day":
            current = _android_datetime_picker_current_parts(driver) or {}
            direction_and_steps = _android_datetime_picker_drag_direction_and_steps(field, current.get(field), parts[field])
            if direction_and_steps is not None:
                direction, steps = direction_and_steps
                _drag_android_datetime_picker_wheel(driver, field, direction, steps=steps)
                time.sleep(0.2)
                current = _android_datetime_picker_current_parts(driver)
                if current and current.get(field) == parts[field]:
                    continue
        if not _drag_android_datetime_picker_wheel_to_target(driver, field, parts[field]):
            return False
    return True


def _set_android_datetime_picker_wheel_value(driver: WebDriver, wheel_id: str, field: str, value: str) -> bool:
    wheel = None
    for locator in _android_datetime_picker_wheel_locators(wheel_id):
        for _ in range(10):
            try:
                wheel = driver.find_element(*locator)
                break
            except (NoSuchElementException, WebDriverException, AttributeError):
                time.sleep(0.2)
        if wheel is not None:
            break
    if wheel is None:
        return False
    try:
        wheel.click()
    except (WebDriverException, AttributeError):
        pass
    try:
        wheel.send_keys(value)
        return _wait_until(
            lambda: (_android_datetime_picker_current_parts(driver) or {}).get(field) == value,
            timeout=1,
        )
    except (WebDriverException, AttributeError):
        return False


def _android_datetime_picker_wheel_locators(wheel_id: str) -> list[tuple[str, str]]:
    escaped = wheel_id.replace('"', '\\"')
    return [
        (AppiumBy.ID, wheel_id),
        (AppiumBy.XPATH, f'//*[@resource-id="{escaped}"]'),
        (AppiumBy.XPATH, f'//*[@resource-id="{escaped}"]/android.widget.ScrollView[1]'),
    ]


def _drag_android_datetime_picker_wheel_to_target(driver: WebDriver, field: str, target: str) -> bool:
    current = _android_datetime_picker_current_parts(driver)
    if current is None:
        return False
    current_value = current.get(field)
    if current_value == target:
        return True

    max_attempts = 36
    for _ in range(max_attempts):
        current = _android_datetime_picker_current_parts(driver)
        if current is None:
            return False
        current_value = current.get(field)
        if current_value == target:
            return True
        step_direction = _android_datetime_picker_step_direction(field, current_value, target)
        if step_direction is None:
            return False
        _tap_android_datetime_picker_wheel_step(driver, field, step_direction)
        time.sleep(0.1)

    current = _android_datetime_picker_current_parts(driver)
    return bool(current and current.get(field) == target)


def _drag_android_datetime_picker_wheel(driver: WebDriver, field: str, direction: str, *, steps: int = 1) -> None:
    try:
        rect = driver.get_window_rect()
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return

    center_x, center_y = _android_datetime_picker_wheel_center(rect, field)
    delta = max(72, int(rect["height"] * 0.05)) * max(1, min(3, steps))
    end_y = center_y - delta if direction == "up" else center_y + delta
    try:
        driver.execute_script(
            "mobile: dragGesture",
            {
                "startX": center_x,
                "startY": center_y,
                "endX": center_x,
                "endY": end_y,
                "speed": 1800,
            },
        )
    except WebDriverException:
        pass


def _tap_android_datetime_picker_wheel_step(driver: WebDriver, field: str, direction: str) -> None:
    try:
        rect = driver.get_window_rect()
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return

    center_x, center_y = _android_datetime_picker_wheel_center(rect, field)
    offset = max(92, int(rect["height"] * 0.04))
    tap_y = center_y + offset if direction == "next" else center_y - offset
    try:
        driver.execute_script("mobile: tap", {"x": center_x, "y": tap_y})
    except WebDriverException:
        pass


def _android_datetime_picker_wheel_center(rect: dict, field: str) -> tuple[int, int]:
    x_ratio, y_ratio = {
        "month": (0.145, 0.813),
        "day": (0.379, 0.813),
        "hour": (0.613, 0.813),
        "minute": (0.847, 0.813),
    }.get(field, (0.145, 0.813))
    return int(rect["width"] * x_ratio), int(rect["height"] * y_ratio)


def _android_datetime_picker_drag_direction(field: str, current: str | None, target: str) -> str | None:
    direction_and_steps = _android_datetime_picker_drag_direction_and_steps(field, current, target)
    if direction_and_steps is None:
        return None
    return direction_and_steps[0]


def _android_datetime_picker_step_direction(field: str, current: str | None, target: str) -> str | None:
    direction_and_steps = _android_datetime_picker_drag_direction_and_steps(field, current, target)
    if direction_and_steps is None:
        return None
    direction, _steps = direction_and_steps
    return "next" if direction == "up" else "previous"


def _android_datetime_picker_drag_direction_and_steps(field: str, current: str | None, target: str) -> tuple[str, int] | None:
    if current is None:
        return None
    try:
        current_int = int(current)
        target_int = int(target)
    except (TypeError, ValueError):
        return None

    ranges = {
        "month": 12,
        "day": 31,
        "hour": 24,
        "minute": 60,
    }
    cycle = ranges.get(field)
    if cycle is None:
        return None
    if current_int == target_int:
        return None

    forward = (target_int - current_int) % cycle
    backward = (current_int - target_int) % cycle
    if forward <= backward:
        return "up", max(1, min(3, forward))
    return "down", max(1, min(3, backward))


def _android_datetime_picker_current_parts(driver: WebDriver) -> dict[str, str] | None:
    page_source = _safe_page_source(driver)
    match = None
    for pattern in [
        r"(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})",
        r"(\d{2})[.](\d{2})\s+(\d{2}):(\d{2})",
    ]:
        match = re.search(pattern, page_source)
        if match:
            break
    if not match:
        return None
    month, day, hour, minute = match.groups()
    return {"month": month, "day": day, "hour": hour, "minute": minute}


def _android_datetime_picker_visible(page_source: str, keyword: str) -> bool:
    if keyword in {"报名截止时间", "报名截止", "开始时间", "活动开始", "结束时间", "活动结束"}:
        return all(token in page_source for token in ["已选择时间", "取消", "确认", "月", "日", "时", "分"])
    return False


def _parse_session_datetime(value: str) -> dict[str, str] | None:
    try:
        date_part, time_part = value.split(" ", 1)
        month, day = date_part.split("-", 2)[1:]
        hour, minute = time_part.split(":", 1)
    except ValueError:
        return None
    return {
        "month": f"{int(month):02d}",
        "day": f"{int(day):02d}",
        "hour": f"{int(hour):02d}",
        "minute": f"{int(minute):02d}",
    }


def _session_datetime_target_rect(keyword: str) -> dict[str, int]:
    if keyword in {"报名截止时间", "报名截止"}:
        return {"x": 320, "y": 822, "left": 42, "right": 627, "top": 753, "bottom": 891}
    if keyword in {"开始时间", "活动开始"}:
        return {"x": 320, "y": 1089, "left": 42, "right": 627, "top": 1020, "bottom": 1158}
    return {"x": 940, "y": 1089, "left": 654, "right": 1238, "top": 1020, "bottom": 1158}


def _rect_matches_target(rect: dict, expected: dict[str, int]) -> bool:
    try:
        center_x = rect["x"] + rect["width"] / 2
        center_y = rect["y"] + rect["height"] / 2
    except (KeyError, TypeError, ValueError):
        return False
    return (
        expected["left"] <= center_x <= expected["right"]
        and expected["top"] <= center_y <= expected["bottom"]
    )


def _confirm_session_picker(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.75),
                "y": int(rect["height"] * 0.93),
            },
        )
        return True
    except (WebDriverException, KeyError, TypeError, AttributeError):
        pass
    for text in ["确认", "确定", "完成", "保存"]:
        if tap_text_if_present(driver, text, timeout=0.5):
            return True
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.80),
                "y": int(rect["height"] * 0.92),
            },
        )
        return True
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return False


def _tap_me_tab(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "我的", timeout=1):
        return True
    try:
        rect = driver.get_window_rect()
        driver.execute_script("mobile: tap", {"x": int(rect["width"] * 0.88), "y": int(rect["height"] * 0.93)})
        return True
    except (WebDriverException, KeyError, TypeError):
        return False


def _tap_my_activity_entry(driver: WebDriver) -> bool:
    for xpath in [
        '//*[contains(@text, "我的活动")]/ancestor::android.view.ViewGroup[1]',
        '//*[contains(@text, "我的活动")]/ancestor::android.view.ViewGroup[2]',
        '//*[contains(@name, "我的活动") or contains(@label, "我的活动") or contains(@value, "我的活动")]/ancestor::*[1]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            activity._tap_element_center(driver, element)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: clickGesture",
            {
                "x": int(rect["width"] * 0.50),
                "y": int(rect["height"] * 0.31),
            },
        )
        return True
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return False


def _tap_publish_tab(driver: WebDriver) -> bool:
    for text in ["发布", "已发布", "我发布的"]:
        if tap_text_if_present(driver, text, timeout=0.5):
            return True
    return False


def _toggle_show_delisted(driver: WebDriver) -> bool:
    for text in ["显示下架活动", "下架活动"]:
        if tap_text_if_present(driver, text, timeout=0.5):
            return True
    return False


def _tap_more_for_approved_activity(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if "通过" in page_source and _tap_right_side_of_top_approved_card(driver):
        return True
    for text in ["...", "…", "更多"]:
        if tap_text_if_present(driver, text, timeout=0.5):
            return True
    for xpath in [
        '//*[contains(@text, "...") or contains(@text, "…") or contains(@content-desc, "更多")]',
        '(//android.widget.TextView[contains(@text, "通过")]/following::android.widget.TextView[contains(@text, "...") or contains(@text, "…")])[1]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            activity._tap_element_center(driver, element)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return False


def _tap_right_side_of_top_approved_card(driver: WebDriver) -> bool:
    y = _top_approved_badge_center_y(driver)
    try:
        rect = driver.get_window_rect()
        tap_y = y if y is not None else int(rect["height"] * 0.30)
        driver.execute_script(
            "mobile: tap",
            {
                "x": round(rect["width"] * 0.91),
                "y": tap_y,
            },
        )
        return True
    except (WebDriverException, KeyError, TypeError, AttributeError):
        return False


def _top_approved_badge_center_y(driver: WebDriver) -> int | None:
    candidates = []
    for xpath in [
        '//*[contains(@text, "通过")]',
        '//*[contains(@name, "通过") or contains(@label, "通过") or contains(@value, "通过")]',
    ]:
        try:
            candidates.extend(driver.find_elements(AppiumBy.XPATH, xpath))
        except (WebDriverException, AttributeError):
            continue
    badge_tops: list[tuple[int, int]] = []
    try:
        window_height = int(driver.get_window_rect()["height"])
    except (WebDriverException, KeyError, TypeError, AttributeError):
        window_height = 3000
    for element in candidates:
        try:
            rect = element.rect
            width = int(rect["width"])
            height = int(rect["height"])
            y = int(rect["y"])
            if width > 120 or height > 80 or y < 0 or y > window_height:
                continue
            badge_tops.append((y, int(y + height / 2)))
        except (WebDriverException, KeyError, TypeError, AttributeError):
            continue
    if not badge_tops:
        return None
    return sorted(badge_tops)[0][1]


def _tap_top_right_plus(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script("mobile: tap", {"x": int(rect["width"] * 0.92), "y": int(rect["height"] * 0.10)})
        return True
    except (WebDriverException, KeyError, TypeError):
        return False


def _tap_submit(driver: WebDriver) -> bool:
    for text in ["保存", "确定", "提交", "新增", "创建"]:
        if tap_text_if_present(driver, text, timeout=0.5):
            return True
    try:
        rect = driver.get_window_rect()
        driver.execute_script("mobile: tap", {"x": int(rect["width"] * 0.72), "y": int(rect["height"] * 0.94)})
        return True
    except (WebDriverException, KeyError, TypeError):
        return False


def _scroll_my_activity_list(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: dragGesture",
            {
                "startX": int(rect["width"] * 0.5),
                "startY": int(rect["height"] * 0.82),
                "endX": int(rect["width"] * 0.5),
                "endY": int(rect["height"] * 0.34),
                "speed": 1800,
            },
        )
        return True
    except (WebDriverException, KeyError, TypeError):
        try:
            driver.execute_script("mobile: swipe", {"direction": "up"})
            return True
        except WebDriverException:
            return False


def _my_activity_list_visible(page_source: str) -> bool:
    return "我的活动" in page_source and any(token in page_source for token in ["发布", "报名", "下架", "审核", "通过"])


def _session_flow_is_already_open(page_source: str) -> bool:
    if _session_form_visible(page_source):
        return True
    if "管理场次" in page_source:
        return True
    return "我的活动" in page_source and any(token in page_source for token in ["我的笔记", "发布", "报名", "下架", "审核", "通过"])


def _session_form_visible(page_source: str) -> bool:
    return any(token in page_source for token in ["场次名称", "场次展示文案", "报名截止", "开始时间", "结束时间", "新增场次", "编辑场次"])


def _wait_until(predicate, timeout: int | float) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""
