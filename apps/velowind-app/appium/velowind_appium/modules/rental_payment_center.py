from __future__ import annotations

from contextlib import contextmanager
import os
import time

from appium.webdriver.webdriver import WebDriver

from velowind_appium.modules.rental_common import (
    safe_page_source,
    tap_by_coordinate_ratios,
    tap_by_text_containing,
    tap_first_available,
    tap_visible_text_hit_point,
    tap_visible_text_containing_hit_point,
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
CURRENT_APP_BUNDLE_ID = "com.velowind.rider"


def wait_for_rental_payment_center_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=PAYMENT_PAGE_IDS,
        texts=PAYMENT_PAGE_TEXTS,
        timeout=timeout,
    )


def tap_rental_payment_button(driver: WebDriver, timeout: int = 20) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        source = safe_page_source(driver)
        if source and CURRENT_APP_BUNDLE_ID not in source:
            return
        if tap_first_available(driver, accessibility_ids=CONFIRM_PAYMENT_IDS, texts=CONFIRM_PAYMENT_TEXTS, timeout=2):
            if wait_until_source_contains(driver, ["确认发起支付", "确认"], timeout=10):
                return
        if tap_by_text_containing(driver, ["去支付", "确认支付", "立即支付"], timeout=2):
            if wait_until_source_contains(driver, ["确认发起支付", "确认"], timeout=10):
                return
        if tap_visible_text_containing_hit_point(driver, ["去支付", "确认支付", "立即支付"], timeout=2):
            if wait_until_source_contains(driver, ["确认发起支付", "确认"], timeout=10):
                return
        if tap_visible_text_hit_point(driver, ["去支付", "确认支付", "立即支付"], timeout=2):
            if wait_until_source_contains(driver, ["确认发起支付", "确认"], timeout=10):
                return
        if tap_by_coordinate_ratios(driver, [(0.50, 0.93), (0.50, 0.91)]):
            source = safe_page_source(driver)
            if source and CURRENT_APP_BUNDLE_ID not in source:
                return
            if wait_until_source_contains(driver, ["确认发起支付", "确认"], timeout=10):
                return
        try:
            wait_for_rental_payment_center_page(driver, timeout=2)
        except Exception:
            pass
        time.sleep(0.3)
    raise AssertionError("Unable to tap payment button in rental payment center")


def confirm_payment_then_think_again(driver: WebDriver, timeout: int = 20) -> None:
    with _payment_profile("confirm-wait-payment-center"):
        wait_for_rental_payment_center_page(driver, timeout=timeout)
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if is_ios:
            with _payment_profile("confirm-tap-ios-coordinate"):
                tapped_ios_coordinate = tap_by_coordinate_ratios(driver, [(0.50, 0.93), (0.50, 0.91)])
            if tapped_ios_coordinate:
                break
        with _payment_profile("confirm-tap-first-available"):
            tapped_confirm = tap_first_available(
                driver,
                accessibility_ids=CONFIRM_PAYMENT_IDS,
                texts=CONFIRM_PAYMENT_TEXTS,
                timeout=2,
            )
        if tapped_confirm:
            break
        with _payment_profile("confirm-tap-coordinate"):
            tapped_coordinate = tap_by_coordinate_ratios(driver, [(0.50, 0.93), (0.50, 0.91)])
        if tapped_coordinate:
            break
        time.sleep(0.3)
    else:
        raise AssertionError("Unable to tap confirm payment in rental payment center")

    with _payment_profile("confirm-wait-dialog"):
        dialog_visible = wait_until_source_contains(driver, THINK_AGAIN_TEXTS + ["确认", "支付"], timeout=10)
    if not dialog_visible:
        raise AssertionError("Payment confirmation dialog did not appear")

    with _payment_profile("confirm-dismiss-dialog"):
        dismissed = dismiss_pending_payment_dialog_if_present(driver, timeout=5)
    if not dismissed:
        raise AssertionError("Unable to dismiss payment dialog by tapping think-again")

    with _payment_profile("confirm-wait-my-rental-page"):
        wait_for_my_rental_page(driver, timeout=20)


def dismiss_pending_payment_dialog_if_present(driver: WebDriver, timeout: int = 3) -> bool:
    end_at = time.monotonic() + timeout
    dismissed = False
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"
    while time.monotonic() < end_at:
        source = safe_page_source(driver)
        if "确认发起支付" not in source and not any(text in source for text in THINK_AGAIN_TEXTS):
            return dismissed
        if is_ios and tap_by_coordinate_ratios(driver, [(0.32, 0.56), (0.35, 0.58), (0.32, 0.62)]):
            return True
        if not tap_visible_text_hit_point(driver, THINK_AGAIN_TEXTS, timeout=0.6):
            tap_first_available(driver, accessibility_ids=THINK_AGAIN_IDS, texts=THINK_AGAIN_TEXTS, timeout=1)
            tap_by_coordinate_ratios(driver, [(0.32, 0.56), (0.35, 0.58), (0.32, 0.62)])
        dismissed = True
        time.sleep(0.5)
    return dismissed and "确认发起支付" not in safe_page_source(driver)


def _payment_profile_enabled() -> bool:
    return os.getenv("VW_ACTIVITY_PROFILE", "").strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def _payment_profile(label: str):
    if not _payment_profile_enabled():
        yield
        return
    started = time.monotonic()
    try:
        yield
    finally:
        print(f"[rental-payment-profile] {label}: {time.monotonic() - started:.2f}s")
