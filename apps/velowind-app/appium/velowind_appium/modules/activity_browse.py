from __future__ import annotations

from dataclasses import dataclass
import time
from xml.etree import ElementTree

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from velowind_appium.actions import (
    swipe_vertical,
    tap_accessibility_id_or_text_if_present,
    tap_if_present,
    tap_text_if_present,
)
from velowind_appium.modules.rental_common import tap_by_coordinate_ratios


ACTIVITY_READY_IDS = ["activity-discovery-v2-page"]
ACTIVITY_READY_TEXTS = ["全部活动", "活动", "总里程", "难度等级"]
ACTIVITY_CATEGORY_TEXTS = ["全部活动", "骑行", "徒步", "滑雪", "登山", "空中运动", "水上运动", "跑步"]
ACTIVITY_CARD_MARKERS = ["总里程", "时长", "场次", "难度等级"]
ACTIVITY_SEARCH_ENTRY_IDS = ["activity-search-entry", "activity-search-button", "activity-discovery-search"]
ACTIVITY_SEARCH_INPUT_XPATHS = [
    '//XCUIElementTypeTextField[@value="请输入内容" or @placeholderValue="请输入内容" or contains(@value, "搜索")]',
    '//XCUIElementTypeSearchField[@value="请输入内容" or @placeholderValue="请输入内容" or contains(@value, "搜索")]',
    '//android.widget.EditText[@text="请输入内容" or @hint="请输入内容" or contains(@text, "搜索")]',
    '//android.widget.EditText',
]
ACTIVITY_SEARCH_SUBMIT_TEXTS = ["搜索", "Search"]
ACTIVITY_DETAIL_READY_IDS = ["activity-route-detail-v3-hero-carousel", "activity-detail-page"]


@dataclass(frozen=True)
class ActivityDetailSnapshot:
    title: str | None
    location: str | None
    publisher: str | None
    hero_image_visible: bool
    metrics_visible: bool
    tags_visible: bool
    route_visible: bool
    comments_visible: bool
    sessions_visible: bool

    def merge(self, other: "ActivityDetailSnapshot") -> "ActivityDetailSnapshot":
        return ActivityDetailSnapshot(
            title=self.title or other.title,
            location=self.location or other.location,
            publisher=self.publisher or other.publisher,
            hero_image_visible=self.hero_image_visible or other.hero_image_visible,
            metrics_visible=self.metrics_visible or other.metrics_visible,
            tags_visible=self.tags_visible or other.tags_visible,
            route_visible=self.route_visible or other.route_visible,
            comments_visible=self.comments_visible or other.comments_visible,
            sessions_visible=self.sessions_visible or other.sessions_visible,
        )

    def is_basic_detail_complete(self) -> bool:
        return all(
            [
                self.title,
                self.location,
                self.publisher,
                self.hero_image_visible,
                self.metrics_visible,
                self.tags_visible,
                self.route_visible,
                self.comments_visible,
                self.sessions_visible,
            ]
        )


def open_activity_tab(driver: WebDriver, timeout: int = 20) -> None:
    if not tap_accessibility_id_or_text_if_present(driver, "bottom-nav-activity", "活动", timeout=5):
        raise AssertionError("Unable to tap the bottom activity tab")
    wait_for_activity_feed(driver, timeout=timeout)


def wait_for_activity_feed(driver: WebDriver, timeout: int = 20) -> str:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _activity_ready_id_present(driver):
            return "activity-feed-id"
        if page_source and _activity_ready_text_present(page_source):
            return "activity-feed-text"
        time.sleep(0.2)
    raise TimeoutException("Activity feed did not become ready")


def switch_activity_category_navigation(driver: WebDriver, timeout: int = 10) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if "全部活动" in page_source and any(text in page_source for text in ACTIVITY_CATEGORY_TEXTS):
            return
        time.sleep(0.2)
    raise AssertionError("Unable to find the activity category navigation")


def select_activity_category(driver: WebDriver, category_name: str, timeout: int = 10) -> None:
    if not _tap_activity_category(driver, category_name):
        raise AssertionError(f"Unable to tap activity category: {category_name}")
    if not wait_for_activity_category_results(driver, category_name, timeout=timeout):
        raise AssertionError(f"Activity feed did not show {category_name} related activities")


def wait_for_activity_category_results(driver: WebDriver, category_name: str, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if activity_feed_contains_category_results(_safe_page_source(driver), category_name):
            return True
        time.sleep(0.2)
    return False


def activity_feed_contains_category_results(page_source: str, category_name: str) -> bool:
    return bool(activity_feed_category_result_texts(page_source, category_name))


def activity_feed_category_result_texts(page_source: str, category_name: str) -> list[str]:
    tag_texts = extract_visible_activity_category_tag_texts(page_source)
    source_texts = tag_texts or extract_visible_activity_card_texts(page_source)
    return [text for text in source_texts if _activity_card_matches_category(text, category_name)]


def activity_feed_all_results_match_category(page_source: str, category_name: str) -> tuple[bool, list[str]]:
    tag_texts = extract_visible_activity_category_tag_texts(page_source)
    source_texts = tag_texts or extract_visible_activity_card_texts(page_source)
    mismatched = [text for text in source_texts if not _activity_card_matches_category(text, category_name)]
    return bool(source_texts) and not mismatched, mismatched


def open_activity_search(driver: WebDriver, timeout: int = 10) -> None:
    if _activity_search_visible(_safe_page_source(driver)):
        return
    for accessibility_id in ACTIVITY_SEARCH_ENTRY_IDS:
        if tap_if_present(driver, accessibility_id, timeout=1):
            break
    else:
        tap_by_coordinate_ratios(driver, [(0.925, 0.103), (0.91, 0.10)])
    if not _wait_until(lambda: _activity_search_visible(_safe_page_source(driver)), timeout=timeout):
        raise AssertionError("Activity search page did not appear")


def search_activities(driver: WebDriver, keyword: str, timeout: int = 15) -> None:
    search_input = _find_activity_search_input(driver, timeout=timeout)
    _replace_text(search_input, keyword)
    if not _tap_activity_search_submit(driver):
        raise AssertionError("Unable to submit activity search")
    if not wait_for_activity_text_search_results(driver, keyword, timeout=timeout):
        raise AssertionError(f"Activity search results did not appear for keyword: {keyword}")


def wait_for_activity_text_search_results(driver: WebDriver, keyword: str, timeout: int = 15) -> bool:
    return _wait_until(
        lambda: bool(activity_text_search_result_texts(_safe_page_source(driver), keyword)),
        timeout=timeout,
    )


def activity_text_search_result_texts(page_source: str, keyword: str) -> list[str]:
    normalized_keyword = " ".join(keyword.split())
    if not normalized_keyword:
        return []
    return [
        text
        for text in extract_visible_activity_card_texts(page_source)
        if normalized_keyword in text
    ]


def open_first_activity_detail(driver: WebDriver, timeout: int = 20) -> None:
    if activity_detail_is_visible(_safe_page_source(driver)):
        return
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        source = _safe_page_source(driver)
        if _tap_first_activity_card(
            driver,
            source,
            verify_open=lambda: activity_detail_is_visible(_safe_page_source(driver)),
            timeout=2,
        ):
            return
        time.sleep(0.3)
    raise AssertionError("Unable to open the first activity detail")


def activity_detail_is_visible(page_source: str) -> bool:
    return any(marker in page_source for marker in ACTIVITY_DETAIL_READY_IDS) or (
        "路线说明" in page_source and "确认报名" in page_source
    )


def browse_activity_detail(driver: WebDriver, timeout: int = 25) -> ActivityDetailSnapshot:
    snapshot = read_activity_detail_snapshot(driver, timeout=timeout)
    if snapshot.is_basic_detail_complete():
        return snapshot

    for _ in range(4):
        swipe_vertical(driver, "up")
        time.sleep(0.6)
        snapshot = snapshot.merge(parse_activity_detail_snapshot(_safe_page_source(driver)))
        if snapshot.is_basic_detail_complete():
            return snapshot
    return snapshot


def read_activity_detail_snapshot(driver: WebDriver, timeout: int = 20) -> ActivityDetailSnapshot:
    if not _wait_until(lambda: activity_detail_is_visible(_safe_page_source(driver)), timeout=timeout):
        raise AssertionError("Activity detail page did not become visible")
    return parse_activity_detail_snapshot(_safe_page_source(driver))


def parse_activity_detail_snapshot(page_source: str) -> ActivityDetailSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_visible_text = " ".join(visible_texts)

    return ActivityDetailSnapshot(
        title=_extract_activity_detail_title(page_source, visible_texts),
        location=_first_text_containing(visible_texts, "省·"),
        publisher=_extract_activity_publisher(joined_visible_text),
        hero_image_visible=_activity_detail_hero_visible(page_source),
        metrics_visible=all(text in joined_visible_text for text in ["总里程", "参考时长", "风险等级"]),
        tags_visible=all(text in joined_visible_text for text in ["风景标签", "沿途景点"]),
        route_visible=all(text in joined_visible_text for text in ["路线说明", "活动概览"]),
        comments_visible="活动评论" in joined_visible_text or "前往评论页查看真实活动评论" in joined_visible_text,
        sessions_visible=any(text in joined_visible_text for text in ["请选择场次", "场次信息", "集合地点"]),
    )


def extract_visible_activity_category_tag_texts(page_source: str) -> list[str]:
    return [
        text
        for text in extract_visible_activity_card_texts(page_source)
        if _looks_like_activity_category_tag_text(text)
    ]


def extract_visible_activity_card_texts(page_source: str) -> list[str]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return _extract_activity_card_texts_from_plain_source(page_source)

    texts: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if element.attrib.get("visible") == "false":
            continue
        text = (
            element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
        ).strip()
        if not _looks_like_activity_card_text(text):
            continue
        normalized = " ".join(text.split())
        if normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    for text in _extract_android_activity_card_texts(root):
        if text in seen:
            continue
        texts.append(text)
        seen.add(text)
    return texts


def _extract_android_activity_card_texts(root: ElementTree.Element) -> list[str]:
    def descendant_texts(element: ElementTree.Element) -> list[str]:
        return [
            child.attrib.get("text", "").strip()
            for child in element.iter()
            if child.attrib.get("displayed") != "false"
            and child.attrib.get("visible") != "false"
            and child.attrib.get("text", "").strip()
        ]

    def is_single_card_container(element: ElementTree.Element) -> bool:
        values = descendant_texts(element)
        return (
            any(value in ACTIVITY_CATEGORY_TEXTS[1:] for value in values)
            and all(values.count(marker) == 1 for marker in ACTIVITY_CARD_MARKERS)
        )

    results: list[str] = []
    for element in root.iter():
        if not is_single_card_container(element):
            continue
        values = descendant_texts(element)
        if any(is_single_card_container(child) for child in element) and not _android_card_context_values(values):
            continue
        category = next(value for value in values if value in ACTIVITY_CATEGORY_TEXTS[1:])
        ordered_values = (
            values
            if _android_card_context_values(values)
            else [category, *[value for value in values if value != category]]
        )
        results.append(" ".join(ordered_values))
    return results


def _android_card_context_values(values: list[str]) -> list[str]:
    return [
        value
        for value in values
        if value not in ACTIVITY_CATEGORY_TEXTS
        and value not in ACTIVITY_CARD_MARKERS
        and not _looks_like_android_metric_value(value)
        and any("\u4e00" <= character <= "\u9fff" for character in value)
    ]


def _looks_like_android_metric_value(value: str) -> bool:
    metric_characters = set("0123456789. -—约小时天晚公里kmKM场")
    return bool(value) and all(character in metric_characters for character in value)


def _extract_activity_card_texts_from_plain_source(page_source: str) -> list[str]:
    return [
        line.strip()
        for line in page_source.splitlines()
        if _looks_like_activity_card_text(line)
    ]


def _looks_like_activity_card_text(text: str) -> bool:
    if not text:
        return False
    if text.startswith("总里程"):
        return False
    if any(nav_text == text for nav_text in ACTIVITY_CATEGORY_TEXTS):
        return False
    if not all(marker in text for marker in ACTIVITY_CARD_MARKERS):
        return False
    return text.count("总里程") == 1


def _looks_like_activity_category_tag_text(text: str) -> bool:
    return any(text.startswith(category) for category in ACTIVITY_CATEGORY_TEXTS if category != "全部活动")


def _activity_card_matches_category(text: str, category_name: str) -> bool:
    if _looks_like_activity_category_tag_text(text):
        return text.startswith(category_name)
    return category_name in text


def _activity_search_visible(page_source: str) -> bool:
    return "请输入内容" in page_source and "搜索" in page_source


def _find_activity_search_input(driver: WebDriver, timeout: int = 10):
    end_at = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < end_at:
        for xpath in ACTIVITY_SEARCH_INPUT_XPATHS:
            try:
                return driver.find_element(AppiumBy.XPATH, xpath)
            except (NoSuchElementException, WebDriverException) as error:
                last_error = error
                continue
        time.sleep(0.2)
    raise AssertionError("Unable to locate the activity search input") from last_error


def _replace_text(element, value: str) -> None:
    element.click()
    try:
        element.clear()
    except WebDriverException:
        pass
    element.send_keys(value)


def _tap_activity_search_submit(driver: WebDriver) -> bool:
    for text in ACTIVITY_SEARCH_SUBMIT_TEXTS:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    if tap_by_coordinate_ratios(driver, [(0.86, 0.103), (0.84, 0.10)]):
        return True
    try:
        driver.execute_script("mobile: tap", {"x": 346, "y": 92})
        return True
    except WebDriverException:
        return False


def _tap_activity_category(driver: WebDriver, category_name: str) -> bool:
    if tap_text_if_present(driver, category_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "right"})
    except WebDriverException:
        pass
    if tap_text_if_present(driver, category_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "left"})
    except WebDriverException:
        pass
    return tap_text_if_present(driver, category_name, timeout=1)


def _tap_first_activity_card(driver: WebDriver, page_source: str, verify_open=None, timeout: float = 1.2) -> bool:
    for x, y in _activity_card_tap_points(page_source):
        try:
            driver.execute_script("mobile: tap", {"x": x, "y": y})
            if verify_open is None or _wait_until(verify_open, timeout=timeout):
                return True
        except WebDriverException:
            continue
    for ratio in [(0.50, 0.28), (0.50, 0.34), (0.50, 0.22)]:
        if not tap_by_coordinate_ratios(driver, [ratio]):
            continue
        if verify_open is None or _wait_until(verify_open, timeout=timeout):
            return True
    return False


def _activity_card_tap_points(page_source: str) -> list[tuple[int, int]]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return []

    rects: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        text = (
            element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
            or element.attrib.get("text", "")
        ).strip()
        if not _looks_like_activity_card_text(text):
            continue
        rect = _rect_from_attrs(element.attrib)
        if rect is None:
            continue
        x, y, width, height = rect
        if width < 180 or height < 120:
            continue
        rects.append(rect)

    points: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for x, y, width, height in sorted(set(rects), key=lambda item: (item[1], item[0])):
        x_point = x + max(1, width // 2)
        y_candidates = [
            y + min(max(48, height // 3), height - 20),
            y + min(max(72, height // 2), height - 20),
        ]
        for y_point in y_candidates:
            point = (x_point, y_point)
            if point in seen:
                continue
            points.append(point)
            seen.add(point)
    return points


def _activity_ready_id_present(driver: WebDriver) -> bool:
    for accessibility_id in ACTIVITY_READY_IDS:
        try:
            driver.find_element("accessibility id", accessibility_id)
            return True
        except Exception:
            continue
    return False


def _activity_ready_text_present(page_source: str) -> bool:
    return any(text in page_source for text in ACTIVITY_READY_TEXTS) and any(
        text in page_source for text in ["首页", "笔记"]
    )


def _extract_texts(page_source: str, *, visible_only: bool) -> list[str]:
    if not page_source:
        return []
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return [" ".join(page_source.split())]

    texts: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if visible_only and (
            element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false"
        ):
            continue
        raw_text = (
            element.attrib.get("text", "")
            or element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
        )
        normalized = " ".join(raw_text.split())
        if not normalized or normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    return texts


def _extract_activity_detail_title(page_source: str, visible_texts: list[str]) -> str | None:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        root = None

    if root is not None:
        candidates: list[tuple[int, str]] = []
        for element in root.iter():
            if element.attrib.get("visible") == "false":
                continue
            raw_text = (
                element.attrib.get("name", "")
                or element.attrib.get("label", "")
                or element.attrib.get("value", "")
            )
            text = " ".join(raw_text.split())
            rect = _rect_from_attrs(element.attrib)
            if rect is None:
                continue
            _, y, width, _ = rect
            if 170 <= y <= 330 and width >= 120 and _looks_like_activity_detail_title(text):
                candidates.append((y, text))
        if candidates:
            return sorted(candidates)[0][1]

    for text in visible_texts:
        if _looks_like_activity_detail_title(text):
            return text
    return None


def _looks_like_activity_detail_title(text: str) -> bool:
    if len(text) < 4:
        return False
    if any(marker in text for marker in ["省·", "总里程", "路线说明", "活动评论", "报名费用"]):
        return False
    if text in set(ACTIVITY_CATEGORY_TEXTS) | {"ROUTE", "COMMENTS", "活动概览", "路线主理人"}:
        return False
    return True


def _first_text_containing(texts: list[str], keyword: str) -> str | None:
    return next((text for text in texts if keyword in text), None)


def _extract_activity_publisher(joined_text: str) -> str | None:
    marker = " 路线主理人"
    if marker not in joined_text:
        return None
    before_marker = joined_text.split(marker, 1)[0].split()
    return before_marker[-1] if before_marker else None


def _activity_detail_hero_visible(page_source: str) -> bool:
    return "activity-route-detail-v3-hero-carousel" in page_source or (
        activity_detail_is_visible(page_source) and "XCUIElementTypeImage" in page_source
    )


def _rect_from_attrs(attrs: dict[str, str]) -> tuple[int, int, int, int] | None:
    try:
        x = int(float(attrs.get("x", "0")))
        y = int(float(attrs.get("y", "0")))
        width = int(float(attrs.get("width", "0")))
        height = int(float(attrs.get("height", "0")))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return (x, y, width, height)


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""


def _wait_until(predicate, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if predicate():
            return True
        time.sleep(0.2)
    return False
