import pytest

from velowind_appium.modules import (
    ActivitySignupAlreadyExistsError,
    browse_activity_detail,
    build_activity_signup_draft,
    fill_activity_signup_form,
    activity_feed_all_results_match_category,
    activity_text_search_result_texts,
    open_first_activity_detail,
    open_activity_signup,
    open_activity_search,
    open_activity_tab,
    open_my_activity_reaction_list,
    open_my_activity_signup_status,
    read_activity_signup_snapshot,
    search_activities,
    select_activity_category,
    submit_activity_signup_order,
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


@pytest.mark.full
def test_user_can_open_activity_signup_form(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-activity-tab", lambda: open_activity_tab(driver, timeout=20))
    step("wait-activity-feed", lambda: wait_for_activity_feed(driver, timeout=20))
    step("open-first-activity-detail", lambda: open_first_activity_detail(driver, timeout=20), capture=True)
    step("open-activity-signup", lambda: open_activity_signup(driver, timeout=20), capture=True)
    snapshot = step("read-activity-signup", lambda: read_activity_signup_snapshot(driver, timeout=15), capture=True)

    assert snapshot.is_basic_signup_complete(), f"Expected complete activity signup snapshot, got: {snapshot}"


@pytest.mark.full
def test_user_can_fill_activity_signup_identity_fields(driver, ios_config, step):
    draft = build_activity_signup_draft()
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-activity-tab", lambda: open_activity_tab(driver, timeout=20))
    step("wait-activity-feed", lambda: wait_for_activity_feed(driver, timeout=20))
    step("open-first-activity-detail", lambda: open_first_activity_detail(driver, timeout=20), capture=True)
    step("open-activity-signup", lambda: open_activity_signup(driver, timeout=20), capture=True)
    snapshot = step("fill-activity-signup", lambda: fill_activity_signup_form(driver, draft, timeout=20), capture=True)

    assert snapshot.matches_draft(draft) or snapshot.self_registration_selected, (
        f"Expected signup form to echo draft values or use the selected self registration, got: {snapshot}"
    )


@pytest.mark.full
def test_user_can_submit_activity_signup_to_payment_page(driver, ios_config, step):
    draft = build_activity_signup_draft()
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-activity-tab", lambda: open_activity_tab(driver, timeout=20))
    step("wait-activity-feed", lambda: wait_for_activity_feed(driver, timeout=20))
    step("open-first-activity-detail", lambda: open_first_activity_detail(driver, timeout=20), capture=True)
    step("open-activity-signup", lambda: open_activity_signup(driver, timeout=20), capture=True)
    step("fill-activity-signup", lambda: fill_activity_signup_form(driver, draft, timeout=20), capture=True)
    if "已经报名，无需重复报名" in driver.page_source:
        pytest.skip("The current account already has an activity signup for this session")
    try:
        snapshot = step("submit-activity-signup-order", lambda: submit_activity_signup_order(driver, timeout=25), capture=True)
    except ActivitySignupAlreadyExistsError as error:
        pytest.skip(str(error))

    assert snapshot.is_order_submission_complete(), f"Expected signup submission to reach payment/order page, got: {snapshot}"


@pytest.mark.full
def test_user_can_view_my_activity_signup_status(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    snapshot = step(
        "open-my-activity-signup-status",
        lambda: open_my_activity_signup_status(driver, timeout=25),
        capture=True,
    )

    assert snapshot.is_signup_status_visible(), f"Expected My Activity signup status to be visible, got: {snapshot}"
    assert snapshot.status in {"待支付", "支付未完成", "报名成功", "报名待支付", "已报名"}


@pytest.mark.full
def test_user_can_open_my_activity_signup_list(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    snapshot = step(
        "open-my-activity-signup-list",
        lambda: open_my_activity_signup_status(driver, timeout=25),
        capture=True,
    )

    assert snapshot.page_visible, f"Expected My Activity page to be visible, got: {snapshot}"
    assert snapshot.signup_tab_visible, f"Expected signup tab to be visible, got: {snapshot}"
    assert snapshot.registration_visible, f"Expected at least one signup record to be visible, got: {snapshot}"


@pytest.mark.full
def test_user_can_open_my_activity_liked_list(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    snapshot = step(
        "open-my-activity-liked-list",
        lambda: open_my_activity_reaction_list(driver, tab_name="点赞", timeout=25),
        capture=True,
    )

    assert snapshot.is_basic_reaction_list_visible(), f"Expected My Activity liked list to be visible, got: {snapshot}"


@pytest.mark.full
def test_user_can_open_my_activity_favorite_list(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    snapshot = step(
        "open-my-activity-favorite-list",
        lambda: open_my_activity_reaction_list(driver, tab_name="收藏", timeout=25),
        capture=True,
    )

    assert snapshot.is_basic_reaction_list_visible(), f"Expected My Activity favorite list to be visible, got: {snapshot}"
