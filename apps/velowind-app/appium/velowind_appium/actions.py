from pathlib import Path
import time
from typing import Dict, Iterable, Optional

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from .artifacts import timestamped_path


ACCESSIBILITY_ID_LOCATOR = AppiumBy.ACCESSIBILITY_ID
POLL_INTERVAL_SECONDS = 0.2


def _ios_predicate_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def page_source_contains_any(page_source: str, texts: Iterable[str]) -> Optional[str]:
    for text in texts:
        if text in page_source:
            return text
    return None


def find_visible_text_if_present(driver: WebDriver, texts: Iterable[str]) -> Optional[str]:
    for text in texts:
        quoted_text = _ios_predicate_string(text)
        predicate = f"name == {quoted_text} OR label == {quoted_text} OR value == {quoted_text}"
        try:
            driver.find_element(AppiumBy.IOS_PREDICATE, predicate)
            return text
        except (NoSuchElementException, WebDriverException):
            continue
    return None


def wait_for_accessibility_id(driver: WebDriver, accessibility_id: str, timeout: int = 20):
    return WebDriverWait(driver, timeout).until(
        ec.presence_of_element_located((ACCESSIBILITY_ID_LOCATOR, accessibility_id))
    )


def wait_for_any_accessibility_id(
    driver: WebDriver,
    accessibility_ids: Iterable[str],
    timeout: int = 20,
) -> Optional[str]:
    end_at = time.monotonic() + timeout
    last_error: Optional[Exception] = None
    while time.monotonic() < end_at:
        for accessibility_id in accessibility_ids:
            try:
                driver.find_element(ACCESSIBILITY_ID_LOCATOR, accessibility_id)
                return accessibility_id
            except NoSuchElementException as error:
                last_error = error
        time.sleep(POLL_INTERVAL_SECONDS)
    if last_error:
        raise TimeoutException(f"None of the expected ids appeared: {', '.join(accessibility_ids)}")
    return None


def wait_for_any_visible_text(driver: WebDriver, texts: Iterable[str], timeout: int = 20) -> Optional[str]:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        matched_text = find_visible_text_if_present(driver, texts)
        if matched_text:
            return matched_text
        try:
            matched_text = page_source_contains_any(driver.page_source, texts)
        except WebDriverException:
            matched_text = None
        if matched_text:
            return matched_text
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutException(f"None of the expected texts appeared: {', '.join(texts)}")


def wait_for_any_accessibility_id_or_text(
    driver: WebDriver,
    accessibility_ids: Iterable[str],
    texts: Iterable[str],
    timeout: int = 20,
) -> Optional[str]:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        for accessibility_id in accessibility_ids:
            try:
                driver.find_element(ACCESSIBILITY_ID_LOCATOR, accessibility_id)
                return accessibility_id
            except (NoSuchElementException, WebDriverException):
                pass
        matched_text = find_visible_text_if_present(driver, texts)
        if matched_text:
            return matched_text
        try:
            matched_text = page_source_contains_any(driver.page_source, texts)
        except WebDriverException:
            matched_text = None
        if matched_text:
            return matched_text
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutException(
        "None of the expected ids or texts appeared: "
        f"{', '.join(accessibility_ids)} / {', '.join(texts)}"
    )


def tap_if_present(driver: WebDriver, accessibility_id: str, timeout: int = 2) -> bool:
    try:
        wait_for_accessibility_id(driver, accessibility_id, timeout=timeout).click()
        return True
    except (NoSuchElementException, TimeoutException, WebDriverException):
        return False


def tap_accessibility_id_or_text_if_present(
    driver: WebDriver,
    accessibility_id: str,
    text: str,
    timeout: int = 2,
) -> bool:
    return tap_if_present(driver, accessibility_id, timeout=timeout) or tap_text_if_present(
        driver,
        text,
        timeout=timeout,
    )


def tap_text_if_present(driver: WebDriver, text: str, timeout: int = 2) -> bool:
    quoted_text = _ios_predicate_string(text)
    predicate = f"name == {quoted_text} OR label == {quoted_text} OR value == {quoted_text}"
    try:
        WebDriverWait(driver, timeout).until(
            ec.presence_of_element_located((AppiumBy.IOS_PREDICATE, predicate))
        ).click()
        return True
    except (NoSuchElementException, TimeoutException, WebDriverException):
        return False


def safe_back(driver: WebDriver) -> None:
    try:
        driver.back()
    except WebDriverException:
        tap_if_present(driver, "login-back", timeout=1)


def capture_page_screenshot(driver: WebDriver, artifact_dir: Path, label: str) -> Optional[Path]:
    screenshot_path = timestamped_path(artifact_dir, label, "png")
    try:
        driver.save_screenshot(str(screenshot_path))
        return screenshot_path
    except WebDriverException:
        return None


def capture_debug_artifacts(driver: WebDriver, artifact_dir: Path, label: str) -> Dict[str, Path]:
    artifacts: Dict[str, Path] = {}
    screenshot_path = timestamped_path(artifact_dir, label, "png")
    source_path = timestamped_path(artifact_dir, label, "xml")
    try:
        driver.save_screenshot(str(screenshot_path))
        artifacts["PNG"] = screenshot_path
    except WebDriverException:
        pass
    try:
        source_path.write_text(driver.page_source, encoding="utf-8")
        artifacts["XML"] = source_path
    except WebDriverException:
        pass
    return artifacts
