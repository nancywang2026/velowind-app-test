from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import html
import os
from pathlib import Path
import re
import time
from xml.etree import ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
import yaml

from velowind_appium.actions import (
    swipe_vertical,
    tap_if_present,
    tap_text_if_present,
    wait_for_any_accessibility_id_or_text,
)
from velowind_appium.auth import ensure_logged_in_if_needed, login_required_from_page_source
from velowind_appium.config import IosAppiumConfig
import velowind_appium.modules.photo_picker as photo_picker


PUBLISH_ENTRY_IDS = [
    "bottom-nav-publish",
    "bottom-nav-plus",
    "bottom-nav-add",
    "home-publish-entry",
    "home-create-entry",
]
PUBLISH_ENTRY_TEXTS = ["发布", "发活动", "创建", "+", "＋"]
ACTIVITY_TYPE_IDS = [
    "publish-type-activity",
    "post-type-activity",
    "activity-publish-type",
]
ACTIVITY_TYPE_TEXTS = ["活动", "发布活动"]
PUBLISH_SHEET_TEXTS = ["选择发布类型"]
FORM_READY_IDS = [
    "activity-publish-page",
    "activity-create-page",
    "activity-edit-page",
    "submit-audit-button",
]
FORM_READY_TEXTS = ["发布活动", "活动信息", "提交审核", "活动名称", "活动详情"]
SUCCESS_TEXTS = ["提交成功", "审核中", "待审核", "发布成功", "提交审核成功"]
SUCCESS_IDS = [
    "publish-success-page",
    "activity-publish-success",
]
TITLE_LABEL_KEYWORDS = ["活动名称", "标题", "名称"]
DESCRIPTION_LABEL_KEYWORDS = ["活动描述", "活动详情", "详情", "描述", "介绍"]
SELECT_FIELD_KEYWORDS = {
    "date": ["活动时间", "开始时间", "结束时间", "集合时间", "报名截止"],
    "location": ["活动地点", "地址", "集合地点", "目的地", "出发地"],
    "category": ["活动类型", "骑行类型", "分类"],
    "level": ["难度", "级别"],
    "fee": ["费用", "报名费", "价格"],
    "count": ["人数", "人数上限", "名额"],
    "contact": ["联系方式", "联系人", "手机号", "微信"],
}
PLACEHOLDER_PATTERN = re.compile(r"(请输入|选择|填写|上传).+")
ACTIVITY_TESTDATA_FILE = Path(__file__).resolve().parents[2] / "tests" / "activity" / "testdata" / "publish_activity.yaml"
FAST_OPTIONAL_TAP_TIMEOUT = 0.5


@dataclass(frozen=True)
class ActivityItineraryItem:
    title: str
    subtitle: str
    body: str


@dataclass(frozen=True)
class ActivityDraft:
    title: str
    description: str
    itinerary: list[ActivityItineraryItem]
    activity_type: str
    province: str
    city: str
    album: str | None
    contact_name: str
    contact_phone: str
    location: str
    max_participants: str
    fee: str
    reference_duration: str
    total_mileage: str
    max_altitude: str
    elevation_gain: str
    scenery_tags: list[str]
    scenic_spots: list[str]


def build_activity_draft(*, testdata_path: Path | None = None) -> ActivityDraft:
    return _build_activity_draft_from_case(_load_activity_cases(testdata_path=testdata_path)[0])


def _load_activity_cases(*, testdata_path: Path | None = None) -> list[dict]:
    source_path = testdata_path or ACTIVITY_TESTDATA_FILE
    data = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    activities = data.get("activities", [])
    if not isinstance(activities, list) or not activities:
        raise AssertionError(f"Invalid or empty activity publish testdata: {source_path}")
    return [item for item in activities if isinstance(item, dict)]


def _build_activity_draft_from_case(case: dict) -> ActivityDraft:
    advanced = case.get("advancedOptions", {}) if isinstance(case.get("advancedOptions"), dict) else {}
    return ActivityDraft(
        title=str(case.get("activityName", "")).strip(),
        description=str(case.get("activityDescription", "")).strip(),
        itinerary=_normalize_itinerary(case.get("activityItinerary", "")),
        activity_type=str(case.get("activityType", "")).strip(),
        province=str(case.get("province", "")).strip(),
        city=str(case.get("city", "")).strip(),
        album=str(case.get("album", "")).strip() or None,
        contact_name=str(advanced.get("contactName", "自动化测试")).strip(),
        contact_phone=str(advanced.get("contactPhone", "13800138000")).strip(),
        location=str(advanced.get("defaultMeetingPoint", "")).strip(),
        max_participants=str(advanced.get("maxParticipants", "20")).strip(),
        fee=str(advanced.get("fee", "0")).strip(),
        reference_duration=str(advanced.get("referenceDuration", "")).strip(),
        total_mileage=str(advanced.get("totalMileage", "")).strip(),
        max_altitude=str(advanced.get("maxAltitude", "")).strip(),
        elevation_gain=str(advanced.get("elevationGain", "")).strip(),
        scenery_tags=_normalize_string_list(advanced.get("sceneryTags", [])),
        scenic_spots=_normalize_string_list(advanced.get("scenicSpots", [])),
    )


def wait_for_activity_form(driver: WebDriver, timeout: int = 30) -> str | None:
    return wait_for_any_accessibility_id_or_text(
        driver,
        FORM_READY_IDS,
        FORM_READY_TEXTS,
        timeout=timeout,
    )


def publish_activity(
    driver: WebDriver,
    draft: ActivityDraft,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 60,
) -> str:
    with _activity_profile("open-publisher"):
        open_activity_publisher(driver, ios_config=ios_config, timeout=timeout)
    with _activity_profile("fill-form"):
        fill_activity_form(driver, draft, timeout=timeout)
    with _activity_profile("submit-for-review"):
        return submit_activity_for_review(driver, expected_title=draft.title, timeout=timeout)


def open_activity_publisher(
    driver: WebDriver,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 30,
) -> None:
    end_at = time.monotonic() + timeout
    if ios_config is not None:
        try:
            from velowind_appium.session import ensure_logged_in_for_publish_entry

            ensure_logged_in_for_publish_entry(driver, ios_config)
        except Exception:
            pass
    _prepare_android_publish_entry(driver)

    while time.monotonic() < end_at:
        if login_required_from_page_source(_safe_page_source(driver)):
            if ios_config is None:
                raise AssertionError("Publish flow reached a login page but no iOS config was provided for re-login")
            ensure_logged_in_if_needed(driver, ios_config)
            end_at = time.monotonic() + timeout
            time.sleep(1)
            continue

        if activity_form_is_visible(_safe_page_source(driver)):
            return

        if _publish_sheet_visible(driver)() and _tap_activity_type_if_present(driver):
            if _wait_until(lambda: activity_form_is_visible(_safe_page_source(driver)), timeout=10):
                return

        if _tap_publish_entry_if_present(driver):
            _tap_activity_type_by_coordinate(driver)
            if _wait_until(lambda: activity_form_is_visible(_safe_page_source(driver)), timeout=2):
                return
            if _wait_until(lambda: _publish_sheet_visible(driver)(), timeout=1):
                if _tap_activity_type_if_present(driver) and _wait_until(
                    lambda: activity_form_is_visible(_safe_page_source(driver)),
                    timeout=8,
                ):
                    return
            _tap_activity_type_if_present(driver)
            if _wait_until(lambda: activity_form_is_visible(_safe_page_source(driver)), timeout=8):
                return
        time.sleep(0.5)

    raise AssertionError("Unable to open the activity publisher from the home page")


def _prepare_android_publish_entry(driver: WebDriver) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return
    try:
        from velowind_appium.modules.message_detail import _prepare_android_publish_entry as prepare_android_publish_entry

        prepare_android_publish_entry(driver)
    except Exception:
        return


def fill_activity_form(driver: WebDriver, draft: ActivityDraft, timeout: int = 60) -> None:
    wait_for_activity_form(driver, timeout=timeout)

    with _activity_profile("upload-image"):
        _upload_activity_image(driver, draft)
    with _activity_profile("fill-title"):
        _fill_title(driver, draft.title)
    with _activity_profile("select-activity-type"):
        _select_activity_type(driver, draft.activity_type)
    with _activity_profile("select-province"):
        _select_province(driver, draft.province)
    with _activity_profile("fill-city"):
        _fill_city(driver, draft.city)
    with _activity_profile("fill-description"):
        _fill_description(driver, draft.description)
    with _activity_profile("fill-itinerary"):
        _fill_itinerary(driver, draft.itinerary)
    with _activity_profile("fill-known-text-fields"):
        _fill_known_text_fields(driver, draft)
    with _activity_profile("fill-advanced-settings"):
        _fill_advanced_settings(driver, draft)
    with _activity_profile("resolve-picker-fields"):
        _resolve_picker_fields(driver, timeout=timeout)

    if not _required_field_markers_resolved(driver):
        raise AssertionError("The activity form still shows unresolved required placeholders after filling")


def submit_activity_for_review(driver: WebDriver, expected_title: str | None = None, timeout: int = 30) -> str:
    if not _tap_submit(driver):
        raise AssertionError("Unable to find the submit-for-review action on the activity form")

    end_at = time.monotonic() + timeout
    last_source = ""
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        last_source = page_source
        if not page_source:
            time.sleep(0.2)
            continue

        success_signal = activity_publish_success_signal(page_source, expected_title=expected_title)
        if success_signal:
            return success_signal

        if tap_text_if_present(driver, "确定", timeout=1) or tap_text_if_present(driver, "知道了", timeout=1):
            time.sleep(0.5)
        time.sleep(0.2)

    raise AssertionError(f"Activity publish did not expose a success signal after submit: {last_source[:500]}")


def activity_form_is_visible(page_source: str) -> bool:
    texts = _extract_strings(page_source)
    joined = " ".join(texts)
    if any(token in joined for token in PUBLISH_SHEET_TEXTS):
        return False
    return any(token in joined for token in FORM_READY_TEXTS)


def activity_publish_success_signal(page_source: str, expected_title: str | None = None) -> str | None:
    texts = _extract_strings(page_source)
    for token in SUCCESS_TEXTS:
        if token in texts or token in page_source:
            return token
    if expected_title and expected_title in page_source and "我的活动" in page_source:
        return "我的活动列表"
    if "审核" in page_source and "成功" in page_source:
        return "审核成功提示"
    return None


def _tap_publish_entry_if_present(driver: WebDriver) -> bool:
    if _tap_plus_button_by_coordinate(driver):
        return True
    for accessibility_id in PUBLISH_ENTRY_IDS:
        if tap_if_present(driver, accessibility_id, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            return True
    for text in PUBLISH_ENTRY_TEXTS:
        if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            return True
    for xpath in [
        '//*[@name="发布" or @label="发布" or @value="发布"]',
        '//*[@name="+" or @label="+" or @value="+"]',
        '//*[@name="＋" or @label="＋" or @value="＋"]',
        "//XCUIElementTypeOther[@x='160' and @y='791' and @width='82' and @height='39']",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _publish_sheet_visible(driver):
    def _check() -> bool:
        source = _safe_page_source(driver)
        return any(text in source for text in PUBLISH_SHEET_TEXTS)

    return _check


def _tap_activity_type_if_present(driver: WebDriver) -> bool:
    if _tap_activity_type_by_coordinate(driver):
        return True
    for accessibility_id in ACTIVITY_TYPE_IDS:
        if tap_if_present(driver, accessibility_id, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            return True
    for text in ACTIVITY_TYPE_TEXTS:
        if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            return True
    for xpath in [
        '//*[@name="活动" or @label="活动" or @value="活动"]',
        '//*[@name="发布活动" or @label="发布活动" or @value="发布活动"]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_activity_type_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.28),
                "y": int(rect["height"] * 0.84),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _fill_title(driver: WebDriver, title: str) -> None:
    for keyword in TITLE_LABEL_KEYWORDS:
        if _fill_input_near_label(driver, keyword, title, overwrite_existing=False):
            return
    title_input = _find_first_title_input(driver)
    if _field_has_user_value(title_input):
        return
    _replace_text(title_input, title)


def _fill_description(driver: WebDriver, description: str) -> None:
    with _activity_profile("description-open-editor"):
        opened = _open_editor(driver, "点击补充活动亮点、行程和适合人群")
    if opened:
        with _activity_profile("description-fill-editor"):
            _fill_editor_entry(driver, "活动概览", description)
        with _activity_profile("description-close-editor"):
            _close_editor(driver)
        _assert_editor_saved(driver, "点击补充活动亮点、行程和适合人群", "activity description")
        return
    for keyword in DESCRIPTION_LABEL_KEYWORDS:
        if _fill_input_near_label(driver, keyword, description, prefer_text_view=True):
            return
    raise AssertionError("Unable to open or fill the activity description editor")


def _fill_itinerary(driver: WebDriver, itinerary: list[ActivityItineraryItem]) -> None:
    if _itinerary_already_saved(_safe_page_source(driver), itinerary):
        return

    with _activity_profile("itinerary-open-editor"):
        opened = _open_editor(driver, "点击补充活动行程安排")
    if opened:
        for index, item in enumerate(itinerary):
            if index > 0:
                with _activity_profile(f"itinerary-{index}-dismiss-before-add"):
                    _dismiss_editor_keyboard_fast(driver)
                with _activity_profile(f"itinerary-{index}-add-segment"):
                    added = _add_itinerary_segment(driver)
                if not added:
                    raise AssertionError(f"Unable to add activity itinerary segment at index {index}")
            with _activity_profile(f"itinerary-{index}-fill-item"):
                _fill_itinerary_editor_item(driver, index, item)
        with _activity_profile("itinerary-close-editor"):
            _close_editor(driver)
        _assert_editor_saved(driver, "点击补充活动行程安排", "activity itinerary")
        return
    raise AssertionError("Unable to open or fill the activity itinerary editor")


def _itinerary_already_saved(page_source: str, itinerary: list[ActivityItineraryItem]) -> bool:
    if not page_source or not itinerary or "活动行程" not in page_source:
        return False
    source = html.unescape(page_source)
    return all(
        all(value and value in source for value in (item.title, item.subtitle, item.body))
        for item in itinerary
    )


def _fill_city(driver: WebDriver, city: str) -> None:
    for keyword in ["城市名称", "例如：杭州"]:
        if _fill_input_near_label(driver, keyword, city):
            _hide_keyboard(driver)
            return
    for xpath in [
        '//XCUIElementTypeTextField[contains(@value, "例如：")]',
        '//XCUIElementTypeTextField[@placeholderValue="例如：杭州"]',
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), city)
            _hide_keyboard(driver)
            return
        except (NoSuchElementException, WebDriverException):
            continue


def _select_activity_type(driver: WebDriver, activity_type: str) -> None:
    if not _tap_form_field(driver, "选择活动类型", fallback_point=(110, 404)):
        return
    _choose_specific_overlay_option(driver, activity_type)


def _select_province(driver: WebDriver, province: str) -> None:
    if not _tap_form_field(driver, "选择所属省份", fallback_point=(111, 499)):
        return
    _choose_specific_overlay_option(driver, _province_option_texts(province))


def _upload_activity_image(driver: WebDriver, draft: ActivityDraft) -> None:
    if not _tap_image_picker(driver):
        return

    if photo_picker.choose_photo_from_library(
        driver,
        album_name=draft.album,
        select_all_from_album=False,
        retry_sheet_option=_tap_activity_photo_library_sheet_option,
    ):
        return
    raise AssertionError("Unable to upload an activity image from the local photo library")


def _choose_photo_library_source(driver: WebDriver) -> bool:
    return photo_picker.choose_photo_library_source(driver)


def _choose_local_photo(driver: WebDriver, *, album_name: str | None = None) -> bool:
    return bool(photo_picker.choose_local_photo(driver, album_name=album_name))


def _photo_library_visible(driver: WebDriver, timeout: int = 5) -> bool:
    return bool(photo_picker.photo_library_visible(driver, timeout=timeout))


def _tap_activity_photo_library_sheet_option(driver: WebDriver) -> bool:
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.5,
                "y": size["height"] * 0.90,
            },
        )
        return True
    except WebDriverException:
        return False


def _fill_known_text_fields(driver: WebDriver, draft: ActivityDraft) -> None:
    page_source = _safe_page_source(driver)
    candidate_values = [
        ("contact-name", SELECT_FIELD_KEYWORDS["contact"], draft.contact_name),
        ("contact-phone", ["手机号", "联系电话", "联系方式"], draft.contact_phone),
        ("location", SELECT_FIELD_KEYWORDS["location"], draft.location),
        ("max-participants", SELECT_FIELD_KEYWORDS["count"], draft.max_participants),
        ("fee", SELECT_FIELD_KEYWORDS["fee"], draft.fee),
    ]
    for label, keywords, value in candidate_values:
        with _activity_profile(f"known-field-{label}"):
            if not any(keyword in page_source for keyword in keywords):
                continue
            for keyword in keywords:
                if _fill_input_near_label(driver, keyword, value, page_source=page_source):
                    break


def _resolve_picker_fields(driver: WebDriver, timeout: int = 60) -> None:
    due_time = time.monotonic() + timeout
    handled: set[str] = set()

    while time.monotonic() < due_time:
        page_source = _safe_page_source(driver)
        unresolved = _find_unresolved_placeholders(page_source)
        pending = [placeholder for placeholder in unresolved if placeholder not in handled]
        if not pending:
            return

        progress = False
        for placeholder in pending:
            handled.add(placeholder)
            if _select_placeholder_field(driver, placeholder):
                progress = True
                time.sleep(0.5)
                break

        if not progress:
            swipe_vertical(driver, direction="up")
            time.sleep(0.4)


def _required_field_markers_resolved(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    unresolved = _find_unresolved_placeholders(page_source)
    if not unresolved:
        return True
    return not any(
        any(
            keyword in placeholder
            for keyword in ("活动", "时间", "地点", "人数", "联系方式", "详情", "省份", "城市", "类型")
        )
        for placeholder in unresolved
    )


def _find_unresolved_placeholders(page_source: str) -> list[str]:
    return [
        text
        for text in _extract_strings(page_source)
        if PLACEHOLDER_PATTERN.match(text)
    ]


def _fill_input_near_label(
    driver: WebDriver,
    keyword: str,
    value: str,
    *,
    prefer_text_view: bool = False,
    overwrite_existing: bool = True,
    page_source: str | None = None,
) -> bool:
    if page_source is None:
        page_source = _safe_page_source(driver)
    if keyword not in page_source:
        return False

    if "<XCUIElementType" in page_source:
        return _fill_ios_input_near_visible_label(
            driver,
            keyword,
            value,
            prefer_text_view=prefer_text_view,
            overwrite_existing=overwrite_existing,
        )

    element_types = ["XCUIElementTypeTextView", "XCUIElementTypeTextField", "android.widget.EditText"]
    if prefer_text_view:
        element_types = ["XCUIElementTypeTextView", "XCUIElementTypeTextField", "android.widget.EditText"]
    else:
        element_types = ["XCUIElementTypeTextField", "android.widget.EditText", "XCUIElementTypeTextView"]

    xpath_templates = [
        f'//*[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]/following::{{element_type}}[1]',
        f'//{{element_type}}[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]',
        f'//*[contains(@text, "{keyword}")]/following::{{element_type}}[1]',
        f'//{{element_type}}[contains(@text, "{keyword}") or contains(@hint, "{keyword}")]',
    ]
    for element_type in element_types:
        for template in xpath_templates:
            xpath = template.format(element_type=element_type)
            try:
                element = driver.find_element(AppiumBy.XPATH, xpath)
                if not overwrite_existing and _field_has_user_value(element):
                    return True
                _replace_text(element, value)
                _hide_keyboard(driver)
                return True
            except (NoSuchElementException, WebDriverException, AttributeError):
                continue
    return False


def _fill_ios_input_near_visible_label(
    driver: WebDriver,
    keyword: str,
    value: str,
    *,
    prefer_text_view: bool = False,
    overwrite_existing: bool = True,
) -> bool:
    label_elements = _find_ios_visible_elements_containing(driver, keyword)
    if not label_elements:
        return False

    type_order = ["XCUIElementTypeTextView", "XCUIElementTypeTextField"] if prefer_text_view else [
        "XCUIElementTypeTextField",
        "XCUIElementTypeTextView",
    ]
    input_elements = []
    for element_type in type_order:
        try:
            input_elements.extend(driver.find_elements(AppiumBy.XPATH, f"//{element_type}[@visible='true']"))
        except WebDriverException:
            continue

    candidates = []
    for label in label_elements:
        label_rect = getattr(label, "rect", {}) or {}
        for field in input_elements:
            field_rect = getattr(field, "rect", {}) or {}
            distance = _ios_input_label_distance(label_rect, field_rect)
            if distance is None:
                continue
            candidates.append((distance, field))

    for _, field in sorted(candidates, key=lambda item: item[0]):
        try:
            if not overwrite_existing and _field_has_user_value(field):
                return True
            _replace_text(field, value)
            _hide_keyboard(driver)
            return True
        except (WebDriverException, AttributeError):
            continue
    return False


def _find_ios_visible_elements_containing(driver: WebDriver, keyword: str):
    xpath = (
        f'//*[@visible="true" and (contains(@name, "{keyword}") '
        f'or contains(@label, "{keyword}") or contains(@value, "{keyword}"))]'
    )
    try:
        return [
            element
            for element in driver.find_elements(AppiumBy.XPATH, xpath)
            if _element_is_visible(element)
        ]
    except WebDriverException:
        return []


def _ios_input_label_distance(label_rect: dict, field_rect: dict) -> float | None:
    try:
        label_x = float(label_rect.get("x", 0))
        label_y = float(label_rect.get("y", 0))
        label_width = float(label_rect.get("width", 0))
        label_height = float(label_rect.get("height", 0))
        field_x = float(field_rect.get("x", 0))
        field_y = float(field_rect.get("y", 0))
        field_width = float(field_rect.get("width", 0))
        field_height = float(field_rect.get("height", 0))
    except (TypeError, ValueError):
        return None
    if min(label_width, label_height, field_width, field_height) <= 0:
        return None

    vertical_gap = field_y - (label_y + label_height)
    same_column = field_x <= label_x + label_width + 80 and field_x + field_width >= label_x - 80
    right_of_label = field_x >= label_x + label_width - 20 and abs(field_y - label_y) <= 80
    if same_column and -8 <= vertical_gap <= 140:
        return abs(vertical_gap) + abs(field_x - label_x) * 0.05
    if right_of_label:
        return abs(field_x - (label_x + label_width)) + abs(field_y - label_y)
    return None


def _fill_first_empty_input(driver: WebDriver, value: str) -> None:
    _replace_text(_find_first_title_input(driver), value)


def _find_first_title_input(driver: WebDriver):
    for xpath in [
        '//XCUIElementTypeTextField[@value="" or not(@value)]',
        '//XCUIElementTypeTextField[contains(@value, "请输入")]',
    ]:
        try:
            return driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException):
            continue
    raise AssertionError("Unable to locate a title input in the activity publish form")


def _fill_first_empty_text_view(driver: WebDriver, value: str) -> None:
    for xpath in [
        '//XCUIElementTypeTextView[@value="" or not(@value)]',
        '//XCUIElementTypeTextView[contains(@value, "请输入")]',
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), value)
            return
        except (NoSuchElementException, WebDriverException):
            continue


def _replace_text(element, value: str) -> None:
    element.click()
    try:
        element.clear()
    except WebDriverException:
        pass
    element.send_keys(value)


def _hide_keyboard(driver: WebDriver) -> None:
    for kwargs in [
        {},
        {"key_name": "Done"},
        {"key_name": "Return"},
        {"key_name": "Next"},
        {"strategy": "pressKey", "key_name": "Done"},
    ]:
        try:
            driver.hide_keyboard(**kwargs)
            return
        except WebDriverException:
            continue
    _dismiss_keyboard_with_safe_tap(driver)


def _dismiss_keyboard_with_safe_tap(driver: WebDriver) -> None:
    for text in ["完成", "收起键盘", "隐藏", "确定"]:
        if tap_text_if_present(driver, text, timeout=1):
            time.sleep(0.2)
            return
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.9,
                "y": size["height"] * 0.18,
            },
        )
        time.sleep(0.2)
    except WebDriverException:
        pass


def _field_has_user_value(element) -> bool:
    try:
        current_value = (element.get_attribute("value") or "").strip()
    except WebDriverException:
        current_value = ""
    if not current_value:
        try:
            current_value = (element.get_attribute("text") or "").strip()
        except WebDriverException:
            current_value = ""
    try:
        placeholder_value = (element.get_attribute("placeholderValue") or "").strip()
    except WebDriverException:
        placeholder_value = ""
    if not placeholder_value:
        try:
            placeholder_value = (element.get_attribute("hint") or "").strip()
        except WebDriverException:
            placeholder_value = ""
    try:
        showing_hint = str(element.get_attribute("showing-hint") or "").lower() == "true"
    except WebDriverException:
        showing_hint = False
    if showing_hint:
        return False
    if not current_value:
        return False
    if placeholder_value and current_value == placeholder_value:
        return False
    if any(token in current_value for token in ["请输入", "选择", "填写", "上传"]):
        return False
    return True


def _select_placeholder_field(driver: WebDriver, placeholder: str) -> bool:
    if not _tap_placeholder(driver, placeholder):
        return False

    if any(keyword in placeholder for keyword in SELECT_FIELD_KEYWORDS["date"]):
        return _confirm_date_picker(driver)
    if any(keyword in placeholder for keyword in SELECT_FIELD_KEYWORDS["location"]):
        return _choose_first_option(driver, preferred_texts=["上海", "杭州", "北京", "确定", "完成"])
    if any(keyword in placeholder for keyword in SELECT_FIELD_KEYWORDS["category"]):
        return _choose_first_option(driver, preferred_texts=["骑行", "休闲", "确定", "完成"])
    if any(keyword in placeholder for keyword in SELECT_FIELD_KEYWORDS["level"]):
        return _choose_first_option(driver, preferred_texts=["初级", "中级", "轻松", "确定", "完成"])
    if any(keyword in placeholder for keyword in SELECT_FIELD_KEYWORDS["count"]):
        return _choose_first_option(driver, preferred_texts=["20", "30", "50", "确定", "完成"])
    if any(keyword in placeholder for keyword in SELECT_FIELD_KEYWORDS["fee"]):
        return _choose_first_option(driver, preferred_texts=["免费", "0", "确定", "完成"])
    if any(keyword in placeholder for keyword in SELECT_FIELD_KEYWORDS["contact"]):
        return _choose_first_option(driver, preferred_texts=["确定", "完成"])

    return _choose_first_option(driver, preferred_texts=["确定", "完成"])


def _open_editor(driver: WebDriver, entry_text: str) -> bool:
    _hide_keyboard(driver)
    baseline = _safe_page_source(driver)
    if not _tap_form_field(driver, entry_text):
        return False

    if _wait_until(lambda: _editor_opened(_safe_page_source(driver), baseline, entry_text), timeout=4):
        return True

    try:
        element = driver.find_element(
            AppiumBy.XPATH,
            f'//*[@name="{entry_text}" or @label="{entry_text}" or @value="{entry_text}"]',
        )
        rect = element.rect
        driver.execute_script("mobile: tap", {"x": 201, "y": rect["y"] + rect["height"] / 2})
    except (NoSuchElementException, WebDriverException, AttributeError):
        return False

    return _wait_until(lambda: _editor_opened(_safe_page_source(driver), baseline, entry_text), timeout=4)


def _editor_opened(page_source: str, baseline: str, entry_text: str) -> bool:
    if not page_source or page_source == baseline:
        return False
    if "编辑活动说明" in page_source or "编辑活动行程" in page_source:
        return True
    if entry_text in page_source and "提交审核" in page_source:
        return False
    return "完成" in page_source or "请输入" in page_source


def _fill_editor_body(driver: WebDriver, body: str) -> None:
    for xpath in [
        '//android.widget.EditText[@text="请输入正文" or @hint="请输入正文"]',
        '//XCUIElementTypeTextView',
        '//XCUIElementTypeTextField[contains(@value, "请输入正文")]',
        '//XCUIElementTypeTextField[1]',
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), body)
            return
        except (NoSuchElementException, WebDriverException):
            continue


def _fill_editor_entry(driver: WebDriver, title: str, body: str) -> None:
    _fill_editor_title(driver, title)
    _fill_editor_body(driver, body)


def _fill_editor_title(driver: WebDriver, title: str) -> None:
    for xpath in [
        '//android.widget.EditText[@text="活动概览" or @hint="活动概览"]',
        '//XCUIElementTypeTextField[1]',
        '//XCUIElementTypeTextField[@placeholderValue="活动概览"]',
        '//XCUIElementTypeTextField[@placeholderValue="活动行程"]',
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), title)
            return
        except (NoSuchElementException, WebDriverException):
            continue


def _fill_itinerary_editor_item(driver: WebDriver, index: int, item: ActivityItineraryItem) -> None:
    with _activity_profile(f"itinerary-{index}-fill-title"):
        _fill_indexed_editor_text_field(driver, "标题", item.title, index)
    with _activity_profile(f"itinerary-{index}-dismiss-after-title"):
        _dismiss_editor_keyboard_fast(driver)
    with _activity_profile(f"itinerary-{index}-fill-subtitle"):
        _fill_indexed_editor_text_field(driver, "副标题", item.subtitle, index)
    with _activity_profile(f"itinerary-{index}-dismiss-after-subtitle"):
        _dismiss_editor_keyboard_fast(driver)
    with _activity_profile(f"itinerary-{index}-fill-body"):
        _fill_indexed_editor_text_view(driver, item.body, index)
    with _activity_profile(f"itinerary-{index}-dismiss-after-body"):
        _dismiss_editor_keyboard_fast(driver)


def _fill_indexed_editor_text_field(driver: WebDriver, placeholder: str, value: str, index: int) -> None:
    field = _find_indexed_editor_text_field(driver, placeholder, index)
    _replace_text(field, value)


def _fill_indexed_editor_text_view(driver: WebDriver, value: str, index: int) -> None:
    field = _find_indexed_editor_text_view(driver, index)
    _replace_text(field, value)


def _find_indexed_editor_text_field(driver: WebDriver, placeholder: str, index: int):
    xpaths = [
        (
            f'//XCUIElementTypeTextField[@placeholderValue="{placeholder}" '
            f'or @value="{placeholder}" or @name="{placeholder}" or @label="{placeholder}"]'
        ),
        f'//android.widget.EditText[@text="{placeholder}" or @hint="{placeholder}"]',
    ]
    return _find_indexed_visible_editor_element(driver, xpaths, index, f"activity itinerary {placeholder}")


def _find_indexed_editor_text_view(driver: WebDriver, index: int):
    return _find_indexed_visible_editor_element(
        driver,
        [
            "//XCUIElementTypeTextView",
            '//android.widget.EditText[@text="正文" or @hint="正文"]',
        ],
        index,
        "activity itinerary body",
    )


def _find_indexed_visible_editor_element(driver: WebDriver, xpath: str | list[str], index: int, field_name: str):
    xpaths = [xpath] if isinstance(xpath, str) else xpath
    for _ in range(5):
        elements = []
        for candidate_xpath in xpaths:
            try:
                elements.extend(driver.find_elements(AppiumBy.XPATH, candidate_xpath))
            except WebDriverException:
                continue
        visible_elements = sorted(
            [element for element in elements if _element_is_visible(element)],
            key=lambda element: (element.rect.get("y", 0), element.rect.get("x", 0)),
        )
        if len(visible_elements) > index:
            return visible_elements[index]
        swipe_vertical(driver, direction="up")
        time.sleep(0.2)
    raise AssertionError(f"Unable to find {field_name} at index {index}")


def _element_is_visible(element) -> bool:
    try:
        if not element.is_displayed():
            return False
    except WebDriverException:
        pass
    rect = getattr(element, "rect", {}) or {}
    return (rect.get("width", 0) or 0) > 0 and (rect.get("height", 0) or 0) > 0


def _add_itinerary_segment(driver: WebDriver) -> bool:
    before_count = _count_itinerary_editor_sections(_safe_page_source(driver))
    for _ in range(4):
        button = _find_add_itinerary_segment_button(driver)
        if button is None:
            swipe_vertical(driver, direction="up")
            time.sleep(0.2)
            continue
        _tap_element_center(driver, button)
        if _wait_until(lambda: _count_itinerary_editor_sections(_safe_page_source(driver)) > before_count, timeout=4):
            return True
    return False


def _find_add_itinerary_segment_button(driver: WebDriver):
    buttons = []
    for xpath in [
        '//XCUIElementTypeOther[@width="30" and @height="30"]',
        "//android.view.ViewGroup[com.horcrux.svg.SvgView]",
    ]:
        try:
            buttons.extend(driver.find_elements(AppiumBy.XPATH, xpath))
        except WebDriverException:
            continue
    visible_buttons = sorted(
        [button for button in buttons if _element_is_visible(button)],
        key=lambda button: (button.rect.get("y", 0), button.rect.get("x", 0)),
    )
    return visible_buttons[-1] if visible_buttons else None


def _count_itinerary_editor_sections(page_source: str) -> int:
    if not page_source:
        return 0
    ios_count = len(
        re.findall(
            r'<XCUIElementTypeTextField[^>]*visible="true"[^>]*placeholderValue="标题"',
            page_source,
        )
    )
    android_count = len(
        re.findall(
            r'<node\b(?=[^>]*\bclass="android\.widget\.EditText")(?=[^>]*\btext="标题")[^>]*>',
            page_source,
        )
    ) + len(
        re.findall(
            r'<android\.widget\.EditText\b(?=[^>]*\btext="标题")[^>]*>',
            page_source,
        )
    )
    return ios_count + android_count


def _normalize_itinerary(raw_itinerary) -> list[ActivityItineraryItem]:
    if isinstance(raw_itinerary, dict):
        item = _normalize_itinerary_item(raw_itinerary, 1)
        return [item] if item is not None else []

    if isinstance(raw_itinerary, list):
        items = [
            _normalize_itinerary_item(item, index)
            for index, item in enumerate(raw_itinerary, start=1)
        ]
        return [item for item in items if item is not None]

    text = str(raw_itinerary or "").strip()
    if not text:
        return []

    parts = [segment.strip() for segment in re.split(r"[；;\n]+", text) if segment.strip()]
    items = [
        _normalize_itinerary_item(segment, index)
        for index, segment in enumerate(parts, start=1)
    ]
    return [item for item in items if item is not None]


def _normalize_itinerary_item(raw_item, index: int) -> ActivityItineraryItem | None:
    if isinstance(raw_item, dict):
        title = str(raw_item.get("title", "")).strip()
        subtitle = str(raw_item.get("subtitle", "")).strip()
        body = str(
            raw_item.get("body")
            or raw_item.get("content")
            or raw_item.get("description")
            or ""
        ).strip()
        if not any([title, subtitle, body]):
            return None
        fallback_title = title or f"Day{index}"
        return ActivityItineraryItem(title=fallback_title, subtitle=subtitle, body=body)

    text = str(raw_item or "").strip()
    if not text:
        return None

    match = re.match(r"^(D\d+|Day\d+)\s+(.*)$", text, flags=re.IGNORECASE)
    if match:
        return ActivityItineraryItem(
            title=match.group(1),
            subtitle="",
            body=match.group(2).strip(),
        )
    return ActivityItineraryItem(title=f"Day{index}", subtitle="", body=text)


def _normalize_string_list(raw_value) -> list[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        return [token.strip() for token in re.split(r"[,，、\s]+", raw_value) if token.strip()]
    return []


def _fill_advanced_settings(driver: WebDriver, draft: ActivityDraft) -> None:
    advanced_values = [
        (["参考时长", "活动时长", "时长"], draft.reference_duration, ["2天1晚", "例如：2天1晚"]),
        (["总里程", "里程"], draft.total_mileage, ["例如：68km"]),
        (["最高海拔", "海拔"], draft.max_altitude, ["例如：812m"]),
        (["累计爬升", "爬升"], draft.elevation_gain, ["例如：1260m"]),
        (["风景标签", "景色标签", "风景"], "，".join(draft.scenery_tags), ["例如：山景、湖景、日落"]),
        (["沿途景点", "途经景点", "景点"], "，".join(draft.scenic_spots), ["例如：龙井村、十里琅珰、九溪烟树"]),
    ]
    advanced_values = [(keywords, value, placeholders) for keywords, value, placeholders in advanced_values if value]
    if not advanced_values:
        return

    if not _open_advanced_settings(driver, advanced_values):
        raise AssertionError("Unable to open activity advanced settings")

    for keywords, value, placeholders in advanced_values:
        if not _fill_advanced_field(driver, keywords, value, placeholders):
            raise AssertionError(f"Unable to fill advanced activity field: {keywords[0]}")


def _fill_advanced_field(driver: WebDriver, keywords: list[str], value: str, placeholders: list[str] | None = None) -> bool:
    for _ in range(4):
        if placeholders:
            for placeholder in placeholders:
                if _fill_input_by_placeholder(driver, placeholder, value):
                    return True
        for keyword in keywords:
            if _fill_input_near_label(driver, keyword, value):
                return True
        swipe_vertical(driver, direction="up")
        time.sleep(0.2)
    return False


def _fill_input_by_placeholder(driver: WebDriver, placeholder: str, value: str) -> bool:
    xpaths = [
        f'//XCUIElementTypeTextField[@placeholderValue="{placeholder}" or @value="{placeholder}"]',
        f'//XCUIElementTypeTextView[@placeholderValue="{placeholder}" or @value="{placeholder}"]',
        f'//android.widget.EditText[@hint="{placeholder}" or @text="{placeholder}"]',
    ]
    for xpath in xpaths:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            if not _element_is_visible(element):
                continue
            _replace_text(element, value)
            _hide_keyboard(driver)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return False


def _open_advanced_settings(driver: WebDriver, advanced_values: list[tuple[list[str], str, list[str]]]) -> bool:
    for _ in range(5):
        page_source = _safe_page_source(driver)
        if _advanced_field_visible(page_source, advanced_values):
            return True
        for text in ["高级设置", "更多信息", "更多设置", "展开更多", "补充更多信息"]:
            if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
                time.sleep(0.5)
                if _advanced_field_visible(_safe_page_source(driver), advanced_values):
                    return True
        if _tap_advanced_settings_row(driver, page_source=page_source):
            time.sleep(0.5)
            if _advanced_field_visible(_safe_page_source(driver), advanced_values):
                return True
        swipe_vertical(driver, direction="up")
        time.sleep(0.3)
    return _advanced_field_visible(_safe_page_source(driver), advanced_values)


def _advanced_field_visible(page_source: str, advanced_values: list[tuple]) -> bool:
    if not page_source:
        return False
    if "<XCUIElementType" in page_source:
        return _ios_advanced_field_visible(page_source, advanced_values)
    return any(keyword in page_source for item in advanced_values for keyword in item[0])


def _ios_advanced_field_visible(page_source: str, advanced_values: list[tuple]) -> bool:
    try:
        root = ET.fromstring(page_source)
    except ET.ParseError:
        return False
    keywords = [keyword for item in advanced_values for keyword in item[0]]
    for element in root.iter():
        if element.attrib.get("visible") != "true":
            continue
        text = _element_text(element)
        if not any(keyword in text for keyword in keywords):
            continue
        try:
            y = int(float(element.attrib.get("y", "0")))
        except ValueError:
            y = 0
        if y > 120:
            return True
    return False


def _tap_advanced_settings_row(driver: WebDriver, *, page_source: str | None = None) -> bool:
    page_source = page_source if page_source is not None else _safe_page_source(driver)
    if "<XCUIElementType" in page_source:
        return _tap_ios_advanced_settings_row(driver)

    for text in ["高级选项", "高级设置"]:
        try:
            element = driver.find_element(
                AppiumBy.XPATH,
                f'//*[contains(@text, "{text}") or contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
            )
            rect = element.rect
            window_rect = driver.get_window_rect()
            driver.execute_script(
                "mobile: tap",
                {
                    "x": int(window_rect["width"] * 0.91),
                    "y": int(rect["y"] + rect["height"] / 2),
                },
            )
            return True
        except (NoSuchElementException, WebDriverException, AttributeError, KeyError, TypeError):
            continue
    return False


def _tap_ios_advanced_settings_row(driver: WebDriver) -> bool:
    for text in ["高级选项", "高级设置"]:
        try:
            elements = driver.find_elements(
                AppiumBy.XPATH,
                f'//*[@name="{text}" or @label="{text}" or @value="{text}"]',
            )
        except (WebDriverException, AttributeError):
            elements = []

        candidates = []
        for element in elements:
            try:
                rect = element.rect
                width = int(rect.get("width", 0))
                height = int(rect.get("height", 0))
                y = int(rect.get("y", 0))
            except (AttributeError, TypeError, ValueError):
                continue
            if width <= 0 or height <= 0 or height > 120 or y < 100:
                continue
            candidates.append((width, height, y, rect))

        if not candidates:
            continue

        _, _, _, rect = max(candidates, key=lambda item: (item[0], item[1]))
        try:
            driver.execute_script(
                "mobile: tap",
                {
                    "x": int(rect["x"] + rect["width"] - min(28, max(12, rect["width"] * 0.08))),
                    "y": int(rect["y"] + rect["height"] / 2),
                },
            )
            return True
        except (WebDriverException, KeyError, TypeError, ValueError):
            continue
    return False


def _close_editor(driver: WebDriver) -> None:
    _dismiss_editor_keyboard_fast(driver)
    _tap_editor_title(driver)
    time.sleep(0.2)
    if _tap_editor_bottom_done(driver):
        if _wait_until(lambda: not _editor_page_visible(_safe_page_source(driver)), timeout=4):
            return
    _dismiss_editor_keyboard_fast(driver)
    _tap_editor_title(driver)
    time.sleep(0.2)
    if _tap_editor_bottom_done(driver):
        if _wait_until(lambda: not _editor_page_visible(_safe_page_source(driver)), timeout=4):
            return
    if _tap_editor_done_slot(driver):
        if _wait_until(lambda: not _editor_page_visible(_safe_page_source(driver)), timeout=4):
            return
    for xpath in [
        "//XCUIElementTypeOther[@x='72' and @y='85' and @width='20' and @height='20']",
        "(//XCUIElementTypeStaticText[@name='编辑活动说明' or @label='编辑活动说明']/preceding::XCUIElementTypeOther[@visible='true'])[last()]",
        "(//XCUIElementTypeStaticText[@name='编辑活动行程' or @label='编辑活动行程']/preceding::XCUIElementTypeOther[@visible='true'])[last()]",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            if _wait_until(lambda: not _editor_page_visible(_safe_page_source(driver)), timeout=4):
                return
        except (NoSuchElementException, WebDriverException):
            continue
    try:
        driver.back()
        if _wait_until(lambda: not _editor_page_visible(_safe_page_source(driver)), timeout=4):
            return
        time.sleep(0.5)
    except WebDriverException:
        pass
    try:
        driver.execute_script("mobile: tap", {"x": 82, "y": 95})
        if _wait_until(lambda: not _editor_page_visible(_safe_page_source(driver)), timeout=4):
            return
    except WebDriverException:
        pass
    raise AssertionError("Unable to close the activity editor and return to the publish form")


def _dismiss_editor_keyboard(driver: WebDriver) -> None:
    _hide_keyboard(driver)
    _tap_outside_editor(driver)
    time.sleep(0.2)


def _dismiss_editor_keyboard_fast(driver: WebDriver) -> None:
    if _tap_outside_editor(driver):
        time.sleep(0.2)
        return
    _dismiss_editor_keyboard(driver)


def _tap_outside_editor(driver: WebDriver) -> bool:
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(size["width"] * 0.9),
                "y": int(size["height"] * 0.18),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        try:
            driver.execute_script("mobile: tap", {"x": 361, "y": 157})
            return True
        except WebDriverException:
            return False


def _tap_editor_title(driver: WebDriver) -> bool:
    try:
        driver.execute_script("mobile: tap", _editor_title_payload(driver))
        return True
    except WebDriverException:
        return False


def _editor_title_payload(driver: WebDriver) -> dict[str, int]:
    try:
        size = driver.get_window_size()
        return {
            "x": int(size["width"] * 0.5),
            "y": int(size["height"] * 0.11),
        }
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return {"x": 201, "y": 95}


def _tap_editor_bottom_done(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "完成", timeout=1):
        return True
    for xpath in [
        '(//*[@name="完成" or @label="完成" or @value="完成"])[last()]',
        '//XCUIElementTypeOther[@name="完成" or @label="完成"]',
    ]:
        try:
            rect = driver.find_element(AppiumBy.XPATH, xpath).rect
            driver.execute_script(
                "mobile: tap",
                {
                    "x": int(rect["x"] + rect["width"] / 2),
                    "y": int(rect["y"] + rect["height"] / 2),
                },
            )
            return True
        except (NoSuchElementException, WebDriverException, KeyError, TypeError):
            continue
    try:
        driver.execute_script("mobile: tap", _editor_bottom_done_payload(driver))
        return True
    except WebDriverException:
        return False


def _editor_bottom_done_payload(driver: WebDriver) -> dict[str, int]:
    try:
        size = driver.get_window_size()
        return {
            "x": int(size["width"] * 0.56),
            "y": int(size["height"] * 0.94),
        }
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return {"x": 225, "y": 821}


def _assert_editor_saved(driver: WebDriver, placeholder: str, field_name: str) -> None:
    page_source = _safe_page_source(driver)
    if placeholder in page_source:
        raise AssertionError(f"The {field_name} placeholder is still visible after closing the editor")


def _tap_editor_done_slot(driver: WebDriver) -> bool:
    try:
        driver.execute_script("mobile: tap", _editor_done_payload(driver))
        return True
    except WebDriverException:
        return False


def _editor_done_payload(driver: WebDriver) -> dict[str, int]:
    try:
        size = driver.get_window_size()
        return {
            "x": int(size["width"] * 0.92),
            "y": int(size["height"] * 0.11),
        }
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return {"x": 370, "y": 95}


def _editor_page_visible(page_source: str) -> bool:
    return "编辑活动说明" in page_source or "编辑活动行程" in page_source


def _tap_image_picker(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        try:
            picker = driver.find_element(
                AppiumBy.XPATH,
                '(//android.widget.TextView[@text="活动图片"]'
                '/following::android.widget.HorizontalScrollView[1]//android.view.ViewGroup)[1]',
            )
            _tap_element_center(driver, picker)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            pass
    try:
        driver.execute_script("mobile: tap", {"x": 60, "y": 206})
        return True
    except WebDriverException:
        pass
    for xpath in [
        "//XCUIElementTypeOther[@x='13' and @y='161' and @width='94' and @height='94']",
        "//XCUIElementTypeOther[@x='13' and @y='161' and @width='90' and @height='90']",
        "//XCUIElementTypeOther[@x='25' and @y='115' and @width='101' and @height='100']",
        "//XCUIElementTypeOther[@x='26' and @y='159' and @width='96' and @height='96']",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_form_field(driver: WebDriver, text: str, fallback_point: tuple[int, int] | None = None) -> bool:
    if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
        return True

    if fallback_point is not None:
        try:
            driver.execute_script("mobile: tap", {"x": fallback_point[0], "y": fallback_point[1]})
            return True
        except WebDriverException:
            return False
    return False


def _tap_placeholder(driver: WebDriver, placeholder: str) -> bool:
    if tap_text_if_present(driver, placeholder, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
        return True
    return False


def _tap_element_center(driver: WebDriver, element) -> None:
    rect = element.rect
    driver.execute_script(
        "mobile: tap",
        {
            "x": rect["x"] + rect["width"] / 2,
            "y": rect["y"] + rect["height"] / 2,
        },
    )


def _confirm_date_picker(driver: WebDriver) -> bool:
    try:
        driver.execute_script(
            "mobile: selectPickerWheelValue",
            {"order": "next", "offset": 0.2, "element": _first_picker_wheel(driver).id},
        )
    except (NoSuchElementException, WebDriverException):
        pass

    for text in ["确定", "完成", "保存"]:
        if tap_text_if_present(driver, text, timeout=2):
            return True
    return True


def _first_picker_wheel(driver: WebDriver):
    return driver.find_element(AppiumBy.XPATH, "//XCUIElementTypePickerWheel[1]")


def _province_option_texts(province: str) -> list[str]:
    candidates = [province]
    if not province.endswith(("省", "市", "自治区", "特别行政区")):
        candidates.extend([f"{province}市", f"{province}省"])
    else:
        candidates.append(province.removesuffix("省").removesuffix("市"))
    return [candidate for candidate in candidates if candidate]


def _choose_specific_overlay_option(driver: WebDriver, texts: str | list[str]) -> bool:
    target_texts = [texts] if isinstance(texts, str) else texts

    for text in target_texts:
        if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            _confirm_overlay_selection(driver)
            return True

    for text in target_texts:
        for xpath in [
            f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
        ]:
            try:
                _tap_element_center(driver, driver.find_element(AppiumBy.XPATH, xpath))
                _confirm_overlay_selection(driver)
                return True
            except (NoSuchElementException, WebDriverException, AttributeError):
                continue

    for text in target_texts:
        if _set_first_picker_wheel_value(driver, text):
            _confirm_overlay_selection(driver)
            return True

    for _ in range(8):
        try:
            swipe_vertical(driver, direction="up")
        except WebDriverException:
            pass
        time.sleep(0.3)
        for text in target_texts:
            if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
                _confirm_overlay_selection(driver)
                return True

    return False


def _set_first_picker_wheel_value(driver: WebDriver, text: str) -> bool:
    try:
        _first_picker_wheel(driver).send_keys(text)
        return True
    except (NoSuchElementException, WebDriverException, AttributeError):
        return False


def _confirm_overlay_selection(driver: WebDriver) -> None:
    for text in ["确定", "完成"]:
        if tap_text_if_present(driver, text, timeout=1):
            return


def _choose_first_option(driver: WebDriver, preferred_texts: list[str]) -> bool:
    for text in preferred_texts:
        if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            return True

    for xpath in [
        "(//XCUIElementTypeCell)[1]",
        "(//XCUIElementTypeButton)[1]",
        "(//XCUIElementTypeStaticText)[1]",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            tap_text_if_present(driver, "确定", timeout=1)
            tap_text_if_present(driver, "完成", timeout=1)
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_submit(driver: WebDriver) -> bool:
    for accessibility_id in ["submit-audit-button", "activity-submit-button", "publish-submit-button"]:
        if tap_if_present(driver, accessibility_id, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            return True
    if _tap_submit_button_center(driver):
        return True
    for text in ["提交审核", "提交", "发布"]:
        if tap_text_if_present(driver, text, timeout=FAST_OPTIONAL_TAP_TIMEOUT):
            return True
    return False


def _tap_submit_button_center(driver: WebDriver) -> bool:
    try:
        elements = driver.find_elements(
            AppiumBy.XPATH,
            '//*[@name="提交审核" or @label="提交审核" or @value="提交审核"]',
        )
    except (AttributeError, WebDriverException):
        return False

    candidates = []
    for element in elements:
        try:
            rect = element.rect
        except (AttributeError, WebDriverException):
            continue
        if (
            (rect.get("width", 0) or 0) >= 120
            and (rect.get("height", 0) or 0) >= 40
            and (rect.get("y", 0) or 0) >= 700
        ):
            candidates.append(element)

    for element in sorted(candidates, key=lambda item: item.rect.get("y", 0), reverse=True):
        try:
            _tap_element_center(driver, element)
            return True
        except (AttributeError, WebDriverException):
            continue
    return False


def _tap_plus_button_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        capabilities = getattr(driver, "capabilities", {}) or {}
        platform = str(capabilities.get("platformName", "")).lower()
        x = int(rect["width"] * 0.5)
        if platform == "android":
            for y_ratio in (0.935, 0.948, 0.958, 0.968):
                driver.execute_script("mobile: tap", {"x": x, "y": int(rect["height"] * y_ratio)})
                if _wait_until(lambda: _publish_entry_opened(_safe_page_source(driver)), timeout=1):
                    return True
            return False
        y = int(rect["height"] * 0.93)
        driver.execute_script("mobile: tap", {"x": x, "y": y})
        return True
    except WebDriverException:
        return False


def _publish_entry_opened(page_source: str) -> bool:
    return activity_form_is_visible(page_source) or any(text in page_source for text in PUBLISH_SHEET_TEXTS)


def _wait_until(predicate, timeout: int) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def _activity_profile_enabled() -> bool:
    return os.getenv("VW_ACTIVITY_PROFILE", "").strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def _activity_profile(label: str):
    started_at = time.monotonic()
    yield
    if _activity_profile_enabled():
        elapsed = time.monotonic() - started_at
        print(f"[activity-profile] {label}: {elapsed:.2f}s", flush=True)


def _extract_strings(page_source: str) -> list[str]:
    values = re.findall(r'(?:text|name|label|value)="([^"]+)"', page_source)
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = html.unescape(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _element_text(element) -> str:
    return " ".join(
        html.unescape(element.attrib.get(attribute, "")).strip()
        for attribute in ("text", "name", "label", "value")
        if element.attrib.get(attribute, "").strip()
    )


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""
