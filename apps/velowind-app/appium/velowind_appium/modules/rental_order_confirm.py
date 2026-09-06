from __future__ import annotations

import time

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException

from velowind_appium.modules.rental_common import (
    safe_page_source,
    tap_first_available,
    wait_for_rental_page,
)
from velowind_appium.modules.rental_payment_center import wait_for_rental_payment_center_page


CONFIRM_PAGE_IDS = ["rental-order-confirm-page", "rent-car-order-confirm-page", "rental-confirm-order-page"]
CONFIRM_PAGE_TEXTS = ["订单确认", "确认订单", "提交订单", "取车时间", "还车时间"]
SUBMIT_ORDER_IDS = ["rental-submit-order-button", "submit-rental-order-button", "submit-order-button"]
SUBMIT_ORDER_TEXTS = ["提交订单", "确认提交"]
SUBMIT_RETRYABLE_FAILURE_TEXTS = ["订单提交失败", "请稍后重试"]


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
    last_failure_source = ""
    while time.monotonic() < end_at:
        if tap_first_available(driver, accessibility_ids=SUBMIT_ORDER_IDS, texts=SUBMIT_ORDER_TEXTS, timeout=2):
            payment_wait_timeout = min(10, max(2, int(end_at - time.monotonic())))
            try:
                wait_for_rental_payment_center_page(driver, timeout=payment_wait_timeout)
                return
            except TimeoutException:
                source = safe_page_source(driver)
                if _submit_retryable_failure_visible(source):
                    last_failure_source = source
                    time.sleep(0.8)
                    continue
                raise
        time.sleep(0.3)
    if last_failure_source:
        raise AssertionError("Rental order submission kept returning a retryable failure")
    raise AssertionError("Unable to submit rental order from confirmation page")


def _submit_retryable_failure_visible(page_source: str) -> bool:
    return all(text in page_source for text in SUBMIT_RETRYABLE_FAILURE_TEXTS)
