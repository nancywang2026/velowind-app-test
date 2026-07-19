from __future__ import annotations

import time

from appium.webdriver.webdriver import WebDriver

from velowind_appium.modules.rental_common import (
    tap_by_coordinate_ratios,
    tap_first_available,
    wait_for_rental_page,
)
from velowind_appium.modules.rental_order_confirm import wait_for_rental_order_confirm_page


DETAIL_PAGE_IDS = ["rental-vehicle-detail-page", "vehicle-detail-page", "rent-car-detail-page"]
DETAIL_PAGE_TEXTS = ["车辆基本信息", "基本信息", "车辆配置"]
BOOK_NOW_IDS = ["rental-book-now-button", "vehicle-book-now-button", "rent-car-book-now-button"]
BOOK_NOW_TEXTS = ["立即预定", "立即预订", "马上预订", "预订", "预定"]


def wait_for_vehicle_detail_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=DETAIL_PAGE_IDS,
        texts=DETAIL_PAGE_TEXTS,
        timeout=timeout,
    )


def assert_vehicle_basic_info_visible(driver: WebDriver, timeout: int = 20) -> None:
    wait_for_vehicle_detail_page(driver, timeout=timeout)


def tap_book_now(driver: WebDriver, timeout: int = 15) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if tap_first_available(driver, accessibility_ids=BOOK_NOW_IDS, texts=BOOK_NOW_TEXTS, timeout=2):
            wait_for_rental_order_confirm_page(driver, timeout=10)
            return
        if tap_by_coordinate_ratios(driver, [(0.83, 0.93), (0.82, 0.91), (0.83, 0.90)]):
            wait_for_rental_order_confirm_page(driver, timeout=10)
            return
        time.sleep(0.3)
    raise AssertionError("Unable to continue from vehicle detail to rental order confirmation")
