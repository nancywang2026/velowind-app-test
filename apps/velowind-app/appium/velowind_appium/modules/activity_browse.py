from __future__ import annotations

import time
from xml.etree import ElementTree

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, WebDriverException

from velowind_appium.actions import tap_accessibility_id_or_text_if_present, tap_text_if_present


ACTIVITY_READY_IDS = ["activity-discovery-v2-page"]
ACTIVITY_READY_TEXTS = ["全部活动", "活动", "总里程", "难度等级"]
ACTIVITY_CATEGORY_TEXTS = ["全部活动", "骑行", "徒步", "滑雪", "登山", "空中运动", "水上运动", "跑步"]
ACTIVITY_CARD_MARKERS = ["总里程", "时长", "场次", "难度等级"]


def open_activity_tab(driver: WebDriver, timeout: int = 20) -> None:
    if not tap_accessibility_id_or_text_if_present(driver, "bottom-nav-activity", "活动", timeout=5):
        raise AssertionError("Unable to tap the bottom activity tab")
    wait_for_activity_feed(driver, timeout=timeout)


def wait_for_activity_feed(driver: WebDriver, timeout: int = 20) -> str:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _activity_ready_id_present(driver):
            return "activity-feed-id"
        if page_source and _activity_ready_text_present(page_source):
            return "activity-feed-text"
        time.sleep(0.2)
    raise TimeoutException("Activity feed did not become ready")


def switch_activity_category_navigation(driver: WebDriver, timeout: int = 10) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if "全部活动" in page_source and any(text in page_source for text in ACTIVITY_CATEGORY_TEXTS):
            return
        time.sleep(0.2)
    raise AssertionError("Unable to find the activity category navigation")


def select_activity_category(driver: WebDriver, category_name: str, timeout: int = 10) -> None:
    if not _tap_activity_category(driver, category_name):
        raise AssertionError(f"Unable to tap activity category: {category_name}")
    if not wait_for_activity_category_results(driver, category_name, timeout=timeout):
        raise AssertionError(f"Activity feed did not show {category_name} related activities")


def wait_for_activity_category_results(driver: WebDriver, category_name: str, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if activity_feed_contains_category_results(_safe_page_source(driver), category_name):
            return True
        time.sleep(0.2)
    return False


def activity_feed_contains_category_results(page_source: str, category_name: str) -> bool:
    return bool(activity_feed_category_result_texts(page_source, category_name))


def activity_feed_category_result_texts(page_source: str, category_name: str) -> list[str]:
    tag_texts = extract_visible_activity_category_tag_texts(page_source)
    source_texts = tag_texts or extract_visible_activity_card_texts(page_source)
    return [text for text in source_texts if _activity_card_matches_category(text, category_name)]


def activity_feed_all_results_match_category(page_source: str, category_name: str) -> tuple[bool, list[str]]:
    tag_texts = extract_visible_activity_category_tag_texts(page_source)
    source_texts = tag_texts or extract_visible_activity_card_texts(page_source)
    mismatched = [text for text in source_texts if not _activity_card_matches_category(text, category_name)]
    return bool(source_texts) and not mismatched, mismatched


def extract_visible_activity_category_tag_texts(page_source: str) -> list[str]:
    return [
        text
        for text in extract_visible_activity_card_texts(page_source)
        if _looks_like_activity_category_tag_text(text)
    ]


def extract_visible_activity_card_texts(page_source: str) -> list[str]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return _extract_activity_card_texts_from_plain_source(page_source)

    texts: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if element.attrib.get("visible") == "false":
            continue
        text = (
            element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
        ).strip()
        if not _looks_like_activity_card_text(text):
            continue
        normalized = " ".join(text.split())
        if normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    return texts


def _extract_activity_card_texts_from_plain_source(page_source: str) -> list[str]:
    return [
        line.strip()
        for line in page_source.splitlines()
        if _looks_like_activity_card_text(line)
    ]


def _looks_like_activity_card_text(text: str) -> bool:
    if not text:
        return False
    if text.startswith("总里程"):
        return False
    if any(nav_text == text for nav_text in ACTIVITY_CATEGORY_TEXTS):
        return False
    if not all(marker in text for marker in ACTIVITY_CARD_MARKERS):
        return False
    return text.count("总里程") == 1


def _looks_like_activity_category_tag_text(text: str) -> bool:
    return any(text.startswith(category) for category in ACTIVITY_CATEGORY_TEXTS if category != "全部活动")


def _activity_card_matches_category(text: str, category_name: str) -> bool:
    if _looks_like_activity_category_tag_text(text):
        return text.startswith(category_name)
    return category_name in text


def _tap_activity_category(driver: WebDriver, category_name: str) -> bool:
    if tap_text_if_present(driver, category_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "right"})
    except WebDriverException:
        pass
    if tap_text_if_present(driver, category_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "left"})
    except WebDriverException:
        pass
    return tap_text_if_present(driver, category_name, timeout=1)


def _activity_ready_id_present(driver: WebDriver) -> bool:
    for accessibility_id in ACTIVITY_READY_IDS:
        try:
            driver.find_element("accessibility id", accessibility_id)
            return True
        except Exception:
            continue
    return False


def _activity_ready_text_present(page_source: str) -> bool:
    return any(text in page_source for text in ACTIVITY_READY_TEXTS) and "首页" in page_source


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""
