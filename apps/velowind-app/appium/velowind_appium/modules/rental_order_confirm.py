from __future__ import annotations

import time

from appium.webdriver.webdriver import WebDriver

from velowind_appium.modules.rental_common import (
    tap_first_available,
    wait_for_rental_page,
)
from velowind_appium.modules.rental_payment_center import wait_for_rental_payment_center_page


CONFIRM_PAGE_IDS = ["rental-order-confirm-page", "rent-car-order-confirm-page", "rental-confirm-order-page"]
CONFIRM_PAGE_TEXTS = ["订单确认", "确认订单", "提交订单", "取车时间", "还车时间"]
SUBMIT_ORDER_IDS = ["rental-submit-order-button", "submit-rental-order-button", "submit-order-button"]
SUBMIT_ORDER_TEXTS = ["提交订单", "确认提交"]


def wait_for_rental_order_confirm_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=CONFIRM_PAGE_IDS,
        texts=CONFIRM_PAGE_TEXTS,
        timeout=timeout,
    )


def submit_rental_order(driver: WebDriver, timeout: int = 20) -> None:
    wait_for_rental_order_confirm_page(driver, timeout=timeout)
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if tap_first_available(driver, accessibility_ids=SUBMIT_ORDER_IDS, texts=SUBMIT_ORDER_TEXTS, timeout=2):
            wait_for_rental_payment_center_page(driver, timeout=12)
            return
        time.sleep(0.3)
    raise AssertionError("Unable to submit rental order from confirmation page")
