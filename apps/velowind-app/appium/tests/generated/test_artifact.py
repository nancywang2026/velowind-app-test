import pytest

from velowind_appium.actions import (
    enter_text_if_present,
    safe_back,
    swipe_vertical,
    tap_accessibility_id_or_text_if_present,
    tap_if_present,
    tap_text_if_present,
    wait_for_any_accessibility_id_or_text,
)
from velowind_appium.modules import (
    choose_first_store,
    open_available_vehicle_detail,
    open_rental_from_home,
    submit_rental_order,
    tap_book_now,
    tap_rental_payment_button,
    tap_select_car_now,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


@pytest.mark.manual_recording
def test_artifact(driver, ios_config, step):
    """Generated from manual recording: /private/var/folders/gj/7mdg85d11911slmkjlzzbk8h0000gn/T/pytest-of-test/pytest-23/test_generate_test_module_writ0/recording.json"""
    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))

    step(
        'artifact',
        lambda: tap_rental_payment_button(driver, timeout=20),
        capture=True,
    )
