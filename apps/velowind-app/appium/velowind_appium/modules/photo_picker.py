from __future__ import annotations

from contextlib import contextmanager
import os
import time
from typing import Callable

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import swipe_vertical, tap_text_if_present


RetrySheetOption = Callable[[WebDriver], bool]


def choose_photo_from_library(
    driver: WebDriver,
    *,
    album_name: str | None = None,
    select_all_from_album: bool = True,
    prefer_retry_sheet_option_first: bool = False,
    retry_sheet_option: RetrySheetOption | None = None,
) -> bool:
    visible = False
    if prefer_retry_sheet_option_first and retry_sheet_option is not None:
        with _photo_picker_profile("retry-sheet-option-initial"):
            retry_sheet_option(driver)
        with _photo_picker_profile("dismiss-alerts-initial"):
            dismiss_photo_permission_alerts(driver)
        with _photo_picker_profile("wait-library-visible-initial"):
            visible = photo_library_visible(driver, timeout=3)

    if not visible:
        with _photo_picker_profile("choose-source"):
            source_chosen = choose_photo_library_source(driver)
        if not source_chosen:
            return False

        with _photo_picker_profile("dismiss-alerts-initial"):
            dismiss_photo_permission_alerts(driver)

        with _photo_picker_profile("wait-library-visible-initial"):
            visible = photo_library_visible(driver, timeout=5)
        if not visible and retry_sheet_option is not None:
            with _photo_picker_profile("retry-sheet-option"):
                retry_sheet_option(driver)
            with _photo_picker_profile("dismiss-alerts-retry"):
                dismiss_photo_permission_alerts(driver)
            with _photo_picker_profile("wait-library-visible-retry"):
                visible = photo_library_visible(driver, timeout=5)

    if not visible:
        return False

    with _photo_picker_profile("choose-local-photo-primary"):
        primary_chosen = choose_local_photo(driver, album_name=album_name, select_all_from_album=select_all_from_album)
    if primary_chosen:
        return True

    with _photo_picker_profile("choose-first-option-fallback"):
        fallback_opened = _choose_first_option(driver, preferred_texts=["最近项目", "照片图库", "照片", "所有照片"])
    if not fallback_opened:
        return False
    with _photo_picker_profile("choose-local-photo-fallback"):
        return choose_local_photo(
            driver,
            album_name=album_name,
            select_all_from_album=select_all_from_album,
        )


def dismiss_photo_permission_alerts(driver: WebDriver) -> None:
    page_source = _safe_page_source(driver)
    alert_texts = ["允许访问所有照片", "允许", "好"]
    if page_source and not any(text in page_source for text in alert_texts):
        return
    for text in alert_texts:
        tap_text_if_present(driver, text, timeout=0.5)


def choose_photo_library_source(driver: WebDriver) -> bool:
    source_texts = ["从手机相册选择", "手机相册", "从相册选择", "相册"]
    if _tap_texts_by_predicate(driver, source_texts):
        return True
    if _tap_photo_source_option(driver, source_texts):
        return True
    for text in source_texts:
        if tap_text_if_present(driver, text, timeout=0.5):
            return True
    return _tap_photo_library_sheet_option(driver)


def photo_library_visible(driver: WebDriver, timeout: int = 5) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        for xpath in [
            '//*[@name="BackButton" or @label="返回"]',
            "(//XCUIElementTypeCell)[1]",
            "(//XCUIElementTypeImage)[1]",
        ]:
            try:
                driver.find_element(AppiumBy.XPATH, xpath)
                return True
            except (NoSuchElementException, WebDriverException, AttributeError):
                continue
        page_source = _safe_page_source(driver)
        if any(text in page_source for text in ["最近项目", "照片图库", "所有照片", "选择项目", "选择照片"]):
            return True
        time.sleep(0.2)
    return False


def choose_local_photo(
    driver: WebDriver,
    *,
    picture_index: int = 1,
    album_name: str | None = None,
    select_all_from_album: bool = True,
) -> bool:
    normalized_index = max(1, picture_index)
    if album_name:
        with _photo_picker_profile("open-photo-album"):
            album_opened = open_photo_album(driver, album_name)
        if not album_opened:
            return False
    if album_name:
        if select_all_from_album:
            with _photo_picker_profile("select-all-album-photos"):
                all_selected = select_all_album_photos(driver)
            if not all_selected:
                return False
        else:
            with _photo_picker_profile("tap-photo-grid-candidate"):
                candidate_tapped = tap_photo_grid_candidate(driver, normalized_index)
            if not candidate_tapped:
                return False
        with _photo_picker_profile("confirm-system-selection"):
            return confirm_system_photo_picker_selection(driver)
    with _photo_picker_profile("tap-photo-grid-candidate"):
        candidate_tapped = tap_photo_grid_candidate(driver, normalized_index)
    if candidate_tapped:
        with _photo_picker_profile("confirm-note-cropper"):
            if confirm_note_image_cropper(driver):
                return True
        with _photo_picker_profile("confirm-system-selection"):
            return confirm_system_photo_picker_selection(driver)
    return False


def open_photo_album(driver: WebDriver, album_name: str) -> bool:
    current_title = photo_album_title(driver)
    if current_title == album_name:
        return True
    if current_title not in {None, "选择最多9张照片。"}:
        if not _tap_photo_picker_back(driver):
            return False
        time.sleep(0.3)
        current_title = photo_album_title(driver)
    if not switch_photo_picker_to_collections(driver, current_title=current_title):
        return False
    for _ in range(4):
        if _tap_named_element_center(driver, album_name):
            if _wait_until(lambda: photo_album_title(driver) == album_name, timeout=2):
                return True
        try:
            swipe_vertical(driver, direction="up")
        except WebDriverException:
            pass
        time.sleep(0.3)
    return False


def tap_photo_grid_candidate(driver: WebDriver, picture_index: int) -> bool:
    candidates = find_photo_grid_candidates(driver)
    if not candidates:
        return False
    target_index = min(max(1, picture_index), len(candidates)) - 1
    rect = _rect_snapshot(candidates[target_index])
    if rect is None:
        return False
    return _tap_rect_center(driver, rect)


def select_all_album_photos(driver: WebDriver) -> bool:
    if _tap_all_photo_grid_selection_badges(driver):
        return True
    return _tap_all_photo_grid_candidates(driver)


def _tap_all_photo_grid_selection_badges(driver: WebDriver) -> bool:
    badges = find_photo_grid_selection_badges(driver)
    rects = [rect for rect in (_rect_snapshot(badge) for badge in badges) if rect is not None]
    tapped_any = False
    for rect in rects:
        if _tap_rect_center(driver, rect):
            tapped_any = True
            time.sleep(0.2)
    return tapped_any


def find_photo_grid_selection_badges(driver: WebDriver) -> list:
    badges = []
    seen: set[tuple[float, float, float, float]] = set()
    for xpath in [
        "//XCUIElementTypeOther",
        "//XCUIElementTypeButton",
        "//XCUIElementTypeImage",
    ]:
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except (AttributeError, WebDriverException):
            continue
        for element in elements:
            rect = getattr(element, "rect", {}) or {}
            x = float(rect.get("x", 0) or 0)
            y = float(rect.get("y", 0) or 0)
            width = float(rect.get("width", 0) or 0)
            height = float(rect.get("height", 0) or 0)
            if not (12 <= width <= 24 and 12 <= height <= 24):
                continue
            if not (90 <= x <= 390 and 120 <= y <= 220):
                continue
            key = (x, y, width, height)
            if key in seen:
                continue
            seen.add(key)
            badges.append(element)
    badges.sort(
        key=lambda element: (
            ((getattr(element, "rect", {}) or {}).get("y", 0)),
            ((getattr(element, "rect", {}) or {}).get("x", 0)),
        )
    )
    return badges


def _tap_all_photo_grid_candidates(driver: WebDriver) -> bool:
    candidates = find_photo_grid_candidates(driver)
    rects = [rect for rect in (_rect_snapshot(candidate) for candidate in candidates) if rect is not None]
    tapped_any = False
    for rect in rects:
        if _tap_rect_center(driver, rect):
            tapped_any = True
            time.sleep(0.2)
    return tapped_any


def find_photo_grid_candidates(driver: WebDriver) -> list:
    candidates = []
    seen: set[tuple[float, float, float, float]] = set()
    for xpath in [
        "//XCUIElementTypeImage[@name='PXGGridLayout-Info']",
        "//XCUIElementTypeImage[contains(@label, 'Screenshot')]",
        "//XCUIElementTypeImage",
    ]:
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except (AttributeError, WebDriverException):
            continue
        for element in elements:
            rect = getattr(element, "rect", {}) or {}
            x = float(rect.get("x", 0) or 0)
            y = float(rect.get("y", 0) or 0)
            width = float(rect.get("width", 0) or 0)
            height = float(rect.get("height", 0) or 0)
            if width < 80 or height < 80:
                continue
            if y < 135:
                continue
            key = (x, y, width, height)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(element)
    candidates.sort(key=lambda element: (((getattr(element, "rect", {}) or {}).get("y", 0)), ((getattr(element, "rect", {}) or {}).get("x", 0))))
    return candidates


def photo_album_title(driver: WebDriver) -> str | None:
    for xpath in [
        "//XCUIElementTypeNavigationBar/XCUIElementTypeStaticText[1]",
        "(//XCUIElementTypeNavigationBar//*[self::XCUIElementTypeStaticText or self::XCUIElementTypeOther][@name])[1]",
    ]:
        try:
            text = driver.find_element(AppiumBy.XPATH, xpath).get_attribute("name")
            normalized = (text or "").strip()
            if normalized and normalized not in {"照片"}:
                return normalized
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return None


def switch_photo_picker_to_collections(driver: WebDriver, *, current_title: str | None = None) -> bool:
    if current_title is None:
        current_title = photo_album_title(driver)
    if current_title == "精选集":
        return True
    if not _tap_text_or_contains(driver, "精选集"):
        return False
    time.sleep(0.5)
    return True


def _tap_photo_picker_back(driver: WebDriver) -> bool:
    try:
        element = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "BackButton")
        try:
            element.click()
            return True
        except WebDriverException:
            if _tap_element_center(driver, element):
                return True
    except (NoSuchElementException, WebDriverException, AttributeError):
        pass
    for point in [
        {"x": 24, "y": 108},
        {"x": 32, "y": 108},
        {"x": 40, "y": 108},
        {"x": 38, "y": 110},
    ]:
        try:
            driver.execute_script("mobile: tap", point)
            return True
        except WebDriverException:
            continue
    try:
        driver.back()
        return True
    except (AttributeError, WebDriverException):
        return False


def _photo_picker_collections_visible(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    return any(text in page_source for text in ["精选集", "最近项目", "照片图库", "所有照片", "选择项目"])


def confirm_note_image_cropper(driver: WebDriver, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _cropper_visible(page_source):
            if _tap_cropper_confirm_button(driver) and _wait_until(
                lambda: not _cropper_visible(_safe_page_source(driver)),
                timeout=5,
            ):
                try:
                    setattr(driver, "_cropper_confirmed_once", True)
                except Exception:
                    pass
                return True
        time.sleep(0.2)
    return False


def confirm_system_photo_picker_selection(driver: WebDriver, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if _tap_photo_picker_done_button(driver) and _wait_until(
            lambda: _photo_picker_transition_completed(driver),
            timeout=2,
        ):
            return True
        time.sleep(0.2)
    return False


def _photo_picker_transition_completed(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if _cropper_visible(page_source):
        if getattr(driver, "_cropper_confirmed_once", False):
            return True
        return confirm_note_image_cropper(driver, timeout=5)
    return not any(text in page_source for text in ["选择最多9张照片。", 'name="Add" label="完成"'])


def _tap_photo_source_option(driver: WebDriver, texts: list[str]) -> bool:
    for text in texts:
        for xpath in [
            f'//*[@name="{text}" or @label="{text}" or @value="{text}"]',
            f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
        ]:
            try:
                element = driver.find_element(AppiumBy.XPATH, xpath)
                rect = element.rect
                try:
                    size = driver.get_window_size()
                    x = size["width"] / 2
                except WebDriverException:
                    x = rect["x"] + rect["width"] / 2
                driver.execute_script(
                    "mobile: tap",
                    {
                        "x": x,
                        "y": rect["y"] + rect["height"] / 2,
                    },
                )
                return True
            except (NoSuchElementException, WebDriverException):
                continue
    return False


def _tap_photo_library_sheet_option(driver: WebDriver) -> bool:
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.5,
                "y": size["height"] * 0.90,
            },
        )
        return True
    except WebDriverException:
        return False


def _tap_cropper_confirm_button(driver: WebDriver) -> bool:
    try:
        size = driver.get_window_size()
    except (AttributeError, WebDriverException):
        size = None

    for xpath in [
        '//*[@name="确认裁剪" or @label="确认裁剪" or @value="确认裁剪"]',
        '//*[contains(@name, "确认裁剪") or contains(@label, "确认裁剪") or contains(@value, "确认裁剪")]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            rect = element.rect
            driver.execute_script(
                "mobile: tap",
                {
                    "x": rect["x"] + rect["width"] / 2,
                    "y": rect["y"] + rect["height"] / 2,
                },
            )
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    if size is not None:
        try:
            driver.execute_script(
                "mobile: tap",
                {
                    "x": size["width"] * 0.74,
                    "y": size["height"] * 0.91,
                },
            )
            return True
        except WebDriverException:
            pass
    return False


def _choose_first_option(driver: WebDriver, preferred_texts: list[str]) -> bool:
    for text in preferred_texts:
        if tap_text_if_present(driver, text, timeout=2):
            return True

    for xpath in [
        "(//XCUIElementTypeCell)[1]",
        "(//XCUIElementTypeButton)[1]",
        "(//XCUIElementTypeStaticText)[1]",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            tap_text_if_present(driver, "确定", timeout=1)
            tap_text_if_present(driver, "完成", timeout=1)
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_named_element_center(driver: WebDriver, text: str) -> bool:
    for xpath in [
        f'//*[@name="{text}" or @label="{text}" or @value="{text}"]',
        f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            rect = element.rect
            driver.execute_script(
                "mobile: tap",
                {
                    "x": rect["x"] + rect["width"] / 2,
                    "y": rect["y"] + rect["height"] / 2,
                },
            )
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_text_or_contains(driver: WebDriver, text: str) -> bool:
    if tap_text_if_present(driver, text, timeout=1):
        return True
    for xpath in [
        f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_texts_by_predicate(driver: WebDriver, texts: list[str]) -> bool:
    escaped_texts = [text.replace("\\", "\\\\").replace('"', '\\"') for text in texts]
    quoted = ", ".join(f'"{text}"' for text in escaped_texts)
    predicate = f"name IN {{{quoted}}} OR label IN {{{quoted}}} OR value IN {{{quoted}}}"
    try:
        driver.find_element(AppiumBy.IOS_PREDICATE, predicate).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_accessibility_id_now(driver: WebDriver, accessibility_id: str) -> bool:
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_photo_picker_done_button(driver: WebDriver) -> bool:
    if _tap_accessibility_id_now(driver, "Add"):
        return True
    if _tap_texts_by_predicate(driver, ["完成", "添加"]):
        return True

    for xpath in [
        '//*[@name="Add" and @enabled="true" and @visible="true"]',
        '//*[@label="完成" and @enabled="true" and @visible="true"]',
        '//*[@label="添加" and @enabled="true" and @visible="true"]',
        '//*[@name="Add" and @enabled="true"]',
        '//*[@label="完成" and @enabled="true"]',
        '//*[@label="添加" and @enabled="true"]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            if _tap_element_center(driver, element):
                return True
            element.click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue

    for text in ["完成", "添加"]:
        if _tap_text_or_contains(driver, text):
            return True
    return False


def _rect_snapshot(element) -> dict[str, float] | None:
    try:
        rect = getattr(element, "rect", {}) or {}
    except WebDriverException:
        return None
    width = float(rect.get("width", 0) or 0)
    height = float(rect.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        return None
    return {
        "x": float(rect.get("x", 0) or 0),
        "y": float(rect.get("y", 0) or 0),
        "width": width,
        "height": height,
    }


def _tap_rect_center(driver: WebDriver, rect: dict[str, float]) -> bool:
    try:
        driver.execute_script(
            "mobile: tap",
            {
                "x": rect["x"] + rect["width"] / 2,
                "y": rect["y"] + rect["height"] / 2,
            },
        )
        return True
    except WebDriverException:
        return False


def _tap_element_center(driver: WebDriver, element) -> bool:
    rect = _rect_snapshot(element)
    if rect is None:
        return False
    return _tap_rect_center(driver, rect)


def _cropper_visible(page_source: str) -> bool:
    return any(pattern in page_source for pattern in ["确认裁剪", "裁剪"])


def _wait_until(predicate, timeout: int) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""


def _photo_picker_profile_enabled() -> bool:
    return os.getenv("VW_ACTIVITY_PROFILE", "").strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def _photo_picker_profile(label: str):
    started_at = time.monotonic()
    yield
    if _photo_picker_profile_enabled():
        elapsed = time.monotonic() - started_at
        print(f"[photo-picker-profile] {label}: {elapsed:.2f}s", flush=True)
