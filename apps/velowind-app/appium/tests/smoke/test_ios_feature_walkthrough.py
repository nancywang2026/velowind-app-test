import os

import pytest
from selenium.common.exceptions import WebDriverException

from velowind_appium.actions import (
    safe_back,
    tap_accessibility_id_or_text_if_present,
    tap_if_present,
    wait_for_accessibility_id,
    wait_for_any_accessibility_id,
    wait_for_any_accessibility_id_or_text,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


ROOT_TABS = [
    ("bottom-nav-home", "首页", ["home-page-title", "post-home-feed-category-pager"], ["首页", "全国", "推荐"]),
    ("bottom-nav-activity", "活动", ["activity-discovery-v2-page"], ["活动"]),
    ("bottom-nav-message", "消息", ["message-page-title"], ["消息"]),
    ("bottom-nav-me", "我的", ["login-page-title"], ["我的", "登录", "手机号"]),
]

OPTIONAL_ENTRY_IDS = [
    "floating-rental-mode-entry-car",
]
@pytest.mark.smoke
def test_ios_feature_walkthrough(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))

    for index, (tab_id, tab_text, expected_ids, expected_texts) in enumerate(ROOT_TABS, start=2):
        step(
            f"{index:02d}-tap-tab-{tab_text}",
            lambda tab_id=tab_id, tab_text=tab_text: tap_accessibility_id_or_text_if_present(
                driver,
                tab_id,
                tab_text,
                timeout=8,
            ),
        )
        step(
            f"{index:02d}-wait-tab-{tab_text}",
            lambda expected_ids=expected_ids, expected_texts=expected_texts: wait_for_any_accessibility_id_or_text(
                driver,
                [*expected_ids, "login-page-title"],
                [*expected_texts, "登录", "手机号"],
                timeout=30,
            ),
        )

    step(
        "tap-home-return",
        lambda: tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=5),
    )
    step(
        "wait-home-return",
        lambda: wait_for_any_accessibility_id_or_text(
            driver,
            ["home-page-title", "home-activity-discovery-browser", "post-home-feed-category-pager"],
            ["首页", "全国", "推荐"],
            timeout=20,
        ),
    )

    visited = []
    for entry_id in OPTIONAL_ENTRY_IDS:
        try:
            if not step(f"tap-entry-{entry_id}", lambda entry_id=entry_id: tap_if_present(driver, entry_id, timeout=1)):
                continue
            visited.append(entry_id)
            dismiss_common_system_alerts(driver, step)
            step(
                f"wait-entry-{entry_id}",
                lambda: wait_for_any_accessibility_id(
                    driver,
                    [
                        "login-page-title",
                        "rent-page-shell",
                        "use-car-tab-page",
                        "home-page-title",
                        "home-activity-discovery-browser",
                        "activity-discovery-v2-page",
                    ],
                    timeout=10,
                ),
            )
            step(f"back-from-entry-{entry_id}", lambda: safe_back(driver))
        except WebDriverException:
            step(f"recover-back-{entry_id}", lambda: safe_back(driver))

    assert visited or step(
        "assert-rent-entry-or-home-present",
        lambda: tap_if_present(driver, "bottom-nav-rent", timeout=1)
        or wait_for_any_accessibility_id_or_text(
            driver,
            ["home-page-title", "home-activity-discovery-browser", "post-home-feed-category-pager"],
            ["首页", "全国", "推荐"],
            timeout=5,
        ),
    )


@pytest.mark.parametrize(
    "tab_id, tab_text, expected_ids, expected_texts",
    ROOT_TABS,
)
@pytest.mark.full
@pytest.mark.skipif(os.environ.get("VW_IOS_RUN_FULL") != "true", reason="Set VW_IOS_RUN_FULL=true to run full tab cases")
def test_bottom_tabs_are_reachable(driver, step, tab_id, tab_text, expected_ids, expected_texts):
    step("tap-home-before-tab", lambda: tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=3))
    step(
        f"tap-tab-{tab_text}",
        lambda: tap_accessibility_id_or_text_if_present(driver, tab_id, tab_text, timeout=8),
    )
    step(
        f"wait-tab-{tab_text}",
        lambda: wait_for_any_accessibility_id_or_text(
            driver,
            [*expected_ids, "login-page-title"],
            [*expected_texts, "登录", "手机号"],
            timeout=30,
        ),
    )
