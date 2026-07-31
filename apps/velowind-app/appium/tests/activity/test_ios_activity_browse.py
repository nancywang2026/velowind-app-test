import pytest

from velowind_appium.modules import (
    browse_activity_detail,
    activity_feed_all_results_match_category,
    activity_text_search_result_texts,
    open_first_activity_detail,
    open_activity_search,
    open_activity_tab,
    search_activities,
    select_activity_category,
    switch_activity_category_navigation,
    wait_for_activity_feed,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


ACTIVITY_CATEGORY = "骑行"
ACTIVITY_SEARCH_KEYWORD = "张家界"


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


@pytest.mark.full
def test_user_can_search_activities_by_title_or_location(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-activity-tab", lambda: open_activity_tab(driver, timeout=20))
    step("wait-activity-feed", lambda: wait_for_activity_feed(driver, timeout=20))
    step("open-activity-search", lambda: open_activity_search(driver, timeout=10), capture=True)
    step("search-activities-by-keyword", lambda: search_activities(driver, ACTIVITY_SEARCH_KEYWORD, timeout=15), capture=True)

    matching_results = activity_text_search_result_texts(driver.page_source, ACTIVITY_SEARCH_KEYWORD)
    assert matching_results, f"Expected at least one visible activity search result for {ACTIVITY_SEARCH_KEYWORD}"


@pytest.mark.full
def test_user_can_browse_activity_detail_fields(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-activity-tab", lambda: open_activity_tab(driver, timeout=20))
    step("wait-activity-feed", lambda: wait_for_activity_feed(driver, timeout=20))
    step("open-first-activity-detail", lambda: open_first_activity_detail(driver, timeout=20), capture=True)
    snapshot = step("browse-activity-detail", lambda: browse_activity_detail(driver, timeout=25), capture=True)

    assert snapshot.is_basic_detail_complete(), f"Expected complete activity detail snapshot, got: {snapshot}"
