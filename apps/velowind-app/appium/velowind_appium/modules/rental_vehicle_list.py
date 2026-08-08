from __future__ import annotations

import time
from xml.etree import ElementTree

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, WebDriverException

from velowind_appium.actions import safe_back
from velowind_appium.modules.rental_common import (
    safe_page_source,
    source_contains_any,
    swipe_horizontal,
    tap_by_coordinate_ratios,
    tap_by_text_containing,
    tap_first_available,
    tap_visible_text_hit_point,
    wait_for_rental_page,
)
from velowind_appium.modules.rental_vehicle_detail import wait_for_vehicle_detail_page


VEHICLE_LIST_IDS = ["rental-vehicle-list-page", "rent-car-list-page", "select-vehicle-page"]
VEHICLE_LIST_TEXTS = ["选择车辆", "选择车型", "车辆列表", "车辆详情"]
VEHICLE_DETAIL_IDS = ["rental-vehicle-detail-button", "vehicle-detail-button", "car-detail-button"]
VEHICLE_DETAIL_TEXTS = ["车辆详情", "查看详情", "详情"]
BOOKABLE_VEHICLE_TEXTS = ["可预定", "立即预定", "立即预订", "马上预订", "预订", "预定"]


def wait_for_rental_vehicle_list_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=VEHICLE_LIST_IDS,
        texts=VEHICLE_LIST_TEXTS,
        timeout=timeout,
    )


def swipe_to_choose_vehicle(driver: WebDriver, swipes: int = 1) -> None:
    wait_for_rental_vehicle_list_page(driver, timeout=20)
    for _ in range(max(swipes, 0)):
        swipe_horizontal(driver, direction="left")
        time.sleep(0.4)


def open_selected_vehicle_detail(driver: WebDriver, timeout: int = 20) -> None:
    wait_for_rental_vehicle_list_page(driver, timeout=timeout)
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if _vehicle_detail_visible(driver):
            return
        if tap_by_coordinate_ratios(driver, [(0.32, 0.75), (0.30, 0.79)]):
            try:
                wait_for_vehicle_detail_page(driver, timeout=8)
                return
            except TimeoutException:
                pass
        if tap_first_available(driver, accessibility_ids=VEHICLE_DETAIL_IDS, texts=VEHICLE_DETAIL_TEXTS, timeout=2):
            try:
                wait_for_vehicle_detail_page(driver, timeout=8)
                return
            except TimeoutException:
                pass
        if tap_by_text_containing(driver, ["车辆详情", "查看详情"], timeout=1):
            try:
                wait_for_vehicle_detail_page(driver, timeout=8)
                return
            except TimeoutException:
                pass
        if tap_visible_text_hit_point(driver, VEHICLE_DETAIL_TEXTS, timeout=1):
            try:
                wait_for_vehicle_detail_page(driver, timeout=8)
                return
            except TimeoutException:
                pass
        if tap_by_coordinate_ratios(driver, [(0.50, 0.62), (0.50, 0.70)]):
            if _vehicle_detail_visible(driver):
                return
        time.sleep(0.3)
    raise AssertionError("Unable to open selected vehicle detail")


def open_available_vehicle_detail(driver: WebDriver, max_attempts: int = 4, timeout: int = 20) -> None:
    wait_for_rental_vehicle_list_page(driver, timeout=timeout)
    if _tap_bookable_vehicle_detail_from_list(driver):
        return
    directions = ["right", "left", "left", "right"]
    for attempt in range(max_attempts):
        open_selected_vehicle_detail(driver, timeout=timeout)
        source = safe_page_source(driver)
        if _visible_vehicle_detail_bookable(source):
            return
        safe_back(driver)
        wait_for_rental_vehicle_list_page(driver, timeout=timeout)
        swipe_horizontal(driver, direction=directions[attempt % len(directions)])
        time.sleep(0.4)
        if _tap_bookable_vehicle_detail_from_list(driver):
            return
    raise AssertionError("Unable to find an available rental vehicle after swiping through vehicles")


def _tap_bookable_vehicle_detail_from_list(driver: WebDriver) -> bool:
    for x, y in _bookable_vehicle_detail_hit_points(safe_page_source(driver)):
        try:
            driver.execute_script("mobile: tap", {"x": x, "y": y})
            wait_for_vehicle_detail_page(driver, timeout=8)
            return True
        except (TimeoutException, WebDriverException):
            continue
    return False


def _bookable_vehicle_detail_hit_points(page_source: str) -> list[tuple[int, int]]:
    if not page_source or "车辆详情" not in page_source or not source_contains_any(page_source, BOOKABLE_VEHICLE_TEXTS):
        return []
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return []

    hit_points: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for element in root.iter():
        attrs = element.attrib
        if attrs.get("visible") == "false" or attrs.get("displayed") == "false":
            continue
        row_text = " ".join(_visible_node_text(descendant) for descendant in element.iter())
        if "车辆详情" not in row_text or "不可预定" in row_text:
            continue
        if not source_contains_any(row_text, BOOKABLE_VEHICLE_TEXTS):
            continue
        point = _detail_button_center(element)
        if point is None or point in seen:
            continue
        hit_points.append(point)
        seen.add(point)
    return hit_points


def _visible_node_text(element: ElementTree.Element) -> str:
    if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
        return ""
    return (
        element.attrib.get("text", "")
        or element.attrib.get("name", "")
        or element.attrib.get("label", "")
        or element.attrib.get("value", "")
    ).strip()


def _detail_button_center(element: ElementTree.Element) -> tuple[int, int] | None:
    detail_candidates: list[tuple[int, int, int]] = []
    row_fallback: tuple[int, int, int] | None = None
    for descendant in element.iter():
        hit_point = _element_hit_point(descendant.attrib)
        if hit_point is None:
            continue
        text = _visible_node_text(descendant)
        if text == "车辆详情":
            detail_candidates.append(hit_point)
        elif row_fallback is None and "车辆详情" in text:
            row_fallback = hit_point
    candidates = detail_candidates or ([row_fallback] if row_fallback else [])
    if not candidates:
        return None
    _, x, y = min(candidates)
    return x, y


def _element_hit_point(attrs: dict[str, str]) -> tuple[int, int, int] | None:
    try:
        x = int(float(attrs.get("x", "")))
        y = int(float(attrs.get("y", "")))
        width = int(float(attrs.get("width", "")))
        height = int(float(attrs.get("height", "")))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width * height, x + width // 2, y + height // 2


def _vehicle_detail_visible(driver: WebDriver) -> bool:
    source = safe_page_source(driver)
    return source_contains_any(source, ["车辆基本信息", "基本信息", "车辆配置"])


def _visible_vehicle_detail_bookable(page_source: str) -> bool:
    if not page_source:
        return False
    if "XCUIElementType" not in page_source:
        return "不可预定" not in page_source
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return "不可预定" not in page_source

    visible_values: list[str] = []
    for element in root.iter():
        attrs = element.attrib
        if attrs.get("visible") == "false":
            continue
        value = attrs.get("value") or attrs.get("label") or attrs.get("name") or ""
        if value and _looks_like_ios_readable_node(attrs, value):
            visible_values.append(value)

    visible_text = " ".join(visible_values)
    if not source_contains_any(visible_text, ["车辆详情", "基本信息", "车辆配置"]):
        return False
    if source_contains_any(visible_text, ["不可预定"]):
        return False
    return source_contains_any(visible_text, ["立即预定", "立即预订", "马上预订", "预订", "预定"])


def _looks_like_ios_readable_node(attrs: dict[str, str], value: str) -> bool:
    node_type = attrs.get("type", "")
    if node_type == "XCUIElementTypeStaticText":
        return True

    try:
        x = int(float(attrs.get("x", "")))
        y = int(float(attrs.get("y", "")))
        width = int(float(attrs.get("width", "")))
        height = int(float(attrs.get("height", "")))
    except ValueError:
        return len(value) <= 160
    return not (x == 0 and y == 0 and width >= 360 and height >= 700 and len(value) > 40)
