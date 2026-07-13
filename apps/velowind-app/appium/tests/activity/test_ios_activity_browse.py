import pytest

from velowind_appium.modules import (
    activity_feed_all_results_match_category,
    open_activity_tab,
    select_activity_category,
    switch_activity_category_navigation,
    wait_for_activity_feed,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


ACTIVITY_CATEGORY = "骑行"


@pytest.mark.full
def test_user_can_filter_activities_by_cycling(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-activity-tab", lambda: open_activity_tab(driver, timeout=20))
    step("wait-activity-feed", lambda: wait_for_activity_feed(driver, timeout=20))
    step("switch-activity-category-navigation", lambda: switch_activity_category_navigation(driver, timeout=8))
    step("select-cycling-category", lambda: select_activity_category(driver, ACTIVITY_CATEGORY, timeout=10))

    all_results_match, mismatched_activities = activity_feed_all_results_match_category(
        driver.page_source,
        ACTIVITY_CATEGORY,
    )
    assert all_results_match, (
        f"Expected all visible activity cards to match {ACTIVITY_CATEGORY}, "
        f"mismatched: {mismatched_activities}"
    )
