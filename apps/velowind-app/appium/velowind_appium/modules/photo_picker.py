from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import time
from typing import Callable

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import swipe_vertical, tap_text_if_present


RetrySheetOption = Callable[[WebDriver], bool]
DEFAULT_ANDROID_MEDIA_DIR = Path(__file__).resolve().parents[2] / "test-media" / "android"
IOS_CROPPER_VISIBLE_PATTERNS = [
    'name="确认裁剪" label="确认裁剪" enabled="true" visible="true"',
    'name="裁剪图片" label="裁剪图片" enabled="true" visible="true"',
]
ANDROID_CROPPER_VISIBLE_PATTERNS = [
    'resource-id="publish-note-image-picker-cropper-viewport"',
    'resource-id="publish-note-image-picker-cropper-frame"',
    'text="确认裁剪"',
    'text="裁剪图片"',
]


def choose_photo_from_library(
    driver: WebDriver,
    *,
    album_name: str | None = None,
    picture_index: int = 1,
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
        primary_chosen = choose_local_photo(
            driver,
            album_name=album_name,
            picture_index=picture_index,
            select_all_from_album=select_all_from_album,
        )
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
            picture_index=picture_index,
            select_all_from_album=select_all_from_album,
        )


def dismiss_photo_permission_alerts(driver: WebDriver) -> None:
    page_source = _safe_page_source(driver)
    alert_texts = ["Allow all", "允许访问所有照片", "允许", "Allow", "好"]
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
        if any(
            text in page_source
            for text in [
                "最近项目",
                "照片图库",
                "所有照片",
                "选择项目",
                "选择照片",
                "Select photos",
                "Device folders",
            ]
        ):
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
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"
    if _is_android_gallery3d_picker(driver):
        return _choose_local_photo_from_android_gallery3d(
            driver,
            preferred_album_name=album_name,
            picture_index=normalized_index,
        )
    if album_name:
        with _photo_picker_profile("open-photo-album"):
            album_opened = open_photo_album(driver, album_name)
        if not album_opened:
            return False
        if is_ios and not _ensure_ios_photo_album_active(driver, album_name):
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
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    page_source = _safe_page_source(driver) if is_android else ""
    if (
        is_android
        and "Device folders" in page_source
        and album_name in page_source
    ):
        if not _tap_named_element_center(driver, album_name):
            return False
        return _wait_until(lambda: bool(find_photo_grid_candidates(driver)), timeout=2)

    current_title = photo_album_title(driver)
    _photo_picker_debug(f"open album start; target={album_name} current={current_title}")
    if current_title == album_name:
        return True
    if current_title == "选择最多9张照片。":
        if not _tap_photo_picker_back(driver):
            _photo_picker_debug("failed to leave multi-select grid before opening requested album")
            return False
        if not _wait_until(
            lambda: _photo_picker_collections_visible(driver) or photo_album_title(driver) != current_title,
            timeout=2,
        ):
            _photo_picker_debug(f"still on multi-select grid after back; current={photo_album_title(driver)}")
            return False
        current_title = photo_album_title(driver)
        _photo_picker_debug(f"after leaving multi-select grid; current={current_title}")
    if current_title not in {None, "选择最多9张照片。"}:
        if not _return_photo_picker_to_collections(driver, current_title=current_title):
            _photo_picker_debug(f"failed to return to collections from current={current_title}")
            return False
        current_title = photo_album_title(driver)
        _photo_picker_debug(f"after return to collections; current={current_title}")
    if not switch_photo_picker_to_collections(driver, current_title=current_title):
        _photo_picker_debug(f"failed to switch to collections; current={current_title}")
        return False
    for _ in range(4):
        if _tap_named_element_center(driver, album_name):
            if _wait_until(lambda: photo_album_title(driver) == album_name, timeout=2):
                _photo_picker_debug(f"opened target album={album_name}")
                return True
        if not is_android and _swipe_ios_album_carousel_left(driver):
            _wait_until(lambda: _tap_named_element_center(driver, album_name), timeout=1)
        else:
            try:
                swipe_vertical(driver, direction="up")
            except WebDriverException:
                pass
        time.sleep(0.3)
    _photo_picker_debug(f"failed to open target album={album_name}; final={photo_album_title(driver)}")
    return False


def tap_photo_grid_candidate(driver: WebDriver, picture_index: int) -> bool:
    candidates = find_photo_grid_candidates(driver)
    if not candidates:
        return False
    target_index = min(max(1, picture_index), len(candidates)) - 1
    candidate = candidates[target_index]
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "ios":
        return _tap_ios_photo_grid_candidate(driver, candidate)
    rect = _rect_snapshot(candidate)
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
        '//android.widget.ImageView[@clickable="true" and contains(@content-desc, "Photo")]',
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
    return _wait_until(
        lambda: photo_album_title(driver) == "精选集" or _visible_text_present(driver, "精选集"),
        timeout=2,
    )


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


def _return_photo_picker_to_collections(driver: WebDriver, *, current_title: str) -> bool:
    for _ in range(2):
        if _photo_picker_collections_visible(driver):
            _photo_picker_debug(f"collections already visible while leaving {current_title}")
            return True
        if not _tap_photo_picker_back(driver):
            _photo_picker_debug(f"back tap failed while leaving {current_title}")
            return False
        if _wait_until(
            lambda: _photo_picker_collections_visible(driver) or photo_album_title(driver) != current_title,
            timeout=2,
        ):
            _photo_picker_debug(f"back navigation left album {current_title}; now={photo_album_title(driver)}")
            return True
        time.sleep(0.3)
        _photo_picker_debug(f"back navigation still in album {current_title}; retrying")
    return _photo_picker_collections_visible(driver)


def _ensure_ios_photo_album_active(driver: WebDriver, album_name: str) -> bool:
    active_title = photo_album_title(driver)
    if active_title == album_name:
        return True
    _photo_picker_debug(f"album mismatch after open; expected={album_name} actual={active_title}")
    if active_title not in {None, "选择最多9张照片。"}:
        if not _return_photo_picker_to_collections(driver, current_title=active_title):
            return False
    if not switch_photo_picker_to_collections(driver):
        return False
    for _ in range(4):
        if _tap_named_element_center(driver, album_name) and _wait_until(
            lambda: photo_album_title(driver) == album_name,
            timeout=2,
        ):
            return True
        if _swipe_ios_album_carousel_left(driver):
            _wait_until(lambda: _tap_named_element_center(driver, album_name), timeout=1)
        else:
            try:
                swipe_vertical(driver, direction="up")
            except WebDriverException:
                pass
        time.sleep(0.3)
    _photo_picker_debug(f"album mismatch persisted; expected={album_name} actual={photo_album_title(driver)}")
    return False


def _photo_picker_collections_visible(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    return any(text in page_source for text in ["精选集", "最近项目", "照片图库", "所有照片", "选择项目"])


def confirm_note_image_cropper(driver: WebDriver, timeout: int = 10) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _cropper_visible(page_source, driver=driver):
            _photo_picker_debug(f"cropper visible; android={is_android}")
            if _tap_cropper_confirm_button(driver) and _wait_until(
                lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver)
                if is_android
                else not _cropper_visible(_safe_page_source(driver), driver=driver, allow_generic_text_fallback=False),
                timeout=8,
            ):
                _photo_picker_debug("cropper confirm succeeded")
                try:
                    setattr(driver, "_cropper_confirmed_once", True)
                except Exception:
                    pass
                return True
            _photo_picker_debug(f"cropper confirm did not exit; source={_safe_page_source(driver)[:300]}")
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
    if not page_source:
        return False
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    if _cropper_visible(page_source, driver=driver):
        if is_android and getattr(driver, "_cropper_confirmed_once", False) and not _android_cropper_visible(page_source):
            return True
        return confirm_note_image_cropper(driver, timeout=5)
    if is_android and _android_publish_selection_completed(page_source):
        return True
    return not any(
        text in page_source
        for text in [
            "选择最多9张照片。",
            'name="Add" label="完成"',
            "Select a photo",
            "Select photos",
            "Device folders",
            'package="com.google.android.apps.photos"',
            'text="Done"',
            "发布笔记",
            "发布活动",
        ]
    )


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
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    size = _safe_window_size(driver)

    xpaths = [
        '//*[@name="确认裁剪" or @label="确认裁剪" or @value="确认裁剪"]',
        '//*[contains(@name, "确认裁剪") or contains(@label, "确认裁剪") or contains(@value, "确认裁剪")]',
    ]
    if is_android:
        xpaths = [
            '//*[@text="确认裁剪"]/..',
            '//*[@text="确认裁剪"]',
            '//*[contains(@text, "确认裁剪")]',
        ] + xpaths

    for xpath in xpaths:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException):
            continue
        rect = _rect_snapshot(element)
        if is_android and rect is not None and _adb_tap_rect_ratio(driver, rect, x_ratio=0.5, y_ratio=0.5):
            _photo_picker_debug(f"cropper adb tap center via {xpath} rect={rect}")
            if _wait_until(lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver), timeout=4):
                return True
        try:
            element.click()
            _photo_picker_debug(f"cropper element.click via {xpath}")
            if _wait_until(lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver), timeout=2):
                return True
        except (AttributeError, WebDriverException):
            pass
        if rect is not None and _tap_rect_center(driver, rect):
            _photo_picker_debug(f"cropper appium center tap via {xpath} rect={rect}")
            if _wait_until(lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver), timeout=2):
                return True
        if is_android and rect is not None and _tap_rect_confirm_hotspots(driver, rect):
            return True
    if size is not None and _tap_android_cropper_confirm_fallbacks(driver, size=size, is_android=is_android):
        return True
    return False


def _tap_rect_confirm_hotspots(driver: WebDriver, rect: dict[str, float]) -> bool:
    hotspot_ratios = [
        (0.82, 0.5),
        (0.82, 0.25),
        (0.82, 0.75),
        (0.68, 0.5),
    ]
    for x_ratio, y_ratio in hotspot_ratios:
        if not _tap_rect_ratio(driver, rect, x_ratio=x_ratio, y_ratio=y_ratio):
            continue
        if _wait_until(lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver), timeout=2):
            return True
        if _adb_tap_rect_ratio(driver, rect, x_ratio=x_ratio, y_ratio=y_ratio):
            if _wait_until(lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver), timeout=2):
                return True
    return False


def _tap_android_cropper_confirm_fallbacks(
    driver: WebDriver,
    *,
    size: dict[str, int],
    is_android: bool,
) -> bool:
    fallback_points = [
        (0.735, 0.9375 if is_android else 0.91),
        (0.80, 0.9375 if is_android else 0.91),
        (0.67, 0.9375 if is_android else 0.91),
    ]
    for x_ratio, y_ratio in fallback_points:
        if not _tap_by_ratio(driver, x_ratio=x_ratio, y_ratio=y_ratio, size=size):
            continue
        if _wait_until(lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver), timeout=2):
            return True
        if _adb_tap_by_ratio(driver, x_ratio=x_ratio, y_ratio=y_ratio, size=size):
            if _wait_until(lambda: _cropper_exit_confirmed(_safe_page_source(driver), driver=driver), timeout=2):
                return True
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
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    xpaths = _visible_ios_text_xpaths(text)
    if is_android:
        xpaths = [
            f'//*[@text="{text}"]',
            f'//*[contains(@text, "{text}")]',
            f'//*[@name="{text}" or @label="{text}" or @value="{text}"]',
            f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
        ] + xpaths
    for xpath in xpaths:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            rect = _rect_snapshot(element)
            if rect is None:
                continue
            if not is_android and not _rect_center_inside_window(driver, rect):
                _photo_picker_debug(f"skip offscreen iOS element text={text} rect={rect}")
                continue
            x = rect["x"] + rect["width"] / 2
            y = rect["y"] + rect["height"] / 2
            try:
                driver.execute_script("mobile: tap", {"x": x, "y": y})
                return True
            except WebDriverException:
                pass
            try:
                element.click()
                return True
            except WebDriverException:
                pass
            if _tap_android_point_by_adb(driver, x=x, y=y):
                return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _rect_center_inside_window(driver: WebDriver, rect: dict[str, float]) -> bool:
    size = _safe_window_size(driver)
    if size is None:
        return True
    x = rect["x"] + rect["width"] / 2
    y = rect["y"] + rect["height"] / 2
    return 0 <= x <= size["width"] and 0 <= y <= size["height"]


def _swipe_ios_album_carousel_left(driver: WebDriver) -> bool:
    size = _safe_window_size(driver)
    if size is None:
        return False
    y = size["height"] * 0.52
    try:
        driver.execute_script(
            "mobile: dragFromToForDuration",
            {
                "duration": 0.35,
                "fromX": size["width"] * 0.86,
                "fromY": y,
                "toX": size["width"] * 0.16,
                "toY": y,
            },
        )
        return True
    except WebDriverException:
        try:
            driver.execute_script("mobile: swipe", {"direction": "left"})
            return True
        except WebDriverException:
            return False


def _tap_text_or_contains(driver: WebDriver, text: str) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    if is_android and tap_text_if_present(driver, text, timeout=1):
        return True
    xpaths = _visible_ios_text_xpaths(text)
    if is_android:
        xpaths.extend(
            [
                f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
            ]
        )
    for xpath in xpaths:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            if _tap_element_center(driver, element):
                return True
            element.click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_texts_by_predicate(driver: WebDriver, texts: list[str]) -> bool:
    escaped_texts = [text.replace("\\", "\\\\").replace('"', '\\"') for text in texts]
    quoted = ", ".join(f'"{text}"' for text in escaped_texts)
    predicate = f"visible == 1 AND (name IN {{{quoted}}} OR label IN {{{quoted}}} OR value IN {{{quoted}}})"
    try:
        driver.find_element(AppiumBy.IOS_PREDICATE, predicate).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _visible_ios_text_xpaths(text: str) -> list[str]:
    return [
        f'//*[@visible="true" and (@name="{text}" or @label="{text}" or @value="{text}")]',
        f'//*[@visible="true" and (contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}"))]',
    ]


def _visible_text_present(driver: WebDriver, text: str) -> bool:
    for xpath in _visible_ios_text_xpaths(text):
        try:
            driver.find_element(AppiumBy.XPATH, xpath)
            return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return False


def _tap_accessibility_id_now(driver: WebDriver, accessibility_id: str) -> bool:
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_photo_picker_done_button(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        if tap_text_if_present(driver, "Done", timeout=1):
            return True
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


def _tap_ios_photo_grid_candidate(driver: WebDriver, candidate) -> bool:
    if _ios_photo_picker_selection_active(driver):
        return True
    try:
        candidate.click()
        if _wait_until(lambda: _ios_photo_picker_selection_active(driver), timeout=1):
            return True
    except (AttributeError, WebDriverException):
        pass

    rect = _rect_snapshot(candidate)
    if rect is None:
        return False

    for x_ratio, y_ratio in [
        (0.5, 0.5),
        (0.35, 0.5),
        (0.65, 0.5),
        (0.5, 0.35),
        (0.5, 0.65),
    ]:
        if not _tap_rect_ratio(driver, rect, x_ratio=x_ratio, y_ratio=y_ratio):
            continue
        if _wait_until(lambda: _ios_photo_picker_selection_active(driver), timeout=1):
            return True
    return False


def _ios_photo_picker_selection_active(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if _cropper_visible(page_source, driver=driver):
        return True
    return _photo_picker_done_button_enabled(driver, page_source=page_source)


def _photo_picker_done_button_enabled(driver: WebDriver, *, page_source: str | None = None) -> bool:
    source = page_source if page_source is not None else _safe_page_source(driver)
    enabled_patterns = [
        'name="Add" label="完成" enabled="true"',
        'name="Add" enabled="true"',
        'name="完成" label="完成" enabled="true"',
        'name="添加" label="添加" enabled="true"',
        'label="完成" enabled="true"',
        'label="添加" enabled="true"',
    ]
    if any(pattern in source for pattern in enabled_patterns):
        return True
    for xpath in [
        '//*[@name="Add"]',
        '//*[@name="完成" or @label="完成" or @name="添加" or @label="添加"]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
        try:
            enabled = str(element.get_attribute("enabled") or "").strip().lower()
        except (AttributeError, WebDriverException):
            enabled = ""
        if enabled in {"true", "1"}:
            return True
    return False


def _choose_local_photo_from_android_gallery3d(
    driver: WebDriver,
    *,
    preferred_album_name: str | None = None,
    picture_index: int = 1,
) -> bool:
    size = _safe_window_size(driver)
    if size is None:
        return False

    album_name = preferred_album_name or _preferred_android_gallery3d_album_name()
    if album_name:
        if _tap_named_element_center(driver, album_name):
            if _wait_until(lambda: not _android_gallery3d_album_list_visible(_safe_page_source(driver)), timeout=2):
                time.sleep(0.5)
        card_index = _android_gallery3d_album_index(album_name)
        if card_index is not None and _android_gallery3d_album_list_visible(_safe_page_source(driver)):
            if _tap_android_gallery3d_album_card(driver, card_index, size=size):
                time.sleep(1)

    tap_order = _android_gallery3d_photo_positions()
    preferred_index = min(max(1, picture_index), len(tap_order)) - 1
    ordered_taps = [tap_order[preferred_index], *tap_order[:preferred_index], *tap_order[preferred_index + 1 :]]

    for x_ratio, y_ratio in ordered_taps:
        current_page = _safe_page_source(driver)
        if _android_publish_selection_completed(current_page):
            return True
        if not _tap_by_ratio(driver, x_ratio=x_ratio, y_ratio=y_ratio, size=size):
            continue
        if _wait_until(lambda: _photo_picker_transition_completed(driver) or _cropper_visible(_safe_page_source(driver), driver=driver), timeout=2):
            if _cropper_visible(_safe_page_source(driver), driver=driver):
                return confirm_note_image_cropper(driver, timeout=5)
            return True
        if _adb_tap_by_ratio(driver, x_ratio=x_ratio, y_ratio=y_ratio, size=size) and _wait_until(
            lambda: _photo_picker_transition_completed(driver) or _cropper_visible(_safe_page_source(driver), driver=driver),
            timeout=2,
        ):
            if _cropper_visible(_safe_page_source(driver), driver=driver):
                return confirm_note_image_cropper(driver, timeout=5)
            return True
        time.sleep(0.4)
        if _android_publish_selection_completed(_safe_page_source(driver)):
            return True
    return False


def _android_gallery3d_photo_positions() -> list[tuple[float, float]]:
    return [
        (0.18, 0.28),
        (0.50, 0.28),
        (0.82, 0.28),
        (0.18, 0.48),
        (0.50, 0.48),
    ]


def _is_android_gallery3d_picker(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    page_source = _safe_page_source(driver)
    return "com.android.gallery3d" in page_source and "选择照片" in page_source


def _android_gallery3d_album_list_visible(page_source: str) -> bool:
    return "选择照片" in page_source and any(text in page_source for text in ["相机", "云南洱海", "长白山"])


def _preferred_android_gallery3d_album_name() -> str | None:
    raw_value = os.environ.get("VW_MAC_PHOTO_ALBUMS", "").strip()
    if raw_value:
        for name in raw_value.split(","):
            normalized = name.strip()
            if normalized:
                return normalized
    return None


def _android_gallery3d_album_index(album_name: str) -> int | None:
    media_dir = Path(os.environ.get("VW_ANDROID_MEDIA_DIR", "")).expanduser() if os.environ.get("VW_ANDROID_MEDIA_DIR") else DEFAULT_ANDROID_MEDIA_DIR
    if not media_dir.exists():
        return None
    album_dirs = sorted(path.name for path in media_dir.iterdir() if path.is_dir())
    try:
        return album_dirs.index(album_name)
    except ValueError:
        return None


def _tap_android_gallery3d_album_card(driver: WebDriver, album_index: int, *, size: dict[str, int]) -> bool:
    # Gallery3d shows a system "相机" entry before our synced albums.
    y_ratios = [0.49, 0.76, 0.92]
    if album_index < 0 or album_index >= len(y_ratios):
        return False
    y_ratio = y_ratios[album_index]
    if _tap_by_ratio(driver, x_ratio=0.5, y_ratio=y_ratio, size=size):
        return True
    return _adb_tap_by_ratio(driver, x_ratio=0.5, y_ratio=y_ratio, size=size)


def _tap_by_ratio(
    driver: WebDriver,
    *,
    x_ratio: float,
    y_ratio: float,
    size: dict[str, int] | None = None,
) -> bool:
    if size is None:
        size = _safe_window_size(driver)
    if size is None:
        return False
    try:
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * x_ratio,
                "y": size["height"] * y_ratio,
            },
        )
        return True
    except WebDriverException:
        return _adb_tap_by_ratio(driver, x_ratio=x_ratio, y_ratio=y_ratio, size=size)


def _safe_window_size(driver: WebDriver) -> dict[str, int] | None:
    try:
        size = driver.get_window_size()
    except (AttributeError, WebDriverException):
        return None
    width = int(size.get("width", 0) or 0)
    height = int(size.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        return None
    return {"width": width, "height": height}


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
    return _tap_rect_ratio(driver, rect, x_ratio=0.5, y_ratio=0.5)


def _tap_rect_ratio(
    driver: WebDriver,
    rect: dict[str, float],
    *,
    x_ratio: float,
    y_ratio: float,
) -> bool:
    try:
        driver.execute_script(
            "mobile: tap",
            {
                "x": rect["x"] + rect["width"] * x_ratio,
                "y": rect["y"] + rect["height"] * y_ratio,
            },
        )
        return True
    except WebDriverException:
        return False


def _adb_tap_rect_ratio(
    driver: WebDriver,
    rect: dict[str, float],
    *,
    x_ratio: float,
    y_ratio: float,
) -> bool:
    x = rect["x"] + rect["width"] * x_ratio
    y = rect["y"] + rect["height"] * y_ratio
    return _adb_tap(driver, x=x, y=y)


def _adb_tap_by_ratio(
    driver: WebDriver,
    *,
    x_ratio: float,
    y_ratio: float,
    size: dict[str, int],
) -> bool:
    return _adb_tap(
        driver,
        x=size["width"] * x_ratio,
        y=size["height"] * y_ratio,
    )


def _adb_tap(driver: WebDriver, *, x: float, y: float) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    udid = (
        str(capabilities.get("appium:udid") or capabilities.get("udid") or "").strip()
        or os.environ.get("VW_ANDROID_UDID", "").strip()
    )
    if not udid:
        return False
    command = ["adb", "-s", udid, "shell", "input", "tap", str(int(x)), str(int(y))]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        _photo_picker_debug(f"adb tap failed to execute at ({int(x)}, {int(y)})")
        return False
    _photo_picker_debug(
        f"adb tap at ({int(x)}, {int(y)}) rc={result.returncode} stdout={(result.stdout or '').strip()} stderr={(result.stderr or '').strip()}"
    )
    return result.returncode == 0


def _tap_element_center(driver: WebDriver, element) -> bool:
    rect = _rect_snapshot(element)
    if rect is None:
        return False
    return _tap_rect_center(driver, rect)


def _cropper_visible(
    page_source: str,
    *,
    driver: WebDriver | None = None,
    allow_generic_text_fallback: bool = True,
) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    patterns = ANDROID_CROPPER_VISIBLE_PATTERNS if is_android else IOS_CROPPER_VISIBLE_PATTERNS
    if any(pattern in page_source for pattern in patterns):
        return True
    if allow_generic_text_fallback and not is_android:
        return any(pattern in page_source for pattern in ["确认裁剪", "裁剪图片"])
    return any(pattern in page_source for pattern in patterns)


def _android_cropper_visible(page_source: str) -> bool:
    return any(pattern in page_source for pattern in ANDROID_CROPPER_VISIBLE_PATTERNS)


def _android_publish_form_visible(page_source: str) -> bool:
    publish_markers = [
        'text="发布笔记"',
        'text="添加标题"',
        'text="输入正文"',
        'resource-id="image"',
    ]
    return any(marker in page_source for marker in publish_markers)


def _android_publish_selection_completed(page_source: str) -> bool:
    return _android_publish_form_visible(page_source) and 'resource-id="image"' in page_source


def _cropper_exit_confirmed(page_source: str, *, driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        return _android_publish_form_visible(page_source)
    return not _cropper_visible(page_source, driver=driver, allow_generic_text_fallback=False)


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
    except (AttributeError, WebDriverException):
        return ""


def _photo_picker_profile_enabled() -> bool:
    return os.getenv("VW_ACTIVITY_PROFILE", "").strip().lower() in {"1", "true", "yes", "on"}


def _photo_picker_debug_enabled() -> bool:
    return os.getenv("VW_APPIUM_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _photo_picker_debug(message: str) -> None:
    if _photo_picker_debug_enabled():
        print(f"[photo-picker-debug] {message}", flush=True)


@contextmanager
def _photo_picker_profile(label: str):
    started_at = time.monotonic()
    yield
    if _photo_picker_profile_enabled():
        elapsed = time.monotonic() - started_at
        print(f"[photo-picker-profile] {label}: {elapsed:.2f}s", flush=True)
