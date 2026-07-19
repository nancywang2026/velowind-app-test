from __future__ import annotations

import time

from appium.webdriver.webdriver import WebDriver

from velowind_appium.modules.rental_common import (
    safe_page_source,
    source_contains_any,
    tap_by_coordinate_ratios,
    tap_by_text_containing,
    tap_first_available,
    wait_for_rental_page,
)
from velowind_appium.modules.rental_vehicle_list import wait_for_rental_vehicle_list_page


STORE_PAGE_IDS = ["rental-store-page", "rent-car-store-page", "rental-service-store-page"]
STORE_PAGE_TEXTS = ["服务门店", "租车门店", "选择门店", "立即选车"]
FIRST_STORE_IDS = ["rental-store-card-0", "rental-store-item-0", "service-store-item-0"]
FIRST_STORE_TEXTS = ["第一个门店", "虹桥店"]
SELECT_CAR_IDS = ["rental-select-car-button", "rent-car-now-button", "select-vehicle-button"]
SELECT_CAR_TEXTS = ["立即选车", "选车", "去选车"]


def wait_for_rental_store_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=STORE_PAGE_IDS,
        texts=STORE_PAGE_TEXTS,
        timeout=timeout,
    )


def choose_first_store(driver: WebDriver, timeout: int = 15) -> None:
    wait_for_rental_store_page(driver, timeout=timeout)
    if _store_selected(driver):
        return

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if "选择服务城市" in safe_page_source(driver):
            tap_by_coordinate_ratios(driver, [(0.88, 0.37), (0.90, 0.38)])
            time.sleep(0.3)
            continue
        if tap_first_available(driver, accessibility_ids=FIRST_STORE_IDS, texts=FIRST_STORE_TEXTS, timeout=1):
            if _wait_for_store_selected(driver):
                return
        if tap_by_coordinate_ratios(driver, [(0.68, 0.59), (0.72, 0.59), (0.90, 0.59)]):
            time.sleep(0.5)
            if tap_by_text_containing(driver, ["门店", "服务车"], timeout=1):
                if _wait_for_store_selected(driver):
                    return
            if tap_by_coordinate_ratios(driver, [(0.68, 0.66), (0.50, 0.70), (0.68, 0.74)]):
                if _wait_for_store_selected(driver):
                    return
        time.sleep(0.3)
    raise AssertionError("Unable to select the first rental service store")


def tap_select_car_now(driver: WebDriver, timeout: int = 15) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if tap_first_available(driver, accessibility_ids=SELECT_CAR_IDS, texts=SELECT_CAR_TEXTS, timeout=2):
            try:
                wait_for_rental_vehicle_list_page(driver, timeout=5)
                return
            except Exception:
                pass
        if tap_by_coordinate_ratios(driver, [(0.50, 0.69), (0.50, 0.71)]):
            wait_for_rental_vehicle_list_page(driver, timeout=10)
            return
        time.sleep(0.3)
    raise AssertionError("Unable to enter the rental vehicle selection page")


def _store_selected(driver: WebDriver) -> bool:
    source = safe_page_source(driver)
    if not source_contains_any(source, ["服务门店", "立即选车"]):
        return False
    return "请选择服务门店" not in source


def _wait_for_store_selected(driver: WebDriver, timeout: int = 5) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if _store_selected(driver):
            return True
        time.sleep(0.2)
    return False
