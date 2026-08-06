import pytest

from velowind_appium.modules import (
    open_account_security_page,
    open_interest_preferences_page,
    open_leader_application_page,
    open_my_coupons_page,
    open_profile_page,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_read_session_on_home


@pytest.mark.full
def test_user_can_view_profile_basic_fields(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_read_session_on_home(driver, ios_config))
    snapshot = step("open-profile-page", lambda: open_profile_page(driver, timeout=20), capture=True)

    assert snapshot.is_basic_profile_visible(), f"Expected profile basic fields to be visible, got: {snapshot}"


@pytest.mark.full
def test_user_can_view_interest_preferences(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_read_session_on_home(driver, ios_config))
    snapshot = step(
        "open-interest-preferences-page",
        lambda: open_interest_preferences_page(driver, timeout=20),
        capture=True,
    )

    assert snapshot.is_basic_preferences_visible(), f"Expected interest preference options to be visible, got: {snapshot}"


@pytest.mark.full
def test_user_can_open_my_coupons_page(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_read_session_on_home(driver, ios_config))
    snapshot = step("open-my-coupons-page", lambda: open_my_coupons_page(driver, timeout=20), capture=True)

    assert snapshot.is_basic_coupons_visible(), f"Expected coupon status tabs to be visible, got: {snapshot}"


@pytest.mark.full
def test_user_can_view_account_security_page(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_read_session_on_home(driver, ios_config))
    snapshot = step(
        "open-account-security-page",
        lambda: open_account_security_page(driver, timeout=20),
        capture=True,
    )

    assert snapshot.is_basic_account_security_visible(), f"Expected account security fields to be visible, got: {snapshot}"


@pytest.mark.full
def test_user_can_view_leader_application_page(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_read_session_on_home(driver, ios_config))
    snapshot = step(
        "open-leader-application-page",
        lambda: open_leader_application_page(driver, timeout=20),
        capture=True,
    )

    assert snapshot.is_basic_leader_application_visible(), f"Expected leader application content to be visible, got: {snapshot}"
