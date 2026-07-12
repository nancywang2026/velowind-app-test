from __future__ import annotations

import time

from appium.webdriver.webdriver import WebDriver

from velowind_appium.actions import safe_back, tap_accessibility_id_or_text_if_present, tap_text_if_present
from velowind_appium.auth import ensure_logged_in_if_needed, login_required_from_page_source
from velowind_appium.config import IosAppiumConfig
from velowind_appium.modules.home_feed import wait_for_home_feed


COMMON_ALERT_TEXTS = ["允许", "好", "以后", "暂不", "取消"]
OPTIONAL_ALERT_TIMEOUT_SECONDS = 0.2
HOME_BLOCKING_TEXTS = [
    "发布活动",
    "提交审核",
    "存草稿",
    "活动图片",
    "写留言",
    "手机号登录",
    "请输入手机号",
    "密码登录",
    "验证并登录",
    "post-detail-banner-pager",
    "post-detail-page",
    "message-detail-page",
    "article-detail-page",
]


def dismiss_common_system_alerts(driver: WebDriver, step=None) -> None:
    for text in COMMON_ALERT_TEXTS:
        if step is None:
            tap_text_if_present(driver, text, timeout=OPTIONAL_ALERT_TIMEOUT_SECONDS)
        else:
            step(
                f"dismiss-alert-{text}",
                lambda text=text: tap_text_if_present(driver, text, timeout=OPTIONAL_ALERT_TIMEOUT_SECONDS),
            )


def ensure_logged_in_from_me_then_home(driver: WebDriver, ios_config: IosAppiumConfig) -> bool:
    dismiss_common_system_alerts(driver)
    tap_text_if_present(driver, "同意并继续", timeout=2)
    tap_text_if_present(driver, "同意", timeout=1)

    if not tap_accessibility_id_or_text_if_present(driver, "bottom-nav-me", "我的", timeout=8):
        if not login_required_from_page_source(_safe_page_source(driver)):
            raise AssertionError("Unable to open the Me tab before running regression cases")
    if login_required_from_page_source(_safe_page_source(driver)):
        if not ensure_logged_in_if_needed(driver, ios_config):
            raise AssertionError("Unable to log in from the Me tab before running regression cases")

    tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=8)
    if not _home_visible(driver):
        wait_for_home_feed(driver, timeout=20)
    return True


def ensure_logged_in_on_home(driver: WebDriver, ios_config: IosAppiumConfig, step=None) -> bool:
    dismiss_common_system_alerts(driver)
    tap_text_if_present(driver, "同意并继续", timeout=2)
    tap_text_if_present(driver, "同意", timeout=1)

    def _go_home():
        return tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=5)

    def _wait_home():
        if _home_visible(driver):
            return True
        return wait_for_home_feed(driver, timeout=20)

    def _recover_to_home():
        for _ in range(2):
            if _go_home():
                try:
                    _wait_home()
                    return True
                except Exception:
                    pass
            safe_back(driver)
        _go_home()
        _wait_home()
        return True

    def _prepare() -> bool:
        if _go_home():
            try:
                _wait_home()
                return False
            except Exception:
                pass

        if login_required_from_page_source(_safe_page_source(driver)):
            logged_in = ensure_logged_in_if_needed(driver, ios_config)
            _recover_to_home()
            return bool(logged_in)

        _recover_to_home()
        return False

    if step is not None:
        if not _home_or_login_visible(driver):
            step("wait-home-feed-ready", _wait_home)
        return bool(step("prepare-login-and-home", _prepare))

    if not _home_or_login_visible(driver):
        _wait_home()
    return bool(_prepare())


def ensure_logged_in_for_publish_entry(driver: WebDriver, ios_config: IosAppiumConfig, step=None) -> bool:
    dismiss_common_system_alerts(driver)
    tap_text_if_present(driver, "同意并继续", timeout=2)
    tap_text_if_present(driver, "同意", timeout=1)

    def _tap_home_fast() -> bool:
        if _tap_home_tab_by_coordinate(driver):
            return True
        return tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=3)

    def _wait_publish_ready(timeout: int = 8) -> bool:
        end_at = time.monotonic() + timeout
        while time.monotonic() < end_at:
            page_source = _safe_page_source(driver)
            if login_required_from_page_source(page_source):
                return True
            if _publish_entry_ready(driver):
                return True
            time.sleep(0.2)
        return False

    def _recover() -> bool:
        for _ in range(2):
            if _publish_entry_ready(driver):
                return True
            _tap_home_fast()
            if _wait_publish_ready():
                return _publish_entry_ready(driver)
            safe_back(driver)
        _tap_home_fast()
        _wait_publish_ready()
        return _publish_entry_ready(driver)

    def _prepare() -> bool:
        if _publish_entry_ready(driver):
            return False

        page_source = _safe_page_source(driver)
        if login_required_from_page_source(page_source):
            logged_in = ensure_logged_in_if_needed(driver, ios_config)
            _recover()
            return bool(logged_in)

        if not _home_or_login_visible(driver):
            _wait_publish_ready()

        if login_required_from_page_source(_safe_page_source(driver)):
            logged_in = ensure_logged_in_if_needed(driver, ios_config)
            _recover()
            return bool(logged_in)

        _recover()
        return False

    if step is not None:
        return bool(step("prepare-publish-entry-session", _prepare))
    return bool(_prepare())


def _home_or_login_visible(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if any(text in page_source for text in HOME_BLOCKING_TEXTS):
        return False
    return any(text in page_source for text in ["首页", "全国", "推荐", "密码登录", "手机号登录", "请输入手机号"])


def _home_visible(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if any(text in page_source for text in HOME_BLOCKING_TEXTS):
        return False
    return all(text in page_source for text in ["首页", "活动", "消息", "我的"]) or any(
        text in page_source for text in ["全国", "推荐", "骑行", "徒步"]
    )


def _publish_entry_ready(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if any(text in page_source for text in HOME_BLOCKING_TEXTS):
        return False
    return all(text in page_source for text in ["首页", "活动", "消息", "我的"])


def _tap_home_tab_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.12),
                "y": int(rect["height"] * 0.93),
            },
        )
        return True
    except Exception:
        return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except Exception:
        return ""
