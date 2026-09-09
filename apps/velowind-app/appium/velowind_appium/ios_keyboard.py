"""Dismiss iOS keyboards without retrying absent English keys five times."""

from selenium.common.exceptions import WebDriverException


def hide_ios_keyboard_if_possible(driver) -> bool:
    try:
        if not driver.is_keyboard_shown():
            return True
        driver.execute_script("mobile: hideKeyboard", {"keys": ["完成", "Done", "隐藏键盘", "Hide keyboard"]})
        return not driver.is_keyboard_shown()
    except (AttributeError, WebDriverException):
        return False
