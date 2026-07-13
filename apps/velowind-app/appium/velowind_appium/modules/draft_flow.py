from __future__ import annotations

import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import tap_accessibility_id_or_text_if_present, tap_text_if_present
from velowind_appium.config import IosAppiumConfig
from velowind_appium.modules import message_detail


SAVE_DRAFT_DIALOG_TEXTS = ["是否保存草稿", "保存草稿", "存草稿", "不保存"]
SAVE_DRAFT_CONFIRM_TEXTS = ["保存草稿", "存草稿"]
ME_PAGE_TEXTS = ["编辑资料", "设置", "我的活动", "草稿箱", "我的发布"]


def save_note_draft(
    driver: WebDriver,
    title: str,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 30,
) -> None:
    open_note_draft_editor(driver, ios_config=ios_config, timeout=timeout)
    fill_note_draft_title(driver, title, timeout=timeout)
    go_back_from_note_editor(driver, timeout=10)
    wait_for_save_draft_dialog(driver, timeout=10)
    choose_save_draft(driver, timeout=10)
    open_me_page(driver, timeout=12)


def open_note_draft_editor(
    driver: WebDriver,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 30,
) -> None:
    message_detail.open_message_note_publisher(driver, ios_config=ios_config, timeout=timeout)


def fill_note_draft_title(driver: WebDriver, title: str, timeout: int = 20) -> None:
    message_detail.wait_for_message_note_form(driver, timeout=timeout)
    message_detail._fill_note_title(driver, title)
    message_detail._hide_keyboard(driver)


def go_back_from_note_editor(driver: WebDriver, timeout: int = 10) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if save_draft_dialog_is_visible(_safe_page_source(driver)):
            return
        if _tap_note_editor_back(driver):
            if _wait_until(lambda: save_draft_dialog_is_visible(_safe_page_source(driver)), timeout=2):
                return
        time.sleep(0.2)
    raise AssertionError("Save draft dialog did not appear after leaving the note editor")


def wait_for_save_draft_dialog(driver: WebDriver, timeout: int = 10) -> None:
    if not _wait_until(lambda: save_draft_dialog_is_visible(_safe_page_source(driver)), timeout=timeout):
        raise AssertionError("Save draft dialog did not appear")


def choose_save_draft(driver: WebDriver, timeout: int = 10) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if not save_draft_dialog_is_visible(_safe_page_source(driver)):
            return
        for text in SAVE_DRAFT_CONFIRM_TEXTS:
            if tap_text_if_present(driver, text, timeout=1):
                if _wait_until(lambda: not save_draft_dialog_is_visible(_safe_page_source(driver)), timeout=3):
                    return
        time.sleep(0.2)
    raise AssertionError("Unable to confirm save draft from the dialog")


def open_me_page(driver: WebDriver, timeout: int = 12) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if me_page_is_visible(_safe_page_source(driver)):
            return
        if _tap_me_tab(driver):
            if _wait_until(lambda: me_page_is_visible(_safe_page_source(driver)), timeout=3):
                return
        time.sleep(0.2)
    raise AssertionError("Unable to enter the Me page after saving draft")


def save_draft_dialog_is_visible(page_source: str) -> bool:
    return all(token in page_source for token in ["保存草稿", "不保存"]) or "是否保存草稿" in page_source


def me_page_is_visible(page_source: str) -> bool:
    if "手机号登录" in page_source or "密码登录" in page_source:
        return False
    return "我的" in page_source and any(token in page_source for token in ME_PAGE_TEXTS)


def _tap_note_editor_back(driver: WebDriver) -> bool:
    for accessibility_id in ["nav-back", "back", "publish-back", "note-back"]:
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    for text in ["返回", "取消"]:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    rect = _note_editor_back_rect(_safe_page_source(driver))
    if rect is not None and _click_note_editor_back_rect_element(driver, rect):
        return True
    if rect is not None and _tap_rect_center(driver, rect):
        return True
    if _tap_note_editor_back_points(driver):
        return True
    if _back_with_driver_api(driver):
        return True
    return False


def _back_with_driver_api(driver: WebDriver) -> bool:
    try:
        driver.back()
        return True
    except WebDriverException:
        return False


def _tap_note_editor_back_points(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        points = [
            (int(rect["width"] * 0.08), int(rect["height"] * 0.11)),
            (32, 95),
            (36, 90),
            (24, 95),
            (45, 95),
        ]
        for x, y in points:
            if _tap_point(driver, x, y):
                return True
        return False
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_me_tab(driver: WebDriver) -> bool:
    if tap_accessibility_id_or_text_if_present(driver, "bottom-nav-me", "我的", timeout=2):
        return True
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.88),
                "y": int(rect["height"] * 0.93),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _wait_until(condition, *, timeout: int | float) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if condition():
            return True
        time.sleep(0.2)
    return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""


def _note_editor_back_rect(page_source: str) -> tuple[int, int, int, int] | None:
    candidates: list[tuple[int, int, int, int]] = []
    for tag in re.findall(r"<XCUIElementTypeOther\b[^>]*>", page_source):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', tag))
        try:
            x = int(float(attrs.get("x", "0")))
            y = int(float(attrs.get("y", "0")))
            width = int(float(attrs.get("width", "0")))
            height = int(float(attrs.get("height", "0")))
        except ValueError:
            continue
        if 8 <= x <= 24 and 60 <= y <= 90 and 28 <= width <= 60 and 28 <= height <= 60:
            candidates.append((x, y, width, height))
    return sorted(candidates, key=lambda item: (item[1], item[0]))[0] if candidates else None


def _tap_rect_center(driver: WebDriver, rect: tuple[int, int, int, int]) -> bool:
    x, y, width, height = rect
    return _tap_point(driver, x + max(1, width // 2), y + max(1, height // 2))


def _click_note_editor_back_rect_element(driver: WebDriver, rect: tuple[int, int, int, int]) -> bool:
    x, y, width, height = rect
    xpath = (
        f'//XCUIElementTypeOther[@x="{x}" and @y="{y}" '
        f'and @width="{width}" and @height="{height}"]'
    )
    try:
        driver.find_element(AppiumBy.XPATH, xpath).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_point(driver: WebDriver, x: int, y: int) -> bool:
    try:
        driver.execute_script(
            "mobile: tap",
            {
                "x": x,
                "y": y,
            },
        )
        return True
    except WebDriverException:
        return False
