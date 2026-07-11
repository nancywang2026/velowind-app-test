from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import html
from pathlib import Path
import re
import time

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
        contact_name="自动化测试",
        contact_phone="13800138000",
        location=str(advanced.get("defaultMeetingPoint", "")).strip(),
        max_participants="20",
        fee="0",
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
    open_activity_publisher(driver, ios_config=ios_config, timeout=timeout)
    fill_activity_form(driver, draft, timeout=timeout)
    return submit_activity_for_review(driver, expected_title=draft.title, timeout=timeout)


def open_activity_publisher(
    driver: WebDriver,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 30,
) -> None:
    end_at = time.monotonic() + timeout

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
            time.sleep(1)
            _tap_activity_type_if_present(driver)
            if _wait_until(lambda: activity_form_is_visible(_safe_page_source(driver)), timeout=10):
                return
        time.sleep(0.5)

    raise AssertionError("Unable to open the activity publisher from the home page")


def fill_activity_form(driver: WebDriver, draft: ActivityDraft, timeout: int = 60) -> None:
    wait_for_activity_form(driver, timeout=timeout)

    _upload_activity_image(driver, draft)
    _fill_title(driver, draft.title)
    _select_activity_type(driver, draft.activity_type)
    _select_province(driver, draft.province)
    _fill_city(driver, draft.city)
    _fill_description(driver, draft.description)
    _fill_itinerary(driver, draft.itinerary)
    _fill_known_text_fields(driver, draft)
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
    for accessibility_id in PUBLISH_ENTRY_IDS:
        if tap_if_present(driver, accessibility_id, timeout=2):
            return True
    for text in PUBLISH_ENTRY_TEXTS:
        if tap_text_if_present(driver, text, timeout=2):
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
    if _tap_plus_button_by_coordinate(driver):
        return True
    return False


def _publish_sheet_visible(driver):
    def _check() -> bool:
        source = _safe_page_source(driver)
        return any(text in source for text in PUBLISH_SHEET_TEXTS)

    return _check


def _tap_activity_type_if_present(driver: WebDriver) -> bool:
    for accessibility_id in ACTIVITY_TYPE_IDS:
        if tap_if_present(driver, accessibility_id, timeout=2):
            return True
    for text in ACTIVITY_TYPE_TEXTS:
        if tap_text_if_present(driver, text, timeout=2):
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


def _fill_title(driver: WebDriver, title: str) -> None:
    for keyword in TITLE_LABEL_KEYWORDS:
        if _fill_input_near_label(driver, keyword, title, overwrite_existing=False):
            return
    title_input = _find_first_title_input(driver)
    if _field_has_user_value(title_input):
        return
    _replace_text(title_input, title)


def _fill_description(driver: WebDriver, description: str) -> None:
    if _open_editor(driver, "点击补充活动亮点、行程和适合人群"):
        _fill_editor_entry(driver, "活动概览", description)
        _close_editor(driver)
        _assert_editor_saved(driver, "点击补充活动亮点、行程和适合人群", "activity description")
        return
    for keyword in DESCRIPTION_LABEL_KEYWORDS:
        if _fill_input_near_label(driver, keyword, description, prefer_text_view=True):
            return
    raise AssertionError("Unable to open or fill the activity description editor")


def _fill_itinerary(driver: WebDriver, itinerary: list[ActivityItineraryItem]) -> None:
    if _open_editor(driver, "点击补充活动行程安排"):
        for index, item in enumerate(itinerary):
            if index > 0:
                _dismiss_editor_keyboard(driver)
                if not _add_itinerary_segment(driver):
                    raise AssertionError(f"Unable to add activity itinerary segment at index {index}")
            _fill_itinerary_editor_item(driver, index, item)
        _close_editor(driver)
        _assert_editor_saved(driver, "点击补充活动行程安排", "activity itinerary")
        return
    raise AssertionError("Unable to open or fill the activity itinerary editor")


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

    if not _choose_photo_library_source(driver):
        raise AssertionError("Unable to choose phone photo library as the image source")

    for text in ["允许访问所有照片", "允许", "好"]:
        tap_text_if_present(driver, text, timeout=2)

    if not _photo_library_visible(driver, timeout=5):
        _tap_activity_photo_library_sheet_option(driver)
        for text in ["允许访问所有照片", "允许", "好"]:
            tap_text_if_present(driver, text, timeout=2)

    if not _photo_library_visible(driver, timeout=5):
        raise AssertionError(
            "Photo library did not open after choosing phone album. "
            "Verify photo permissions and that the system picker is visible."
        )

    if _choose_local_photo(driver, album_name=draft.album):
        return

    if _choose_first_option(driver, preferred_texts=["最近项目", "照片图库", "照片", "所有照片"]) and _choose_local_photo(
        driver,
        album_name=draft.album,
    ):
        return
    raise AssertionError("Unable to upload an activity image from the local photo library")


def _choose_photo_library_source(driver: WebDriver) -> bool:
    from velowind_appium.modules.message_detail import _tap_photo_source_option

    source_texts = ["从手机相册选择", "手机相册", "从相册选择", "相册"]
    if _tap_photo_source_option(driver, source_texts):
        return True
    for text in source_texts:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    return _tap_activity_photo_library_sheet_option(driver)


def _choose_local_photo(driver: WebDriver, *, album_name: str | None = None) -> bool:
    from velowind_appium.modules.message_detail import _choose_local_photo as _choose_note_local_photo

    return bool(_choose_note_local_photo(driver, album_name=album_name))


def _photo_library_visible(driver: WebDriver, timeout: int = 5) -> bool:
    from velowind_appium.modules.message_detail import _photo_library_visible as _note_photo_library_visible

    return bool(_note_photo_library_visible(driver, timeout=timeout))


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
    candidate_values = [
        (SELECT_FIELD_KEYWORDS["contact"], draft.contact_name),
        (["手机号", "联系电话", "联系方式"], draft.contact_phone),
        (SELECT_FIELD_KEYWORDS["location"], draft.location),
        (["城市名称"], draft.city),
        (SELECT_FIELD_KEYWORDS["count"], draft.max_participants),
        (SELECT_FIELD_KEYWORDS["fee"], draft.fee),
    ]
    for keywords, value in candidate_values:
        for keyword in keywords:
            if _fill_input_near_label(driver, keyword, value):
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
) -> bool:
    element_types = ["XCUIElementTypeTextView", "XCUIElementTypeTextField"]
    if prefer_text_view:
        element_types = ["XCUIElementTypeTextView", "XCUIElementTypeTextField"]
    else:
        element_types = ["XCUIElementTypeTextField", "XCUIElementTypeTextView"]

    xpath_templates = [
        f'//*[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]/following::{{element_type}}[1]',
        f'//{{element_type}}[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]',
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
            except (NoSuchElementException, WebDriverException):
                continue
    return False


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
    try:
        placeholder_value = (element.get_attribute("placeholderValue") or "").strip()
    except WebDriverException:
        placeholder_value = ""
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
    except (NoSuchElementException, WebDriverException):
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
    _fill_indexed_editor_text_field(driver, "标题", item.title, index)
    _dismiss_editor_keyboard(driver)
    _fill_indexed_editor_text_field(driver, "副标题", item.subtitle, index)
    _dismiss_editor_keyboard(driver)
    _fill_indexed_editor_text_view(driver, item.body, index)
    _dismiss_editor_keyboard(driver)


def _fill_indexed_editor_text_field(driver: WebDriver, placeholder: str, value: str, index: int) -> None:
    field = _find_indexed_editor_text_field(driver, placeholder, index)
    _replace_text(field, value)


def _fill_indexed_editor_text_view(driver: WebDriver, value: str, index: int) -> None:
    field = _find_indexed_editor_text_view(driver, index)
    _replace_text(field, value)


def _find_indexed_editor_text_field(driver: WebDriver, placeholder: str, index: int):
    xpath = (
        f'//XCUIElementTypeTextField[@placeholderValue="{placeholder}" '
        f'or @value="{placeholder}" or @name="{placeholder}" or @label="{placeholder}"]'
    )
    return _find_indexed_visible_editor_element(driver, xpath, index, f"activity itinerary {placeholder}")


def _find_indexed_editor_text_view(driver: WebDriver, index: int):
    return _find_indexed_visible_editor_element(driver, "//XCUIElementTypeTextView", index, "activity itinerary body")


def _find_indexed_visible_editor_element(driver: WebDriver, xpath: str, index: int, field_name: str):
    for _ in range(5):
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except WebDriverException:
            elements = []
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
    try:
        buttons = driver.find_elements(AppiumBy.XPATH, '//XCUIElementTypeOther[@width="30" and @height="30"]')
    except WebDriverException:
        return None
    visible_buttons = sorted(
        [button for button in buttons if _element_is_visible(button)],
        key=lambda button: (button.rect.get("y", 0), button.rect.get("x", 0)),
    )
    return visible_buttons[-1] if visible_buttons else None


def _count_itinerary_editor_sections(page_source: str) -> int:
    if not page_source:
        return 0
    return len(
        re.findall(
            r'<XCUIElementTypeTextField[^>]*visible="true"[^>]*placeholderValue="标题"',
            page_source,
        )
    )


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


def _close_editor(driver: WebDriver) -> None:
    _dismiss_editor_keyboard(driver)
    _tap_editor_title(driver)
    time.sleep(0.2)
    if _tap_editor_bottom_done(driver):
        if _wait_until(lambda: not _editor_page_visible(_safe_page_source(driver)), timeout=4):
            return
    _dismiss_editor_keyboard(driver)
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
    try:
        driver.execute_script("mobile: tap", {"x": 60, "y": 206})
        return True
    except WebDriverException:
        return False


def _tap_form_field(driver: WebDriver, text: str, fallback_point: tuple[int, int] | None = None) -> bool:
    if tap_text_if_present(driver, text, timeout=2):
        return True
    xpath = f'//*[@name="{text}" or @label="{text}" or @value="{text}"]'
    try:
        _tap_element_center(driver, driver.find_element(AppiumBy.XPATH, xpath))
        return True
    except (NoSuchElementException, WebDriverException):
        pass

    if fallback_point is not None:
        try:
            driver.execute_script("mobile: tap", {"x": fallback_point[0], "y": fallback_point[1]})
            return True
        except WebDriverException:
            return False
    return False


def _tap_placeholder(driver: WebDriver, placeholder: str) -> bool:
    if tap_text_if_present(driver, placeholder, timeout=2):
        return True
    xpath = f'//*[@name="{placeholder}" or @label="{placeholder}" or @value="{placeholder}"]'
    try:
        _tap_element_center(driver, driver.find_element(AppiumBy.XPATH, xpath))
        return True
    except (NoSuchElementException, WebDriverException):
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
        if tap_text_if_present(driver, text, timeout=2):
            _confirm_overlay_selection(driver)
            return True

    for text in target_texts:
        for xpath in [
            f'//*[@name="{text}" or @label="{text}" or @value="{text}"]',
            f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
        ]:
            try:
                _tap_element_center(driver, driver.find_element(AppiumBy.XPATH, xpath))
                _confirm_overlay_selection(driver)
                return True
            except (NoSuchElementException, WebDriverException):
                continue

    for text in target_texts:
        if _set_first_picker_wheel_value(driver, text):
            _confirm_overlay_selection(driver)
            return True

    return False


def _set_first_picker_wheel_value(driver: WebDriver, text: str) -> bool:
    try:
        _first_picker_wheel(driver).send_keys(text)
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _confirm_overlay_selection(driver: WebDriver) -> None:
    for text in ["确定", "完成"]:
        if tap_text_if_present(driver, text, timeout=1):
            return


def _choose_first_option(driver: WebDriver, preferred_texts: list[str]) -> bool:
    for text in preferred_texts:
        if tap_text_if_present(driver, text, timeout=2):
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
        if tap_if_present(driver, accessibility_id, timeout=2):
            return True
    for text in ["提交审核", "提交", "发布"]:
        if tap_text_if_present(driver, text, timeout=2):
            return True
    return False


def _tap_plus_button_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        x = int(rect["width"] * 0.5)
        y = int(rect["height"] * 0.93)
        driver.execute_script("mobile: tap", {"x": x, "y": y})
        return True
    except WebDriverException:
        return False


def _wait_until(predicate, timeout: int) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def _extract_strings(page_source: str) -> list[str]:
    values = re.findall(r'(?:name|label|value)="([^"]+)"', page_source)
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = html.unescape(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""
