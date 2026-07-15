import os

import pytest

from velowind_appium.actions import (
    tap_accessibility_id_or_text_if_present,
    tap_text_if_present,
    wait_for_any_accessibility_id_or_text,
    wait_for_any_visible_text,
)
from velowind_appium.session import dismiss_common_system_alerts


ROOT_TABS = [
    ("bottom-nav-home", "首页", ["home-page-title", "post-home-feed-category-pager"], ["首页", "全国", "推荐"]),
    ("bottom-nav-activity", "活动", ["activity-discovery-v2-page"], ["活动"]),
    ("bottom-nav-message", "消息", ["message-page-title"], ["消息"]),
    ("bottom-nav-me", "我的", ["login-page-title"], ["我的", "登录", "手机号"]),
]

HOME_CATEGORIES = ["骑行", "徒步", "滑雪"]


def prepare_android_home(android_driver, step) -> bool:
    dismiss_common_system_alerts(android_driver, step)
    step("accept-privacy-if-present", lambda: tap_text_if_present(android_driver, "同意并继续", timeout=2))
    step("accept-agreement-if-present", lambda: tap_text_if_present(android_driver, "同意", timeout=1))
    step(
        "tap-home",
        lambda: tap_accessibility_id_or_text_if_present(android_driver, "bottom-nav-home", "首页", timeout=5),
    )
    return bool(
        step(
            "wait-home",
            lambda: wait_for_any_accessibility_id_or_text(
                android_driver,
                ["home-page-title", "post-home-feed-category-pager", "login-page-title"],
                ["首页", "全国", "推荐", "登录", "手机号"],
                timeout=30,
            ),
        )
    )


@pytest.mark.android_smoke
def test_android_home_categories_are_reachable(android_driver, step):
    assert prepare_android_home(android_driver, step)

    for index, category in enumerate(HOME_CATEGORIES, start=1):
        assert step(
            f"{index:02d}-tap-category-{category}",
            lambda category=category: tap_text_if_present(android_driver, category, timeout=8),
        )
        step(
            f"{index:02d}-wait-category-{category}",
            lambda category=category: wait_for_any_visible_text(android_driver, [category], timeout=15),
            capture=True,
        )


@pytest.mark.parametrize(
    "tab_id, tab_text, expected_ids, expected_texts",
    ROOT_TABS,
)
@pytest.mark.full
@pytest.mark.skipif(os.environ.get("VW_ANDROID_RUN_FULL") != "true", reason="Set VW_ANDROID_RUN_FULL=true to run full tab cases")
def test_android_bottom_tabs_are_reachable(android_driver, step, tab_id, tab_text, expected_ids, expected_texts):
    prepare_android_home(android_driver, step)
    step(
        f"tap-tab-{tab_text}",
        lambda: tap_accessibility_id_or_text_if_present(android_driver, tab_id, tab_text, timeout=8),
    )
    step(
        f"wait-tab-{tab_text}",
        lambda: wait_for_any_accessibility_id_or_text(
            android_driver,
            [*expected_ids, "login-page-title"],
            [*expected_texts, "登录", "手机号"],
            timeout=30,
        ),
    )
