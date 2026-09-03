from dataclasses import dataclass
import html
import json
import re
import time
from typing import Optional
import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import safe_back, swipe_vertical, tap_text_if_present
from velowind_appium.cleanup_config import CleanupConfig, matches_test_data
from velowind_appium.modules.activity import _tap_element_center
from velowind_appium.modules.activity_sessions import open_my_activity_publish_list
from velowind_appium.session import ensure_logged_in_on_home


NOTE_ACTION_TEXTS = ["删除", "确认删除"]
ACTIVITY_ACTION_TEXTS = ["下架", "取消发布", "删除"]
SESSION_ACTION_TEXTS = ["删除", "取消", "下架"]
CONFIRM_TEXTS = ["确认删除", "确定", "确认", "删除", "下架", "取消发布"]


@dataclass(frozen=True)
class CleanupReport:
    item_type: str
    deleted: list[str]
    skipped: list[str]


def cleanup_notes(driver: WebDriver, config: CleanupConfig, app_config, *, dry_run: bool = False) -> CleanupReport:
    ensure_logged_in_on_home(driver, app_config)
    _open_me_entry(driver, "我的笔记")
    try:
        return cleanup_matching_visible_items(
            driver,
            item_type="note",
            matchers=config.note_matchers,
            action_texts=NOTE_ACTION_TEXTS,
            dry_run=dry_run,
        )
    finally:
        safe_back(driver)


def cleanup_published_note(driver: WebDriver, title: str, app_config) -> CleanupReport:
    ensure_logged_in_on_home(driver, app_config)
    _open_me_entry(driver, "我的笔记")
    try:
        return cleanup_exact_visible_item(
            driver,
            item_type="note",
            title=title,
            action_texts=NOTE_ACTION_TEXTS,
        )
    finally:
        safe_back(driver)


def cleanup_activities(driver: WebDriver, config: CleanupConfig, app_config, *, dry_run: bool = False) -> CleanupReport:
    ensure_logged_in_on_home(driver, app_config)
    open_my_activity_publish_list(driver)
    try:
        return cleanup_matching_visible_items(
            driver,
            item_type="activity",
            matchers=config.activity_matchers,
            action_texts=ACTIVITY_ACTION_TEXTS,
            dry_run=dry_run,
            required_page_texts=["通过", "上架"],
        )
    finally:
        safe_back(driver)


def cleanup_sessions(driver: WebDriver, config: CleanupConfig, app_config, *, dry_run: bool = False) -> CleanupReport:
    ensure_logged_in_on_home(driver, app_config)
    open_my_activity_publish_list(driver)
    try:
        if not tap_text_if_present(driver, "管理场次", timeout=2):
            return CleanupReport(item_type="session", deleted=[], skipped=[])
        return cleanup_matching_visible_items(
            driver,
            item_type="session",
            matchers=config.session_matchers,
            action_texts=SESSION_ACTION_TEXTS,
            dry_run=dry_run,
        )
    finally:
        safe_back(driver)


def cleanup_matching_visible_items(
    driver: WebDriver,
    *,
    item_type: str,
    matchers: list[str],
    action_texts: list[str],
    dry_run: bool,
    required_texts: Optional[list[str]] = None,
    required_page_texts: Optional[list[str]] = None,
    exact_match: bool = False,
    max_rounds: int = 20,
) -> CleanupReport:
    deleted: list[str] = []
    skipped: list[str] = []
    seen: set[str] = set()

    for _ in range(max_rounds):
        page_source = _safe_page_source(driver)
        page_has_required_texts = not required_page_texts or all(text in page_source for text in required_page_texts)
        candidates = [
            text for text in find_matching_visible_texts(page_source, matchers, required_texts=required_texts)
            if text not in seen
            and page_has_required_texts
            and (not exact_match or text in matchers)
        ]
        if candidates:
            for candidate in candidates:
                seen.add(candidate)
                if dry_run:
                    skipped.append(candidate)
                    continue
                if _delete_candidate(driver, candidate, action_texts):
                    deleted.append(candidate)
                    break
                skipped.append(candidate)
                safe_back(driver)
                break
            if not dry_run:
                continue
        if _cleanup_page_reached_end(page_source):
            break
        if not _scroll_page(driver):
            break
        next_page_source = _safe_page_source(driver)
        if next_page_source == page_source:
            break

    return CleanupReport(item_type=item_type, deleted=deleted, skipped=skipped)


def cleanup_exact_visible_item(
    driver: WebDriver,
    *,
    item_type: str,
    title: str,
    action_texts: list[str],
) -> CleanupReport:
    """Delete a just-created item only when its exact title is visible at the list top."""
    if not _tap_exact_visible_title(driver, title):
        return CleanupReport(item_type=item_type, deleted=[], skipped=[])
    time.sleep(0.5)
    if not tap_first_available_text(driver, ["更多", "...", "…"]):
        _tap_ios_top_right_more(driver)
    if not tap_first_available_text(driver, action_texts):
        return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
    if not confirm_destructive_action(driver):
        return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
    return CleanupReport(item_type=item_type, deleted=[title], skipped=[])


def _tap_exact_visible_title(driver: WebDriver, title: str) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    platform = str(capabilities.get("platformName", "")).lower()
    if platform == "android":
        quoted = json.dumps(title, ensure_ascii=False)
        locator = (AppiumBy.ANDROID_UIAUTOMATOR, f"new UiSelector().text({quoted})")
    else:
        escaped = title.replace("\\", "\\\\").replace('"', '\\"')
        locator = (
            AppiumBy.IOS_PREDICATE,
            f'name == "{escaped}" OR label == "{escaped}" OR value == "{escaped}"',
        )
    try:
        elements = driver.find_elements(*locator)
    except (AttributeError, NoSuchElementException, WebDriverException):
        return False
    for element in elements:
        if not _element_is_visible(element):
            continue
        return _tap_element_center(driver, element)
    return False


def _cleanup_page_reached_end(page_source: str) -> bool:
    return any(marker in page_source for marker in ["已经到底了", "没有更多了", "暂无更多"])


def find_matching_visible_texts(
    page_source: str,
    matchers: list[str],
    *,
    required_texts: Optional[list[str]] = None,
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for value in _visible_text_values(page_source):
        text = html.unescape(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        if text.startswith("#"):
            continue
        if required_texts and not all(required_text in text for required_text in required_texts):
            continue
        if matches_test_data(text, matchers):
            matched.append(text)
    return matched


def _visible_text_values(page_source: str) -> list[str]:
    try:
        root = ET.fromstring(page_source)
    except ET.ParseError:
        return re.findall(r'(?:text|name|label|value)="([^"]+)"', page_source)

    values: list[str] = []
    for element in root.iter():
        if not _is_text_candidate_element(element):
            continue
        for attribute in ("text", "name", "label", "value"):
            value = element.attrib.get(attribute)
            if value:
                values.append(value)
                break
    return values


def _is_text_candidate_element(element: ET.Element) -> bool:
    element_type = element.attrib.get("type", element.tag)
    if element_type.startswith("XCUIElementType") and element.attrib.get("visible") == "false":
        return False
    if element_type in {"XCUIElementTypeStaticText", "XCUIElementTypeButton"}:
        return True
    if element_type.endswith("TextView") or element_type.endswith("Button"):
        return True
    if element_type.startswith("XCUIElementType"):
        return False
    return len(list(element)) == 0


def _delete_candidate(driver: WebDriver, text: str, action_texts: list[str]) -> bool:
    if not tap_matching_item(driver, text):
        return False
    time.sleep(0.5)
    if not tap_first_available_text(driver, ["更多", "...", "…"]):
        _tap_ios_top_right_more(driver)
    if not tap_first_available_text(driver, action_texts):
        return False
    return confirm_destructive_action(driver)


def tap_matching_item(driver: WebDriver, text: str) -> bool:
    for xpath in _candidate_xpaths(text):
        try:
            for element in driver.find_elements(AppiumBy.XPATH, xpath):
                if not _element_is_visible(element):
                    continue
                _tap_element_center(driver, element)
                return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return tap_text_if_present(driver, text, timeout=1)


def tap_first_available_text(driver: WebDriver, texts: list[str]) -> bool:
    for text in texts:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    return False


def _element_is_visible(element) -> bool:
    try:
        return bool(element.is_displayed())
    except (WebDriverException, AttributeError):
        return True


def _tap_ios_top_right_more(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "ios":
        return False
    try:
        size = driver.get_window_size()
        driver.execute_script("mobile: tap", {"x": size["width"] - 36, "y": 92})
        return True
    except (WebDriverException, KeyError, TypeError):
        return False


def confirm_destructive_action(driver: WebDriver) -> bool:
    for text in CONFIRM_TEXTS:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    return True


def _open_me_entry(driver: WebDriver, text: str) -> None:
    if tap_text_if_present(driver, text, timeout=2):
        return
    tap_text_if_present(driver, "我的", timeout=3)
    if tap_text_if_present(driver, text, timeout=5):
        return
    raise AssertionError(f"Unable to open Me entry: {text}")


def _candidate_xpaths(text: str) -> list[str]:
    escaped = _xpath_literal(text)
    return [
        f'//*[contains(@text, {escaped})]/ancestor::android.view.ViewGroup[1]',
        f'//*[contains(@text, {escaped})]/ancestor::android.view.ViewGroup[2]',
        f'//*[contains(@name, {escaped}) or contains(@label, {escaped}) or contains(@value, {escaped})]/ancestor::*[1]',
        f'//*[contains(@text, {escaped}) or contains(@name, {escaped}) or contains(@label, {escaped}) or contains(@value, {escaped})]',
    ]


def _xpath_literal(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ', \'"\', '.join(f'"{part}"' for part in parts) + ")"


def _scroll_page(driver: WebDriver) -> bool:
    try:
        swipe_vertical(driver, direction="up")
        return True
    except (WebDriverException, AttributeError):
        return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""
