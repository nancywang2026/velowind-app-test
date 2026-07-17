import os
import subprocess
import time

import pytest

from velowind_appium.actions import (
    safe_back,
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
ANDROID_HOME_BLOCKING_TEXTS = [
    "发布笔记",
    "添加标题",
    "添加正文",
    "存草稿",
    "提交审核",
    "标记地点",
    "活动详情",
    "发布活动",
    "登录",
    "手机号",
    "选择分享方式",
    "微信好友",
    "朋友圈",
    "写留言",
    "共 0 条评论",
    "浏览",
    "评论",
]


def prepare_android_home(android_driver, step) -> bool:
    dismiss_common_system_alerts(android_driver, step)
    step("accept-privacy-if-present", lambda: tap_text_if_present(android_driver, "同意并继续", timeout=2))
    step("accept-agreement-if-present", lambda: tap_text_if_present(android_driver, "同意", timeout=1))
    step("recover-home-session", lambda: _recover_android_home(android_driver))
    step(
        "tap-home",
        lambda: tap_accessibility_id_or_text_if_present(android_driver, "bottom-nav-home", "首页", timeout=5),
    )
    return bool(step("wait-home", lambda: _wait_android_home_ready(android_driver, timeout=30)))


def _recover_android_home(android_driver) -> bool:
    for _ in range(6):
        if _android_home_ready(android_driver):
            return True
        page_source = _safe_page_source(android_driver)
        if any(text in page_source for text in ANDROID_HOME_BLOCKING_TEXTS):
            if _dismiss_android_overlay(android_driver, page_source):
                time.sleep(0.4)
                continue
            if tap_text_if_present(android_driver, "不保存", timeout=1):
                time.sleep(0.3)
                continue
            if _tap_android_top_back(android_driver):
                time.sleep(0.4)
            safe_back(android_driver)
            time.sleep(0.4)
            continue
        tap_accessibility_id_or_text_if_present(android_driver, "bottom-nav-home", "首页", timeout=2)
        time.sleep(0.4)
    return _android_home_ready(android_driver)


def _dismiss_android_overlay(android_driver, page_source: str) -> bool:
    if "选择分享方式" in page_source or "微信好友" in page_source or "朋友圈" in page_source:
        if _tap_android_share_sheet_close(android_driver):
            return True
        if _android_adb_back(android_driver):
            return True
        safe_back(android_driver)
        return True
    if _android_search_page_visible(page_source):
        if _tap_android_header_close(android_driver) or _android_adb_back(android_driver) or _tap_android_top_back(android_driver):
            return True
        safe_back(android_driver)
        return True
    if _android_detail_page_visible(page_source):
        if _android_adb_back(android_driver) or _tap_android_top_back(android_driver):
            return True
        safe_back(android_driver)
        return True
    if _android_image_preview_visible(page_source):
        if _android_adb_back(android_driver) or _tap_android_top_back(android_driver):
            return True
        safe_back(android_driver)
        return True
    return False


def _wait_android_home_ready(android_driver, timeout: int = 30) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if _android_home_ready(android_driver):
            return True
        _recover_android_home(android_driver)
        time.sleep(0.3)
    return False


def _android_home_ready(android_driver) -> bool:
    page_source = _safe_page_source(android_driver)
    if any(text in page_source for text in ANDROID_HOME_BLOCKING_TEXTS):
        return False
    return (
        ("首页" in page_source and "全国" in page_source and "推荐" in page_source)
        or "post-home-feed-category-pager" in page_source
        or ("首页" in page_source and "活动" in page_source and "消息" in page_source and "我的" in page_source)
    )


def _tap_android_top_back(android_driver) -> bool:
    try:
        rect = android_driver.get_window_rect()
        for x_ratio, y_ratio in [(0.04, 0.06), (0.06, 0.09), (0.05, 0.11)]:
            android_driver.execute_script(
                "mobile: tap",
                {
                    "x": int(rect["width"] * x_ratio),
                    "y": int(rect["height"] * y_ratio),
                },
            )
            time.sleep(0.2)
            if _android_home_ready(android_driver):
                return True
        return True
    except Exception:
        return False


def _tap_android_header_close(android_driver) -> bool:
    try:
        rect = android_driver.get_window_rect()
        for x_ratio, y_ratio in [(0.93, 0.09), (0.95, 0.09), (0.91, 0.09)]:
            android_driver.execute_script(
                "mobile: tap",
                {
                    "x": int(rect["width"] * x_ratio),
                    "y": int(rect["height"] * y_ratio),
                },
            )
            time.sleep(0.2)
            if _android_home_ready(android_driver):
                return True
        return True
    except Exception:
        return False


def _tap_android_share_sheet_close(android_driver) -> bool:
    try:
        rect = android_driver.get_window_rect()
        for x_ratio, y_ratio in [(0.95, 0.81), (0.95, 0.84), (0.97, 0.81)]:
            android_driver.execute_script(
                "mobile: tap",
                {
                    "x": int(rect["width"] * x_ratio),
                    "y": int(rect["height"] * y_ratio),
                },
            )
            time.sleep(0.2)
            page_source = _safe_page_source(android_driver)
            if "选择分享方式" not in page_source and "微信好友" not in page_source:
                return True
        return False
    except Exception:
        return False


def _android_image_preview_visible(page_source: str) -> bool:
    if "选择分享方式" in page_source:
        return False
    return "android:id/content" in page_source and "resource-id=\"image\"" not in page_source and "朋友圈" not in page_source


def _android_search_page_visible(page_source: str) -> bool:
    return "android.widget.EditText" in page_source and 'text="搜索"' in page_source


def _android_detail_page_visible(page_source: str) -> bool:
    if any(text in page_source for text in ["写留言", "共 0 条评论", "地点 |", "浏览", "评论"]):
        return True
    if any(text in page_source for text in ["首页", "活动", "消息", "我的"]):
        return False
    if _android_search_page_visible(page_source) or "选择分享方式" in page_source:
        return False
    return page_source.count('resource-id="image"') >= 3 and page_source.count('text="赞"') >= 1


def _android_adb_back(android_driver) -> bool:
    capabilities = getattr(android_driver, "capabilities", {}) or {}
    udid = str(capabilities.get("appium:udid") or capabilities.get("udid") or os.environ.get("VW_ANDROID_UDID", "")).strip()
    if not udid:
        return False
    try:
        subprocess.run(
            ["adb", "-s", udid, "shell", "input", "keyevent", "4"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        time.sleep(0.2)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _safe_page_source(android_driver) -> str:
    try:
        return android_driver.page_source
    except Exception:
        return ""


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
