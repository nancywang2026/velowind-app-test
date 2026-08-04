from __future__ import annotations

import os
import re
import subprocess
import time

from appium.webdriver.webdriver import WebDriver
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import safe_back, tap_accessibility_id_or_text_if_present, tap_text_if_present
from velowind_appium.auth import ensure_logged_in_if_needed, login_required_from_page_source
from velowind_appium.config import IosAppiumConfig
from velowind_appium.modules.home_feed import wait_for_home_feed


COMMON_ALERT_TEXTS = ["Close app", "关闭应用", "允许", "好", "以后", "暂不", "取消"]
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
    "activity-route-detail-v3",
    "活动详情",
    "页面预览提示",
    "rent-page-shell",
    "use-car-tab-page",
    "立即选车",
    "服务门店",
    "选择分享方式",
    "微信好友",
    "朋友圈",
    "系统消息",
    "系统通知",
    "内容通知",
    "活动通知",
    'placeholderValue="请输入内容"',
    'hint="请输入内容"',
]
MESSAGE_TAB_BLOCKING_TEXTS = {"系统消息", "系统通知"}


def dismiss_common_system_alerts(driver: WebDriver, step=None) -> None:
    for text in COMMON_ALERT_TEXTS:
        if step is None:
            tap_text_if_present(driver, text, timeout=OPTIONAL_ALERT_TIMEOUT_SECONDS)
        else:
            matched = tap_text_if_present(driver, text, timeout=OPTIONAL_ALERT_TIMEOUT_SECONDS)
            if matched:
                step(
                    f"dismiss-alert-{text}",
                    lambda matched=matched: matched,
                )


def ensure_logged_in_from_me_then_home(driver: WebDriver, ios_config: IosAppiumConfig) -> bool:
    dismiss_common_system_alerts(driver)
    tap_text_if_present(driver, "同意并继续", timeout=2)
    tap_text_if_present(driver, "同意", timeout=1)

    me_tab_opened = tap_accessibility_id_or_text_if_present(driver, "bottom-nav-me", "我的", timeout=8)
    if not me_tab_opened:
        capabilities = getattr(driver, "capabilities", {}) or {}
        is_android = str(capabilities.get("platformName", "")).lower() == "android"
        if is_android:
            for _ in range(3):
                if not (_android_adb_back(driver) or safe_back(driver)):
                    break
                time.sleep(0.3)
                if not _home_visible(driver):
                    _tap_home_tab(driver, timeout=2)
                    time.sleep(0.3)
                if _home_visible(driver):
                    me_tab_opened = tap_accessibility_id_or_text_if_present(driver, "bottom-nav-me", "我的", timeout=3)
                    break
            if not me_tab_opened and not login_required_from_page_source(_safe_page_source(driver)):
                ensure_logged_in_on_home(driver, ios_config)
                me_tab_opened = tap_accessibility_id_or_text_if_present(driver, "bottom-nav-me", "我的", timeout=5)
        if not me_tab_opened and not login_required_from_page_source(_safe_page_source(driver)):
            raise AssertionError("Unable to open the Me tab before running regression cases")
    if _login_required_after_short_wait(driver):
        if not ensure_logged_in_if_needed(driver, ios_config):
            raise AssertionError("Unable to log in from the Me tab before running regression cases")

    _tap_home_tab(driver, timeout=8)
    if not _home_visible(driver):
        try:
            wait_for_home_feed(driver, timeout=20)
        except Exception:
            ensure_logged_in_on_home(driver, ios_config)
    return True


def _login_required_after_short_wait(driver: WebDriver, timeout: float = 3.0) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if login_required_from_page_source(_safe_page_source(driver)):
            return True
        time.sleep(0.2)
    return False


def ensure_logged_in_on_home(driver: WebDriver, ios_config: IosAppiumConfig, step=None) -> bool:
    dismiss_common_system_alerts(driver)
    tap_text_if_present(driver, "同意并继续", timeout=2)
    tap_text_if_present(driver, "同意", timeout=1)

    def _go_home():
        return _tap_home_tab(driver, timeout=5) or _tap_home_tab_by_coordinate(driver)

    def _wait_home():
        if _home_visible(driver):
            return True
        return wait_for_home_feed(driver, timeout=20)

    def _relaunch_from_android_launcher() -> bool:
        if not _android_launcher_visible(driver):
            return False
        for app_name in ["寻风集", "Predicted app: 寻风集"]:
            if tap_accessibility_id_or_text_if_present(driver, app_name, app_name, timeout=2):
                time.sleep(1)
                try:
                    _wait_home()
                except Exception:
                    pass
                return True
        return False

    def _recover_to_home():
        for _ in range(5):
            if _home_visible(driver):
                return True
            if _relaunch_from_android_launcher():
                return True
            if not _home_or_login_visible(driver):
                if _tap_top_back_by_coordinate(driver):
                    time.sleep(0.2)
                    page_source = _safe_page_source(driver)
                    if any(text in page_source for text in ["是否保存草稿", "不保存"]):
                        if tap_text_if_present(driver, "不保存", timeout=0.5):
                            time.sleep(0.2)
                            if _home_visible(driver):
                                return True
                    if _home_visible(driver):
                        return True
                if _android_adb_back(driver):
                    time.sleep(0.3)
                    if _home_visible(driver):
                        return True
                safe_back(driver)
                time.sleep(0.2)
                continue
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
        if _relaunch_from_android_launcher():
            return False

        if _home_or_login_visible(driver) and _go_home():
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
            step("recover-home-session", _recover_to_home)
        return bool(step("prepare-login-and-home", _prepare))

    return bool(_prepare())


def ensure_logged_in_for_publish_entry(driver: WebDriver, ios_config: IosAppiumConfig, step=None) -> bool:
    dismiss_common_system_alerts(driver)
    tap_text_if_present(driver, "同意并继续", timeout=2)
    tap_text_if_present(driver, "同意", timeout=1)

    def _tap_home_fast() -> bool:
        if _tap_home_tab_by_coordinate(driver):
            return True
        return _tap_home_tab(driver, timeout=3)

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
        for _ in range(5):
            if _publish_entry_ready(driver):
                return True
            if not _home_or_login_visible(driver):
                if _tap_top_back_by_coordinate(driver):
                    time.sleep(0.3)
                    if _publish_entry_ready(driver):
                        return True
                if _android_adb_back(driver):
                    time.sleep(0.3)
                    if _publish_entry_ready(driver):
                        return True
                safe_back(driver)
                time.sleep(0.3)
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
    if _me_content_page_visible(page_source):
        return False
    if _home_blocking_text_present(page_source, allow_message_tab=True):
        return False
    if all(text in page_source for text in ["笔记", "活动", "消息", "我的"]):
        return True
    return any(text in page_source for text in ["首页", "笔记", "全国", "推荐", "密码登录", "手机号登录", "请输入手机号"])


def _home_visible(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if _me_content_page_visible(page_source):
        return False
    if _home_blocking_text_present(page_source):
        return False
    return (
        all(text in page_source for text in ["活动", "消息", "我的"])
        and any(text in page_source for text in ["首页", "笔记"])
    ) or any(text in page_source for text in ["全国", "推荐", "骑行", "徒步"])


def _publish_entry_ready(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if _me_content_page_visible(page_source):
        return False
    if _home_blocking_text_present(page_source):
        return False
    return all(text in page_source for text in ["活动", "消息", "我的"]) and any(
        text in page_source for text in ["首页", "笔记", "全国", "推荐"]
    )


def _home_blocking_text_present(page_source: str, *, allow_message_tab: bool = False) -> bool:
    blockers = HOME_BLOCKING_TEXTS
    if allow_message_tab:
        blockers = [text for text in HOME_BLOCKING_TEXTS if text not in MESSAGE_TAB_BLOCKING_TEXTS]
    return any(text in page_source for text in blockers)


def _me_content_page_visible(page_source: str) -> bool:
    if not page_source:
        return False
    return (
        "我的笔记" in page_source
        or all(text in page_source for text in ["我的活动", "发布", "报名"])
        or all(text in page_source for text in ["草稿箱", "我的发布"])
        or all(text in page_source for text in ["个人资料", "昵称", "手机号"])
        or all(text in page_source for text in ["兴趣偏好", "骑行"])
        or all(text in page_source for text in ["设置", "账号与安全", "退出登录"])
        or all(text in page_source for text in ["账号与安全", "绑定手机号", "账号注销"])
        or all(text in page_source for text in ["成为领队", "寻风集领队", "申请状态"])
        or any(text in page_source for text in ["我的卡券", "优惠券"])
    )


def _tap_home_tab(driver: WebDriver, timeout: int = 3) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android" and (
        _tap_android_home_tab_text(driver) or _tap_android_home_tab_by_coordinate(driver)
    ):
        return True
    return (
        tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "笔记", timeout=timeout)
        or tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=1)
    )


def _tap_android_home_tab_text(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    for text in ["笔记", "首页"]:
        for xpath in [
            f'//android.widget.TextView[@text="{text}"]',
            f'//android.view.ViewGroup[.//android.widget.TextView[@text="{text}"]]',
        ]:
            try:
                element = driver.find_element(AppiumBy.XPATH, xpath)
                if _tap_android_element_center(driver, element):
                    return True
                element.click()
                return True
            except (AttributeError, NoSuchElementException, WebDriverException):
                continue
    return False


def _tap_android_element_center(driver: WebDriver, element) -> bool:
    bounds = ""
    try:
        bounds = element.get_attribute("bounds") or ""
    except (AttributeError, WebDriverException):
        bounds = ""
    match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", bounds)
    try:
        if match:
            left, top, right, bottom = (int(value) for value in match.groups())
            x = (left + right) // 2
            y = (top + bottom) // 2
        else:
            rect = element.rect
            x = int(rect["x"] + rect["width"] / 2)
            y = int(rect["y"] + rect["height"] / 2)
        driver.execute_script("mobile: tap", {"x": x, "y": y})
        _android_adb_tap(driver, x, y)
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _android_launcher_visible(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    page_source = _safe_page_source(driver)
    return "com.google.android.apps.nexuslauncher" in page_source


def _tap_android_home_tab_by_coordinate(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    try:
        rect = driver.get_window_rect()
        x = int(rect["width"] * 0.10)
        y = int(rect["height"] * 0.94)
        driver.execute_script(
            "mobile: tap",
            {
                "x": x,
                "y": y,
            },
        )
        _android_adb_tap(driver, x, y)
        return True
    except Exception:
        return False


def _android_adb_tap(driver: WebDriver, x: int, y: int) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    udid = str(capabilities.get("appium:udid") or capabilities.get("udid") or "").strip()
    if not udid:
        return False
    try:
        subprocess.run(
            ["adb", "-s", udid, "shell", "input", "tap", str(x), str(y)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def _tap_home_tab_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.12),
                "y": int(rect["height"] * 0.90),
            },
        )
        return True
    except Exception:
        return False


def _tap_top_back_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.05),
                "y": int(rect["height"] * 0.10),
            },
        )
        return True
    except Exception:
        return False


def _android_adb_back(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    udid = (
        str(capabilities.get("appium:udid") or capabilities.get("udid") or "").strip()
        or os.environ.get("VW_ANDROID_UDID", "").strip()
    )
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
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except Exception:
        return ""
