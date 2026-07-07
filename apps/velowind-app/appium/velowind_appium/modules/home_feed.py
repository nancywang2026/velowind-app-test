from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from velowind_appium.actions import (
    swipe_vertical,
    tap_if_present,
    wait_for_any_accessibility_id_or_text,
)
from velowind_appium.modules.message_detail import message_detail_is_visible


HOME_READY_IDS = [
    "home-page-title",
    "home-activity-discovery-browser",
    "post-home-feed-category-pager",
]
HOME_READY_TEXTS = ["首页", "全国", "推荐"]
FIRST_MESSAGE_IDS = [
    "post-home-feed-item-0",
    "post-home-feed-card-0",
    "home-feed-item-0",
]
FIRST_MESSAGE_XPATHS = [
    "(//XCUIElementTypeCollectionView//XCUIElementTypeCell)[1]",
    "(//XCUIElementTypeCollectionView//XCUIElementTypeButton)[1]",
    "(//XCUIElementTypeTable//XCUIElementTypeCell)[1]",
    "(//XCUIElementTypeTable//XCUIElementTypeButton)[1]",
]


def wait_for_home_feed(driver: WebDriver, timeout: int = 60) -> str | None:
    return wait_for_any_accessibility_id_or_text(
        driver,
        HOME_READY_IDS,
        HOME_READY_TEXTS,
        timeout=timeout,
    )


def open_first_home_message(driver: WebDriver, max_swipes: int = 3) -> None:
    wait_for_home_feed(driver, timeout=60)
    if message_detail_is_visible(driver):
        return

    for _ in range(max_swipes + 1):
        if message_detail_is_visible(driver):
            return
        if _tap_first_message(driver):
            for _ in range(20):
                if message_detail_is_visible(driver):
                    return
        if message_detail_is_visible(driver):
            return
        if not _tap_first_visible_card(driver):
            swipe_vertical(driver, direction="up")

    if message_detail_is_visible(driver):
        return
    raise AssertionError("Unable to detect the first message detail after entering from the home feed")


def _tap_first_message(driver: WebDriver) -> bool:
    for accessibility_id in FIRST_MESSAGE_IDS:
        if tap_if_present(driver, accessibility_id, timeout=2):
            return True

    for xpath in FIRST_MESSAGE_XPATHS:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            element.click()
            return True
        except (NoSuchElementException, TimeoutException, WebDriverException):
            continue
    return False


def _tap_first_visible_card(driver: WebDriver) -> bool:
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.25,
                "y": size["height"] * 0.38,
            },
        )
        return True
    except WebDriverException:
        return False
