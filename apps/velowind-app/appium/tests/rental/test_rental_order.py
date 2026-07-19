import pytest

from velowind_appium.modules import (
    assert_vehicle_basic_info_visible,
    choose_first_store,
    confirm_payment_then_think_again,
    dismiss_pending_payment_dialog_if_present,
    open_available_vehicle_detail,
    open_rental_from_home,
    read_latest_rental_order_summary,
    submit_rental_order,
    tap_book_now,
    tap_select_car_now,
    wait_for_rental_store_page,
)
from velowind_appium.actions import safe_back
from velowind_appium.modules.home_feed import wait_for_home_feed
from velowind_appium.modules.rental_common import tap_by_coordinate_ratios
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


@pytest.mark.rental
@pytest.mark.android_smoke
@pytest.mark.skip_home_session
def test_user_can_create_rental_order_and_leave_payment_unfinished(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)
    step("dismiss-stale-payment-dialog-if-present", lambda: dismiss_pending_payment_dialog_if_present(driver))
    step("prepare-home-session", lambda: _prepare_rental_home(driver, ios_config))

    step("open-rental-from-home-floating-truck", lambda: open_rental_from_home(driver, timeout=25), capture=True)
    step("wait-rental-store-page", lambda: wait_for_rental_store_page(driver, timeout=20))
    step("choose-first-store", lambda: choose_first_store(driver, timeout=15))
    step("tap-select-car-now", lambda: tap_select_car_now(driver, timeout=20), capture=True)

    step("open-available-vehicle-detail", lambda: open_available_vehicle_detail(driver, timeout=20), capture=True)
    step("assert-vehicle-basic-info", lambda: assert_vehicle_basic_info_visible(driver, timeout=20))
    step("tap-book-now", lambda: tap_book_now(driver, timeout=20), capture=True)
    step("submit-rental-order", lambda: submit_rental_order(driver, timeout=25), capture=True)
    step("confirm-payment-then-think-again", lambda: confirm_payment_then_think_again(driver, timeout=25), capture=True)

    summary = step(
        "read-my-rental-unfinished-order",
        lambda: read_latest_rental_order_summary(driver, timeout=25),
        capture=True,
    )
    assert summary.is_complete(), f"Expected complete unfinished rental order summary, got: {summary}"


def _prepare_rental_home(driver, ios_config) -> None:
    try:
        ensure_logged_in_on_home(driver, ios_config)
        return
    except Exception:
        pass
    tap_by_coordinate_ratios(driver, [(0.10, 0.94), (0.12, 0.92)])
    wait_for_home_feed(driver, timeout=20)
