from __future__ import annotations

from xml.etree import ElementTree
import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from velowind_appium.actions import (
    swipe_vertical,
    tap_text_if_present,
)
from velowind_appium.modules.message_detail import message_detail_is_visible
from velowind_appium.modules.note_card_picker import tap_first_note_card


HOME_READY_IDS = [
    "home-page-title",
    "home-activity-discovery-browser",
    "post-home-feed-category-pager",
]
HOME_READY_TEXTS = ["首页", "全国", "推荐"]
NOTE_TYPE_NAV_TEXTS = ["全国", "推荐", "骑行", "徒步", "登山", "跑步"]
NOTE_TYPE_RELATED_KEYWORDS = {
    "徒步": ["徒步", "散步", "步道", "爬山", "登山", "山间", "路线", "户外"],
}
HOME_BLOCKING_TEXTS = [
    "发布活动",
    "提交审核",
    "存草稿",
    "活动图片",
    "写留言",
    "手机号登录",
    "请输入手机号",
    "密码登录",
    "验证并登录",
    "post-detail-banner-pager",
    "post-detail-page",
    "message-detail-page",
    "article-detail-page",
]
def wait_for_home_feed(driver: WebDriver, timeout: int = 60) -> str | None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if page_source and any(text in page_source for text in HOME_BLOCKING_TEXTS):
            time.sleep(0.2)
            continue
        if _home_ready_id_present(driver):
            return "home-feed-id"
        if page_source and _home_ready_text_present(page_source):
            return "home-feed-text"
        time.sleep(0.2)
    raise TimeoutException("Home feed did not become ready")


def open_first_home_message(driver: WebDriver, max_swipes: int = 3) -> None:
    wait_for_home_feed(driver, timeout=60)
    if message_detail_is_visible(driver):
        return

    for _ in range(max_swipes + 1):
        if message_detail_is_visible(driver):
            return
        if _tap_first_message(driver):
            for _ in range(20):
                if message_detail_is_visible(driver):
                    return
                time.sleep(0.2)
        if message_detail_is_visible(driver):
            return
        if not _tap_first_visible_card(driver):
            swipe_vertical(driver, direction="up")

    if message_detail_is_visible(driver):
        return
    raise AssertionError("Unable to detect the first message detail after entering from the home feed")


def browse_note_feed(driver: WebDriver, timeout: int = 30) -> None:
    wait_for_home_feed(driver, timeout=timeout)


def switch_note_type_navigation(driver: WebDriver, timeout: int = 10) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if all(text in page_source for text in ["首页", "全国"]) and any(
            text in page_source for text in NOTE_TYPE_NAV_TEXTS
        ):
            return
        time.sleep(0.2)
    raise AssertionError("Unable to find the note type navigation on the home feed")


def select_note_type(driver: WebDriver, type_name: str, timeout: int = 10) -> None:
    if not _tap_note_type(driver, type_name):
        raise AssertionError(f"Unable to tap note type: {type_name}")
    if not wait_for_note_type_results(driver, type_name, timeout=timeout):
        raise AssertionError(f"Note feed did not show {type_name} related notes")


def wait_for_note_type_results(driver: WebDriver, type_name: str, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if note_feed_contains_type_results(_safe_page_source(driver), type_name):
            return True
        time.sleep(0.2)
    return False


def note_feed_contains_type_results(page_source: str, type_name: str) -> bool:
    return bool(note_feed_type_result_texts(page_source, type_name))


def note_feed_type_result_texts(page_source: str, type_name: str) -> list[str]:
    card_texts = _extract_visible_note_card_texts(page_source)
    return [text for text in card_texts if _note_card_matches_type(text, type_name)]


def note_feed_all_results_match_type(page_source: str, type_name: str) -> tuple[bool, list[str]]:
    card_texts = _extract_visible_note_card_texts(page_source)
    mismatched = [text for text in card_texts if not _note_card_matches_type(text, type_name)]
    return bool(card_texts) and not mismatched, mismatched


def _tap_first_message(driver: WebDriver) -> bool:
    return tap_first_note_card(driver, verify_open=message_detail_is_visible)


def _tap_first_visible_card(driver: WebDriver) -> bool:
    return tap_first_note_card(driver, verify_open=message_detail_is_visible)


def _tap_note_type(driver: WebDriver, type_name: str) -> bool:
    if tap_text_if_present(driver, type_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "right"})
    except WebDriverException:
        pass
    if tap_text_if_present(driver, type_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "left"})
    except WebDriverException:
        pass
    return tap_text_if_present(driver, type_name, timeout=1)


def _extract_visible_note_card_texts(page_source: str) -> list[str]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return _extract_note_card_texts_from_plain_source(page_source)

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
        if not _looks_like_note_card_text(text):
            continue
        normalized = " ".join(text.split())
        if normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    return texts


def _extract_note_card_texts_from_plain_source(page_source: str) -> list[str]:
    return [
        line.strip()
        for line in page_source.splitlines()
        if _looks_like_note_card_text(line)
    ]


def _looks_like_note_card_text(text: str) -> bool:
    if not text:
        return False
    if any(nav_text == text for nav_text in NOTE_TYPE_NAV_TEXTS):
        return False
    if text.startswith("用户"):
        return False
    if text.count("用户") != 1:
        return False
    return "用户" in text and ("赞" in text or "浏览" in text)


def _note_card_matches_type(text: str, type_name: str) -> bool:
    related_keywords = NOTE_TYPE_RELATED_KEYWORDS.get(type_name, [type_name])
    return any(keyword in text for keyword in related_keywords)


def _home_ready_id_present(driver: WebDriver) -> bool:
    for accessibility_id in HOME_READY_IDS:
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id)
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _home_ready_text_present(page_source: str) -> bool:
    if any(text in page_source for text in HOME_BLOCKING_TEXTS):
        return False
    return "首页" in page_source and ("全国" in page_source or "推荐" in page_source)


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""
