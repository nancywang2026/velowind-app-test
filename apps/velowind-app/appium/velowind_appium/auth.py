from __future__ import annotations

import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import tap_accessibility_id_or_text_if_present, tap_text_if_present
from velowind_appium.config import IosAppiumConfig


def login_required_from_page_source(page_source: str) -> bool:
    phone_login_tokens = ["手机号登录", "请输入手机号", "登录"]
    password_login_tokens = ["密码登录", "请输入手机号和密码完成登录", "登录"]
    return all(token in page_source for token in phone_login_tokens) or all(
        token in page_source for token in password_login_tokens
    )


def ensure_logged_in_if_needed(driver: WebDriver, config: IosAppiumConfig) -> bool:
    if not config.login_username or not config.login_password:
        return False

    if not login_required_from_page_source(_safe_page_source(driver)):
        tap_accessibility_id_or_text_if_present(driver, "bottom-nav-me", "我的", timeout=3)
        time.sleep(1)

    if not login_required_from_page_source(_safe_page_source(driver)):
        tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=3)
        return False

    _perform_password_login(driver, config.login_username, config.login_password)
    tap_accessibility_id_or_text_if_present(driver, "bottom-nav-home", "首页", timeout=5)
    return True


def _perform_password_login(driver: WebDriver, username: str, password: str) -> None:
    _dismiss_login_agreement_sheet(driver)
    _open_password_login_form(driver)

    phone_input = _find_phone_input(driver)
    phone_input.click()
    phone_input.clear()
    phone_input.send_keys(username)

    password_input = _find_password_input(driver)
    password_input.click()
    try:
        password_input.clear()
    except WebDriverException:
        pass
    password_input.send_keys(password)

    _tap_agreement(driver)
    if not _tap_login_submit(driver):
        raise AssertionError("Unable to submit the login form")
    _save_password_if_prompted(driver)

    end_at = time.monotonic() + 20
    last_submit_at = time.monotonic()
    while time.monotonic() < end_at:
        _dismiss_login_agreement_sheet(driver)
        _save_password_if_prompted(driver)
        current_source = _safe_page_source(driver)
        if not login_required_from_page_source(current_source):
            return
        if time.monotonic() - last_submit_at >= 2:
            _tap_agreement(driver)
            _tap_login_submit(driver)
            _save_password_if_prompted(driver)
            last_submit_at = time.monotonic()
        time.sleep(0.5)

    raise AssertionError("Login page remained visible after submitting credentials")


def _find_phone_input(driver: WebDriver):
    if _is_android(driver):
        return driver.find_element(AppiumBy.XPATH, "(//android.widget.EditText)[1]")
    return driver.find_element(AppiumBy.XPATH, "//XCUIElementTypeTextField[1]")


def _find_password_input(driver: WebDriver):
    end_at = time.monotonic() + 10
    retried_password_tab = False
    while time.monotonic() < end_at:
        xpaths = (
            ['(//android.widget.EditText[@password="true"])[1]', "(//android.widget.EditText)[2]"]
            if _is_android(driver)
            else ["//XCUIElementTypeSecureTextField[1]", "(//XCUIElementTypeTextField)[2]"]
        )
        for xpath in xpaths:
            try:
                return driver.find_element(AppiumBy.XPATH, xpath)
            except NoSuchElementException:
                continue
        if not retried_password_tab:
            retried_password_tab = True
            _open_password_login_form(driver)
        time.sleep(0.3)
    raise AssertionError("Unable to locate the password input on the login page")


def _open_password_login_form(driver: WebDriver) -> None:
    baseline = _safe_page_source(driver)
    if _has_password_input(driver) and "请输入手机号和密码完成登录" in baseline:
        return

    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        if tap_text_if_present(driver, "密码登录", timeout=1):
            _tap_agreement(driver)
            time.sleep(1)
            if _password_form_visible(driver, baseline):
                return

    for xpath in [
        "//XCUIElementTypeStaticText[@name='密码登录']",
        "//XCUIElementTypeStaticText[@label='密码登录']",
        "(//*[@name='密码登录'])[1]",
        "(//*[@label='密码登录'])[1]",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            _tap_agreement(driver)
            time.sleep(1)
            if _password_form_visible(driver, baseline):
                return
        except NoSuchElementException:
            continue

    raise AssertionError("Unable to switch the login page into password-login mode")


def _password_form_visible(driver: WebDriver, baseline: str) -> bool:
    if _has_password_input(driver):
        return True
    current = _safe_page_source(driver)
    return (
        "请输入手机号和密码完成登录" in current
        or "登录" in current and "请输入手机号" in current and current != baseline
    )


def _has_password_input(driver: WebDriver) -> bool:
    xpaths = (
        ['(//android.widget.EditText[@password="true"])[1]', "(//android.widget.EditText)[2]"]
        if _is_android(driver)
        else ["//XCUIElementTypeSecureTextField[1]", "(//XCUIElementTypeTextField)[2]"]
    )
    for xpath in xpaths:
        try:
            driver.find_element(AppiumBy.XPATH, xpath)
            return True
        except NoSuchElementException:
            continue
    return False


def _is_android(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    return str(capabilities.get("platformName", "")).lower() == "android"


def _tap_agreement(driver: WebDriver) -> None:
    for accessibility_id in [
        "login-agreement-checkbox",
        "login-agreement",
        "agreement-checkbox",
    ]:
        try:
            driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id).click()
            return
        except (NoSuchElementException, WebDriverException):
            continue

    for xpath in [
        '//XCUIElementTypeOther[@name="我已阅读并同意《寻风集用户协议》《隐私政策》"]/XCUIElementTypeOther[1]',
        '(//XCUIElementTypeOther[@name="我已阅读并同意《寻风集用户协议》《隐私政策》"])[1]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            _tap_element_center(driver, element)
            return
        except (NoSuchElementException, WebDriverException):
            continue

    predicate = (
        '(name CONTAINS "已阅读" AND name CONTAINS "同意") OR '
        '(label CONTAINS "已阅读" AND label CONTAINS "同意") OR '
        '(value CONTAINS "已阅读" AND value CONTAINS "同意")'
    )
    try:
        element = driver.find_element(AppiumBy.IOS_PREDICATE, predicate)
        _tap_element_leading_checkbox(driver, element)
    except (NoSuchElementException, WebDriverException):
        return


def _tap_element_center(driver: WebDriver, element) -> None:
    rect = element.rect
    driver.execute_script(
        "mobile: tap",
        {
            "x": rect["x"] + rect["width"] / 2,
            "y": rect["y"] + rect["height"] / 2,
        },
    )
    time.sleep(0.2)


def _tap_element_leading_checkbox(driver: WebDriver, element) -> None:
    rect = element.rect
    driver.execute_script(
        "mobile: tap",
        {
            "x": rect["x"] + min(12, rect["width"] / 2),
            "y": rect["y"] + rect["height"] / 2,
        },
    )
    time.sleep(0.2)


def _dismiss_login_agreement_sheet(driver: WebDriver) -> None:
    tap_text_if_present(driver, "同意并继续", timeout=1)
    tap_text_if_present(driver, "同意", timeout=1)


def _save_password_if_prompted(driver: WebDriver) -> None:
    tap_text_if_present(driver, "保存", timeout=2)


def _tap_login_submit(driver: WebDriver) -> bool:
    if _is_android(driver):
        return tap_text_if_present(driver, "登录", timeout=1) or tap_text_if_present(
            driver,
            "验证并登录",
            timeout=1,
        )

    for xpath in [
        '(//XCUIElementTypeOther[@name="验证并登录"])[1]',
        '(//XCUIElementTypeOther[@name="登录"])[1]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except NoSuchElementException:
            continue

    predicate = (
        'name IN {"验证并登录", "登录"} OR '
        'label IN {"验证并登录", "登录"} OR '
        'value IN {"验证并登录", "登录"}'
    )
    try:
        driver.find_element(AppiumBy.IOS_PREDICATE, predicate).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""
