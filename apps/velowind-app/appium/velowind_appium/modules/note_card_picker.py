from __future__ import annotations

import html
import re
import time
from typing import Callable

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException


NOTE_CARD_IDS = [
    "post-home-feed-item-0",
    "post-home-feed-card-0",
    "home-feed-item-0",
    "search-result-note-0",
    "note-search-result-0",
    "post-search-result-0",
]
NOTE_CARD_XPATHS = [
    "(//XCUIElementTypeCollectionView//XCUIElementTypeCell)[1]",
    "(//XCUIElementTypeCollectionView//XCUIElementTypeButton)[1]",
    "(//XCUIElementTypeTable//XCUIElementTypeCell)[1]",
    "(//XCUIElementTypeTable//XCUIElementTypeButton)[1]",
]
GENERIC_NOTE_CARD_TEXTS = {
    "首页",
    "推荐",
    "全国",
    "关注",
    "赞",
    "用户",
    "评论",
    "浏览",
}


def tap_first_note_card(
    driver: WebDriver,
    *,
    page_source: str | None = None,
    verify_open: Callable[[], bool] | None = None,
    timeout: float = 1.2,
) -> bool:
    if _tap_by_accessibility_id(driver) and _opened(verify_open, timeout):
        return True
    if _tap_by_collection_xpath(driver) and _opened(verify_open, timeout):
        return True
    if _tap_by_page_source_rect(driver, page_source=page_source, verify_open=verify_open, timeout=timeout):
        return True
    if _tap_home_browse_coordinate(driver) and _opened(verify_open, timeout):
        return True
    return verify_open is None


def _tap_by_accessibility_id(driver: WebDriver) -> bool:
    for accessibility_id in NOTE_CARD_IDS:
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_by_collection_xpath(driver: WebDriver) -> bool:
    for xpath in NOTE_CARD_XPATHS:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, TimeoutException, WebDriverException):
            continue
    return False


def _tap_by_page_source_rect(
    driver: WebDriver,
    *,
    page_source: str | None,
    verify_open: Callable[[], bool] | None,
    timeout: float,
) -> bool:
    source = page_source or _safe_page_source(driver)
    if not source:
        return False

    points = _candidate_tap_points(source)
    for x, y in _dedupe_points(points):
        if not _tap_point(driver, x, y):
            continue
        if _opened(verify_open, timeout):
            return True
    return False


def _candidate_tap_points(page_source: str) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    card_rect = _first_note_card_rect_from_source(page_source)
    title_rect = _first_note_title_rect_from_source(page_source)
    if card_rect is not None:
        x, y, width, height = card_rect
        points.extend(
            [
                (x + max(1, width // 2), y + int(height * 0.62)),
                (x + max(1, width // 2), y + min(120, max(24, height // 3))),
                (x + max(1, width // 2), min(y + height - 28, y + 300)),
            ]
        )
    if title_rect is not None:
        x, y, width, height = title_rect
        points.extend(
            [
                (x + max(1, width // 2), y + max(1, height // 2)),
                (x + max(1, width // 2), max(130, y - min(90, max(20, y - 130)))),
            ]
        )
    return points


def _first_note_card_rect_from_source(page_source: str) -> tuple[int, int, int, int] | None:
    rects: list[tuple[int, int, int, int]] = []
    for tag in re.findall(r"<XCUIElementTypeOther\b[^>]*>", page_source):
        attrs = _xml_tag_attrs(tag)
        text = attrs.get("name") or attrs.get("label") or attrs.get("value") or ""
        rect = _rect_from_attrs(attrs)
        if rect is None:
            continue
        x, y, width, height = rect
        if _looks_like_note_card(text, x, y, width, height):
            rects.append(rect)
    return sorted(rects, key=lambda item: (item[0], item[1]))[0] if rects else None


def _first_note_title_rect_from_source(page_source: str) -> tuple[int, int, int, int] | None:
    rects: list[tuple[int, int, int, int]] = []
    for tag in re.findall(r"<XCUIElementTypeStaticText\b[^>]*>", page_source):
        attrs = _xml_tag_attrs(tag)
        text = attrs.get("name") or attrs.get("label") or attrs.get("value") or ""
        rect = _rect_from_attrs(attrs)
        if rect is None:
            continue
        x, y, width, height = rect
        if _looks_like_note_title(text, x, y, width, height):
            rects.append(rect)
    return sorted(rects, key=lambda item: (item[0], item[1]))[0] if rects else None


def _looks_like_note_card(text: str, x: int, y: int, width: int, height: int) -> bool:
    if y < 120 or width < 150 or width > 220 or height < 70:
        return False
    if not text or "用户" not in text:
        return False
    if "赞" not in text and not re.search(r"\s\d+\s*$", text):
        return False
    if "首页 活动 消息 我的" in text or "Vertical scroll bar" in text:
        return False
    if text.startswith("用户 "):
        return False
    return 0 <= x <= 430


def _looks_like_note_title(text: str, x: int, y: int, width: int, height: int) -> bool:
    if y < 120 or width < 80 or height < 12:
        return False
    if not text or len(text) < 6:
        return False
    if text in GENERIC_NOTE_CARD_TEXTS:
        return False
    if text.startswith("#") or text.startswith("用户"):
        return False
    if re.fullmatch(r"[0-9a-f]{16,}", text):
        return False
    if any(token in text for token in ["Vertical scroll bar", "首页 活动 消息 我的"]):
        return False
    return 0 <= x <= 430


def _tap_home_browse_coordinate(driver: WebDriver) -> bool:
    try:
        size = driver.get_window_size()
        return _tap_point(driver, int(size["width"] * 0.25), int(size["height"] * 0.38))
    except (KeyError, TypeError, WebDriverException):
        return False


def _tap_point(driver: WebDriver, x: int, y: int) -> bool:
    try:
        driver.execute_script("mobile: tap", {"x": x, "y": y})
        return True
    except WebDriverException:
        return False


def _opened(verify_open: Callable[[], bool] | None, timeout: float) -> bool:
    if verify_open is None:
        return True
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if verify_open():
            return True
        time.sleep(0.2)
    return False


def _xml_tag_attrs(tag: str) -> dict[str, str]:
    return {key: html.unescape(value) for key, value in re.findall(r'(\w+)="([^"]*)"', tag)}


def _rect_from_attrs(attrs: dict[str, str]) -> tuple[int, int, int, int] | None:
    try:
        return (
            int(float(attrs.get("x", "0"))),
            int(float(attrs.get("y", "0"))),
            int(float(attrs.get("width", "0"))),
            int(float(attrs.get("height", "0"))),
        )
    except ValueError:
        return None


def _dedupe_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    deduped: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for point in points:
        if point in seen:
            continue
        seen.add(point)
        deduped.append(point)
    return deduped


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""
