from __future__ import annotations

import re
import time
from xml.etree import ElementTree

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from velowind_appium.actions import (
    tap_if_present,
    tap_text_if_present,
    wait_for_any_accessibility_id_or_text,
)


OPTIONAL_TAP_TIMEOUT_SECONDS = 0.8


def wait_for_rental_page(
    driver: WebDriver,
    *,
    accessibility_ids: list[str],
    texts: list[str],
    timeout: int = 20,
) -> str | None:
    return wait_for_any_accessibility_id_or_text(driver, accessibility_ids, texts, timeout=timeout)


def tap_first_available(driver: WebDriver, *, accessibility_ids: list[str], texts: list[str], timeout: int = 2) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        for accessibility_id in accessibility_ids:
            if tap_if_present(driver, accessibility_id, timeout=OPTIONAL_TAP_TIMEOUT_SECONDS):
                return True
        for text in texts:
            if tap_text_if_present(driver, text, timeout=OPTIONAL_TAP_TIMEOUT_SECONDS):
                return True
        time.sleep(0.2)
    return False


def tap_by_text_containing(driver: WebDriver, keywords: list[str], timeout: int = 2) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        source = safe_page_source(driver)
        for text in extract_visible_texts(source):
            if any(keyword in text for keyword in keywords):
                if tap_text_if_present(driver, text, timeout=OPTIONAL_TAP_TIMEOUT_SECONDS):
                    return True
        time.sleep(0.2)
    return False


def tap_by_coordinate_ratios(driver: WebDriver, ratios: list[tuple[float, float]]) -> bool:
    try:
        rect = driver.get_window_rect()
    except WebDriverException:
        return False

    for x_ratio, y_ratio in ratios:
        try:
            driver.execute_script(
                "mobile: tap",
                {"x": int(rect["width"] * x_ratio), "y": int(rect["height"] * y_ratio)},
            )
            time.sleep(0.4)
            return True
        except WebDriverException:
            continue
    return False


def swipe_horizontal(driver: WebDriver, direction: str = "left") -> None:
    if direction not in {"left", "right"}:
        raise ValueError(f"Unsupported horizontal swipe direction: {direction}")

    try:
        rect = driver.get_window_rect()
        y = int(rect["height"] * 0.56)
        if direction == "left":
            start_x, end_x = int(rect["width"] * 0.66), int(rect["width"] * 0.34)
        else:
            start_x, end_x = int(rect["width"] * 0.34), int(rect["width"] * 0.66)
        driver.swipe(start_x, y, end_x, y, 450)
        return
    except WebDriverException:
        pass

    try:
        driver.execute_script("mobile: swipe", {"direction": direction})
        return
    except WebDriverException:
        pass

    return


def tap_first_visible_container(driver: WebDriver, *, y_min_ratio: float = 0.18, y_max_ratio: float = 0.78) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.50),
                "y": int(rect["height"] * ((y_min_ratio + y_max_ratio) / 2)),
            },
        )
        time.sleep(0.4)
        return True
    except WebDriverException:
        return False


def safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""


def source_contains_any(page_source: str, texts: list[str]) -> bool:
    return any(text in page_source for text in texts)


def wait_until_source_contains(driver: WebDriver, texts: list[str], timeout: int = 15) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if source_contains_any(safe_page_source(driver), texts):
            return True
        time.sleep(0.2)
    return False


def extract_visible_texts(page_source: str) -> list[str]:
    if not page_source:
        return []
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return _extract_texts_from_plain_source(page_source)

    texts: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        raw_text = (
            element.attrib.get("text", "")
            or element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
            or element.attrib.get("content-desc", "")
        )
        normalized = normalize_text(raw_text)
        if not normalized or normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    return texts


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_texts_from_plain_source(page_source: str) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for line in page_source.splitlines():
        normalized = normalize_text(line)
        if not normalized or normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    return texts


def find_elements_by_text_keywords(driver: WebDriver, keywords: list[str]):
    matches = []
    for keyword in keywords:
        try:
            matches.extend(driver.find_elements(AppiumBy.XPATH, f'//*[contains(@text, "{keyword}") or contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@content-desc, "{keyword}")]'))
        except (NoSuchElementException, WebDriverException):
            continue
    return matches
