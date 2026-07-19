from __future__ import annotations

import time

from appium.webdriver.webdriver import WebDriver

from velowind_appium.modules.rental_common import (
    safe_page_source,
    tap_by_coordinate_ratios,
    tap_first_available,
    wait_for_rental_page,
    wait_until_source_contains,
)
from velowind_appium.modules.rental_orders import wait_for_my_rental_page


PAYMENT_PAGE_IDS = ["rental-payment-center-page", "payment-center-page", "rent-car-payment-page"]
PAYMENT_PAGE_TEXTS = ["支付中心", "确认支付", "订单支付"]
CONFIRM_PAYMENT_IDS = ["rental-confirm-payment-button", "confirm-payment-button", "pay-confirm-button"]
CONFIRM_PAYMENT_TEXTS = ["确认支付", "立即支付", "去支付"]
THINK_AGAIN_IDS = ["payment-think-again-button", "rental-think-again-button", "payment-cancel-button"]
THINK_AGAIN_TEXTS = ["再想想", "想一想", "我再想想", "暂不支付", "取消"]


def wait_for_rental_payment_center_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=PAYMENT_PAGE_IDS,
        texts=PAYMENT_PAGE_TEXTS,
        timeout=timeout,
    )


def confirm_payment_then_think_again(driver: WebDriver, timeout: int = 20) -> None:
    wait_for_rental_payment_center_page(driver, timeout=timeout)
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if tap_first_available(driver, accessibility_ids=CONFIRM_PAYMENT_IDS, texts=CONFIRM_PAYMENT_TEXTS, timeout=2):
            break
        if tap_by_coordinate_ratios(driver, [(0.50, 0.93), (0.50, 0.91)]):
            break
        time.sleep(0.3)
    else:
        raise AssertionError("Unable to tap confirm payment in rental payment center")

    if not wait_until_source_contains(driver, THINK_AGAIN_TEXTS + ["确认", "支付"], timeout=10):
        raise AssertionError("Payment confirmation dialog did not appear")

    if not dismiss_pending_payment_dialog_if_present(driver, timeout=5):
        raise AssertionError("Unable to dismiss payment dialog by tapping think-again")

    wait_for_my_rental_page(driver, timeout=20)


def dismiss_pending_payment_dialog_if_present(driver: WebDriver, timeout: int = 3) -> bool:
    end_at = time.monotonic() + timeout
    dismissed = False
    while time.monotonic() < end_at:
        source = safe_page_source(driver)
        if "确认发起支付" not in source and not any(text in source for text in THINK_AGAIN_TEXTS):
            return dismissed
        tap_first_available(driver, accessibility_ids=THINK_AGAIN_IDS, texts=THINK_AGAIN_TEXTS, timeout=1)
        tap_by_coordinate_ratios(driver, [(0.32, 0.56), (0.35, 0.58), (0.32, 0.62)])
        dismissed = True
        time.sleep(0.5)
    return dismissed and "确认发起支付" not in safe_page_source(driver)
