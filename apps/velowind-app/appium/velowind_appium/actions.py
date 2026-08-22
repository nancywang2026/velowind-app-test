from __future__ import annotations

import json
from pathlib import Path
import re
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from .artifacts import timestamped_path


ACCESSIBILITY_ID_LOCATOR = AppiumBy.ACCESSIBILITY_ID
POLL_INTERVAL_SECONDS = 0.2


@dataclass(frozen=True)
class LocatorCandidate:
    kind: str
    value: str
    label: str | None = None

    def describe(self) -> str:
        return self.label or f"{self.kind}={self.value}"


class LocatorTimeoutError(TimeoutException):
    """Raised when a required semantic locator is not found before its deadline."""


def accessibility_id(value: str, *, label: str | None = None) -> LocatorCandidate:
    return LocatorCandidate("accessibility_id", value, label)


def text(value: str, *, label: str | None = None) -> LocatorCandidate:
    return LocatorCandidate("text", value, label)


def ios_predicate(value: str, *, label: str | None = None) -> LocatorCandidate:
    return LocatorCandidate("ios_predicate", value, label)


def xpath(value: str, *, label: str | None = None) -> LocatorCandidate:
    return LocatorCandidate("xpath", value, label)


def _ios_predicate_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _text_locator(driver: WebDriver, text: str) -> tuple[str, str]:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        quoted_text = json.dumps(text, ensure_ascii=False)
        return AppiumBy.ANDROID_UIAUTOMATOR, f"new UiSelector().text({quoted_text})"

    quoted_text = _ios_predicate_string(text)
    predicate = f"name == {quoted_text} OR label == {quoted_text} OR value == {quoted_text}"
    return AppiumBy.IOS_PREDICATE, predicate


def _test_id_locator(driver: WebDriver, test_id: str) -> tuple[str, str]:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        escaped = test_id.replace('"', '\\"')
        return AppiumBy.XPATH, f'//*[@resource-id="{escaped}" or @content-desc="{escaped}"]'
    return ACCESSIBILITY_ID_LOCATOR, test_id


def _candidate_locator(driver: WebDriver, candidate: LocatorCandidate) -> tuple[str, str]:
    if candidate.kind == "accessibility_id":
        return _test_id_locator(driver, candidate.value)
    if candidate.kind == "text":
        return _text_locator(driver, candidate.value)
    if candidate.kind == "ios_predicate":
        return AppiumBy.IOS_PREDICATE, candidate.value
    if candidate.kind == "xpath":
        return AppiumBy.XPATH, candidate.value
    raise ValueError(f"Unsupported locator candidate kind: {candidate.kind}")


def _candidate_list(candidates: Iterable[LocatorCandidate]) -> list[LocatorCandidate]:
    normalized = list(candidates)
    if not normalized:
        raise ValueError("At least one locator candidate is required")
    return normalized


def find_first(
    driver: WebDriver,
    candidates: Iterable[LocatorCandidate],
    *,
    logical_name: str = "element",
) -> object | None:
    del logical_name  # Kept in the signature so callers can use the same API as wait_for_first.
    for candidate in _candidate_list(candidates):
        try:
            return driver.find_element(*_candidate_locator(driver, candidate))
        except (NoSuchElementException, StaleElementReferenceException, WebDriverException):
            continue
    return None


def _page_summary(driver: WebDriver, limit: int = 8) -> str:
    try:
        source = driver.page_source or ""
    except WebDriverException:
        return "<page source unavailable>"
    values = re.findall(r'(?:name|label|value|text|resource-id|content-desc)="([^"]+)"', source)
    unique_values = list(dict.fromkeys(value for value in values if value))
    return " | ".join(unique_values[:limit]) or "<empty page>"


def _locator_timeout_message(
    driver: WebDriver,
    candidates: list[LocatorCandidate],
    *,
    logical_name: str,
    elapsed: float,
    attempted: list[str],
) -> str:
    rendered = ", ".join(candidate.describe() for candidate in candidates)
    attempts = ", ".join(attempted) or "none"
    return (
        f"Unable to locate {logical_name} after {elapsed:.2f}s. "
        f"Candidates: {rendered}. Attempted: {attempts}. "
        f"Page summary: {_page_summary(driver)}"
    )


def wait_for_first(
    driver: WebDriver,
    candidates: Iterable[LocatorCandidate],
    *,
    logical_name: str = "element",
    timeout: float = 20,
    required: bool = True,
) -> object | None:
    normalized = _candidate_list(candidates)
    started_at = time.monotonic()
    deadline = started_at + max(0.0, float(timeout))
    attempted: list[str] = []
    first_poll = True

    while first_poll or time.monotonic() < deadline:
        first_poll = False
        for candidate in normalized:
            attempted.append(candidate.describe())
            try:
                return driver.find_element(*_candidate_locator(driver, candidate))
            except (NoSuchElementException, StaleElementReferenceException, WebDriverException):
                continue
        if time.monotonic() >= deadline:
            break
        time.sleep(min(POLL_INTERVAL_SECONDS, max(0.0, deadline - time.monotonic())))

    if not required:
        return None
    raise LocatorTimeoutError(
        _locator_timeout_message(
            driver,
            normalized,
            logical_name=logical_name,
            elapsed=time.monotonic() - started_at,
            attempted=attempted,
        )
    )


def tap_first(
    driver: WebDriver,
    candidates: Iterable[LocatorCandidate],
    *,
    logical_name: str = "element",
    timeout: float = 2,
    required: bool = True,
) -> bool:
    element = wait_for_first(
        driver,
        candidates,
        logical_name=logical_name,
        timeout=timeout,
        required=required,
    )
    if element is None:
        return False
    element.click()
    return True


def page_source_contains_any(page_source: str, texts: Iterable[str]) -> Optional[str]:
    for text in texts:
        if text in page_source:
            return text
    return None


def find_visible_text_if_present(driver: WebDriver, texts: Iterable[str]) -> Optional[str]:
    for text in texts:
        locator = _text_locator(driver, text)
        try:
            driver.find_element(*locator)
            return text
        except (NoSuchElementException, WebDriverException):
            continue
    return None


def wait_for_accessibility_id(driver: WebDriver, accessibility_id: str, timeout: int = 20):
    return WebDriverWait(driver, timeout).until(
        ec.presence_of_element_located(_test_id_locator(driver, accessibility_id))
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
                driver.find_element(*_test_id_locator(driver, accessibility_id))
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
                driver.find_element(*_test_id_locator(driver, accessibility_id))
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
    return tap_first(
        driver,
        [LocatorCandidate("accessibility_id", accessibility_id)],
        logical_name=f"accessibility id {accessibility_id}",
        timeout=timeout,
        required=False,
    )


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
    return tap_first(
        driver,
        [LocatorCandidate("text", text)],
        logical_name=f"text {text}",
        timeout=timeout,
        required=False,
    )


def enter_text_if_present(driver: WebDriver, accessibility_id: str, value: str, timeout: int = 2) -> bool:
    try:
        element = wait_for_accessibility_id(driver, accessibility_id, timeout=timeout)
        element.click()
        try:
            element.clear()
        except WebDriverException:
            pass
        element.send_keys(value)
        return True
    except (NoSuchElementException, TimeoutException, WebDriverException):
        return False


def safe_back(driver: WebDriver) -> None:
    try:
        driver.back()
    except WebDriverException:
        tap_if_present(driver, "login-back", timeout=1)


def swipe_vertical(driver: WebDriver, direction: str = "up") -> None:
    if direction not in {"up", "down"}:
        raise ValueError(f"Unsupported swipe direction: {direction}")

    try:
        driver.execute_script("mobile: swipe", {"direction": direction})
        return
    except WebDriverException:
        pass

    fallback_direction = "down" if direction == "up" else "up"
    driver.execute_script("mobile: scroll", {"direction": fallback_direction})


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
