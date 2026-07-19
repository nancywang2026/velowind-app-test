from __future__ import annotations

import time

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException

from velowind_appium.actions import safe_back, tap_accessibility_id_or_text_if_present
from velowind_appium.modules.home_feed import wait_for_home_feed
from velowind_appium.modules.rental_common import (
    safe_page_source,
    source_contains_any,
    tap_by_coordinate_ratios,
    tap_by_text_containing,
    tap_first_available,
)
from velowind_appium.modules.rental_store import wait_for_rental_store_page


RENTAL_ENTRY_IDS = [
    "home-rental-entry",
    "home-rent-car-entry",
    "rental-entry",
    "rent-car-entry",
    "floating-rental-entry",
    "floating-truck-entry",
    "floating-rental-mode-entry-car",
    "floating-rental-mode-entry-car-icon",
    "truck",
    "truck-icon",
]
RENTAL_ENTRY_TEXTS = ["租车", "车辆租赁", "租车服务"]
FLOATING_TRUCK_RATIOS = [
    (0.65, 0.84),
    (0.70, 0.84),
    (0.90, 0.72),
    (0.90, 0.78),
    (0.88, 0.66),
    (0.92, 0.62),
]


def open_rental_from_home(driver: WebDriver, timeout: int = 20) -> None:
    _recover_home_before_opening_rental(driver)
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if _rental_store_visible(driver):
            return
        if tap_first_available(driver, accessibility_ids=RENTAL_ENTRY_IDS, texts=RENTAL_ENTRY_TEXTS, timeout=2):
            if _wait_for_store_after_tap(driver):
                return
        if tap_by_text_containing(driver, ["租车", "车辆租赁"], timeout=1):
            if _wait_for_store_after_tap(driver):
                return
        if tap_by_coordinate_ratios(driver, FLOATING_TRUCK_RATIOS):
            if _wait_for_store_after_tap(driver):
                return
        time.sleep(0.4)
    raise AssertionError("Unable to open the rental page from the home floating truck entry")


def _recover_home_before_opening_rental(driver: WebDriver) -> None:
    for _ in range(4):
        if _home_visible(driver):
            return
        if tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=1):
            if _wait_for_home_after_recovery(driver):
                return
        if tap_by_coordinate_ratios(driver, [(0.05, 0.09), (0.06, 0.07)]):
            if _wait_for_home_after_recovery(driver):
                return
        safe_back(driver)
        if _wait_for_home_after_recovery(driver):
            return


def _wait_for_home_after_recovery(driver: WebDriver) -> bool:
    try:
        wait_for_home_feed(driver, timeout=5)
        return True
    except Exception:
        return _home_visible(driver)


def _wait_for_store_after_tap(driver: WebDriver) -> bool:
    try:
        wait_for_rental_store_page(driver, timeout=8)
        return True
    except TimeoutException:
        return False


def _rental_store_visible(driver: WebDriver) -> bool:
    source = safe_page_source(driver)
    return source_contains_any(source, ["服务门店", "立即选车", "租车门店", "选择门店"])


def _home_visible(driver: WebDriver) -> bool:
    source = safe_page_source(driver)
    return (
        ("首页" in source and ("全国" in source or "推荐" in source))
        or "post-home-feed-category-pager" in source
        or all(text in source for text in ["首页", "活动", "消息", "我的"])
    )
