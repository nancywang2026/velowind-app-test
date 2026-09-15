from dataclasses import dataclass
import html
import json
import os
import re
import time
from typing import Optional
import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from velowind_appium.actions import safe_back, swipe_vertical, tap_text_if_present
from velowind_appium.android_settings import without_android_idle_wait
from velowind_appium.cleanup_config import CleanupConfig, matches_test_data
from velowind_appium.modules.activity import _tap_element_center
from velowind_appium.modules.activity_sessions import open_my_activity_publish_list
from velowind_appium.session import ensure_logged_in_on_home
from velowind_appium.timing import profile_section


NOTE_ACTION_TEXTS = ["删除", "确认删除"]
ACTIVITY_ACTION_TEXTS = ["下架", "取消发布", "删除"]
SESSION_ACTION_TEXTS = ["删除", "取消", "下架"]
CONFIRM_TEXTS = ["确认删除", "确定", "确认", "删除", "下架", "取消发布"]
MIN_TRUNCATED_TITLE_PREFIX_LENGTH = 12
TRUNCATED_TITLE_WAIT_SECONDS = 10


@dataclass(frozen=True)
class CleanupReport:
    item_type: str
    deleted: list[str]
    skipped: list[str]


def cleanup_notes(driver: WebDriver, config: CleanupConfig, app_config, *, dry_run: bool = False) -> CleanupReport:
    ensure_logged_in_on_home(driver, app_config)
    _open_me_entry(driver, "我的笔记")
    try:
        return cleanup_matching_visible_items(
            driver,
            item_type="note",
            matchers=config.note_matchers,
            action_texts=NOTE_ACTION_TEXTS,
            dry_run=dry_run,
        )
    finally:
        safe_back(driver)


def cleanup_published_note(driver: WebDriver, title: str, app_config) -> CleanupReport:
    mode = os.environ.get("VW_NOTE_CLEANUP_MODE", "ui").strip().lower()
    if mode not in {"ui", "api"}:
        raise ValueError("VW_NOTE_CLEANUP_MODE must be ui or api")
    # A playing video continuously emits accessibility events. Waiting for
    # global idleness adds ~10s to each query before navigation can even begin.
    # Keep the existing explicit waits and title checks; restore the setting
    # before the next test or any unrelated workflow uses this shared session.
    with without_android_idle_wait(driver):
        with profile_section("cleanup.prepare-home"):
            ensure_logged_in_on_home(driver, app_config)
        with profile_section("cleanup.open-my-notes"):
            _open_me_entry(driver, "我的笔记")
        try:
            with profile_section("cleanup.delete-exact-note"):
                if mode == "api":
                    return cleanup_published_note_via_api(driver, title, app_config)
                return cleanup_exact_visible_item(
                    driver,
                    item_type="note",
                    title=title,
                    action_texts=NOTE_ACTION_TEXTS,
                )
        finally:
            with profile_section("cleanup.leave-note-list"):
                safe_back(driver)


def cleanup_published_note_via_api(driver, title: str, app_config) -> CleanupReport:
    """Delete one uniquely matched visible note from the already-open My Notes page."""
    from velowind_appium.note_api_cleanup import delete_note_via_api, note_post_ids_from_xml

    deadline = time.monotonic() + 8
    while True:
        post_ids = note_post_ids_from_xml(_safe_page_source(driver), title)
        if len(post_ids) == 1:
            delete_note_via_api(post_ids[0], app_config.login_username, app_config.login_password)
            return CleanupReport("note", [title], [])
        if len(post_ids) > 1 or time.monotonic() >= deadline:
            return CleanupReport("note", [], [title])
        time.sleep(.3)


def cleanup_activities(driver: WebDriver, config: CleanupConfig, app_config, *, dry_run: bool = False) -> CleanupReport:
    ensure_logged_in_on_home(driver, app_config)
    open_my_activity_publish_list(driver)
    try:
        return cleanup_matching_visible_items(
            driver,
            item_type="activity",
            matchers=config.activity_matchers,
            action_texts=ACTIVITY_ACTION_TEXTS,
            dry_run=dry_run,
            required_page_texts=["通过", "上架"],
        )
    finally:
        safe_back(driver)


def cleanup_sessions(driver: WebDriver, config: CleanupConfig, app_config, *, dry_run: bool = False) -> CleanupReport:
    ensure_logged_in_on_home(driver, app_config)
    open_my_activity_publish_list(driver)
    try:
        if not tap_text_if_present(driver, "管理场次", timeout=2):
            return CleanupReport(item_type="session", deleted=[], skipped=[])
        return cleanup_matching_visible_items(
            driver,
            item_type="session",
            matchers=config.session_matchers,
            action_texts=SESSION_ACTION_TEXTS,
            dry_run=dry_run,
        )
    finally:
        safe_back(driver)


def cleanup_matching_visible_items(
    driver: WebDriver,
    *,
    item_type: str,
    matchers: list[str],
    action_texts: list[str],
    dry_run: bool,
    required_texts: Optional[list[str]] = None,
    required_page_texts: Optional[list[str]] = None,
    exact_match: bool = False,
    max_rounds: int = 20,
) -> CleanupReport:
    deleted: list[str] = []
    skipped: list[str] = []
    seen: set[str] = set()

    for _ in range(max_rounds):
        page_source = _safe_page_source(driver)
        page_has_required_texts = not required_page_texts or all(text in page_source for text in required_page_texts)
        candidates = [
            text for text in find_matching_visible_texts(page_source, matchers, required_texts=required_texts)
            if text not in seen
            and page_has_required_texts
            and (not exact_match or text in matchers)
        ]
        if candidates:
            for candidate in candidates:
                seen.add(candidate)
                if dry_run:
                    skipped.append(candidate)
                    continue
                if _delete_candidate(driver, candidate, action_texts):
                    deleted.append(candidate)
                    break
                skipped.append(candidate)
                safe_back(driver)
                break
            if not dry_run:
                continue
        if _cleanup_page_reached_end(page_source):
            break
        if not _scroll_page(driver):
            break
        next_page_source = _safe_page_source(driver)
        if next_page_source == page_source:
            break

    return CleanupReport(item_type=item_type, deleted=deleted, skipped=skipped)


def cleanup_exact_visible_item(
    driver: WebDriver,
    *,
    item_type: str,
    title: str,
    action_texts: list[str],
) -> CleanupReport:
    """Delete a just-created item only when its exact title is visible at the list top."""
    if item_type == "note" and _is_android(driver):
        return _cleanup_exact_android_note(driver, item_type=item_type, title=title, action_texts=action_texts)
    if item_type == "note" and str((getattr(driver, "capabilities", {}) or {}).get("platformName", "")).lower() == "ios":
        return _cleanup_exact_ios_note(driver, title, action_texts)
    if not _tap_exact_visible_title(driver, title):
        return CleanupReport(item_type=item_type, deleted=[], skipped=[])
    time.sleep(0.5)
    if not tap_first_available_text(driver, ["更多", "...", "…"]):
        _tap_ios_top_right_more(driver)
    if not tap_first_available_text(driver, action_texts):
        return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
    if not confirm_destructive_action(driver):
        return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
    return CleanupReport(item_type=item_type, deleted=[title], skipped=[])


def _is_android(driver) -> bool:
    return str((getattr(driver, "capabilities", {}) or {}).get("platformName", "")).lower() == "android"


def _normalized_note_title(value: str) -> str:
    return "".join(value.split())


def _ios_note_cards(source: str, *, visible_only: bool = True):
    from velowind_appium.modules.message_detail import _ios_note_card_title, _source_element_rect
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        return []
    root = next((e for e in root.iter() if e.get("name") == "my-posts-scroll-notes"), root)
    cards = []
    def visit(node):
        if visible_only and (node.get("visible") == "false" or node.get("displayed") == "false"):
            return
        # Preserve line-break wrapping until title matching, so a break in the
        # middle of a Chinese title does not become a significant extra space.
        title = _ios_note_card_title({"type": node.tag, **node.attrib})
        rect = _source_element_rect(node.attrib)
        if title and rect:
            cards.append((node.get("name"), title, rect))
        for child in node:
            visit(child)
    visit(root)
    return cards


def _ios_detail_has_exact_title(source: str, title: str) -> bool:
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        return False
    def visit(node, in_detail=False):
        if node.get("visible") == "false" or node.get("displayed") == "false":
            return False
        in_detail = in_detail or node.get("name") == "post-detail-page"
        if in_detail and node.get("type", node.tag) == "XCUIElementTypeStaticText":
            text = node.get("label") or node.get("value") or node.get("name", "")
            if _normalized_note_title(text) == _normalized_note_title(title):
                return True
        return any(visit(child, in_detail) for child in node)
    return visit(root)


def _cleanup_exact_ios_note(driver, title: str, action_texts: list[str]) -> CleanupReport:
    from velowind_appium.modules.message_detail import _tap_rect_center, _tap_ios_detail_back_button_from_source
    normalized = _normalized_note_title(title)
    deadline = time.monotonic() + 8
    cards = []
    while not cards:
        cards = [entry for entry in _ios_note_cards(_safe_page_source(driver))
                 if _normalized_note_title(entry[1]) == normalized]
        if cards or time.monotonic() >= deadline:
            break
        # Opening My Notes returns before its async cards have been laid out.
        # Keep this page open long enough for the exact card to become visible.
        time.sleep(.3)
    if not cards:
        return CleanupReport("note", [], [])
    post_id, _, (left, top, right, bottom) = min(cards, key=lambda c: (c[2][1], c[2][0]))
    if not _tap_rect_center(driver, {"x": left, "y": top, "width": right-left, "height": bottom-top}):
        return CleanupReport("note", [], [title])
    deadline = time.monotonic() + 8
    revealed_title = False
    while not _ios_detail_has_exact_title(_safe_page_source(driver), title):
        source = _safe_page_source(driver)
        if not revealed_title and "post-detail-page" in source:
            # Portrait video can cover the title beneath the player.
            swipe_vertical(driver, direction="up")
            revealed_title = True
        if time.monotonic() >= deadline:
            _tap_ios_detail_back_button_from_source(driver)
            return CleanupReport("note", [], [title])
        time.sleep(.2)
    if not _tap_ios_top_right_more(driver) or not tap_first_available_text(driver, action_texts):
        return CleanupReport("note", [], [title])
    confirm_destructive_action(driver)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        source = _safe_page_source(driver)
        if "my-posts-scroll-notes" in source and not _ios_detail_has_exact_title(source, title):
            if post_id not in {entry[0] for entry in _ios_note_cards(source, visible_only=False)}:
                return CleanupReport("note", [title], [])
        time.sleep(.2)
    return CleanupReport("note", [], [title])


def _cleanup_exact_android_note(driver, *, item_type, title, action_texts) -> CleanupReport:
    deadline = time.monotonic() + 10
    opened = False
    while not opened:
        # Scope to note cards: a transitioning screen can still expose the
        # previous detail's title in the same Android hierarchy.
        for rendered in _visible_text_values(_safe_page_source(driver)):
            prefix = rendered.rstrip("…").rstrip()
            if rendered != title and not (
                len(prefix) >= MIN_TRUNCATED_TITLE_PREFIX_LENGTH
                and len(prefix) < len(title) and title.startswith(prefix)
            ):
                continue
            locator = (
                '//*[starts-with(@resource-id, "post-home-feed-note-card-")]'
                f'//*[@text={_xpath_literal(rendered)}]'
            )
            for element in driver.find_elements(AppiumBy.XPATH, locator):
                if _element_is_visible(element):
                    _tap_element_center(driver, element)
                    opened = True
                    break
            if opened:
                break
        if opened or time.monotonic() >= deadline:
            break
        time.sleep(0.2)
    if not opened:
        return CleanupReport(item_type=item_type, deleted=[], skipped=[])
    # A prefix is only sufficient to open a candidate, never to delete it.
    deadline = time.monotonic() + 8
    detail_title = f'//*[@resource-id="post-detail-page"]//*[@text={_xpath_literal(title)}]'
    while not any(_element_is_visible(e) for e in driver.find_elements(AppiumBy.XPATH, detail_title)):
        if time.monotonic() >= deadline:
            safe_back(driver)
            return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
        time.sleep(0.2)
    if not _tap_android_note_more(driver) or not tap_first_available_text(driver, action_texts):
        safe_back(driver)
        return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
    if not tap_first_available_text(driver, CONFIRM_TEXTS):
        return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
    deadline = time.monotonic() + 8
    while driver.find_elements(AppiumBy.ID, "post-detail-page"):
        if time.monotonic() >= deadline:
            return CleanupReport(item_type=item_type, deleted=[], skipped=[title])
        time.sleep(0.2)
    return CleanupReport(item_type=item_type, deleted=[title], skipped=[])


def _tap_android_note_more(driver) -> bool:
    # The header has a stable testID; its final direct child is the menu icon.
    locator = '//*[@resource-id="post-detail-top-nav-subpage-header"]/android.view.ViewGroup[last()]'
    for element in driver.find_elements(AppiumBy.XPATH, locator):
        if _element_is_visible(element):
            _tap_element_center(driver, element)
            return True
    return False


def _tap_exact_visible_title(driver: WebDriver, title: str) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    platform = str(capabilities.get("platformName", "")).lower()
    candidates = [title]

    exact_title_found = False
    for candidate in candidates:
        if platform == "android":
            quoted = json.dumps(candidate, ensure_ascii=False)
            locator = (AppiumBy.ANDROID_UIAUTOMATOR, f"new UiSelector().text({quoted})")
        else:
            escaped = candidate.replace("\\", "\\\\").replace('"', '\\"')
            locator = (
                AppiumBy.IOS_PREDICATE,
                f'name == "{escaped}" OR label == "{escaped}" OR value == "{escaped}"',
            )
        try:
            elements = driver.find_elements(*locator)
        except (AttributeError, NoSuchElementException, WebDriverException):
            elements = []
        exact_title_found = exact_title_found or bool(elements)
        for element in elements:
            if not _element_is_visible(element):
                continue
            _tap_element_center(driver, element)
            return True

    if platform == "ios":
        # React Native can expose the title in page source as an exact visible
        # StaticText while the native predicate query still returns no match.
        # Stay on the current viewport and use an exact XPath fallback before
        # considering rendered truncation; newly published notes are at the top.
        escaped_title = _xpath_literal(title)
        exact_xpath = (
            '//*[@visible="true" and '
            f'(@name={escaped_title} or @label={escaped_title} or @value={escaped_title})]'
        )
        try:
            exact_elements = driver.find_elements(AppiumBy.XPATH, exact_xpath)
        except (AttributeError, NoSuchElementException, WebDriverException):
            exact_elements = []
        for element in exact_elements:
            if not _element_is_visible(element):
                continue
            _tap_element_center(driver, element)
            return True

        # An exact but off-screen match needs scrolling, not a ten-second wait
        # for a truncated rendering of the same title.
        if exact_title_found:
            return False
        end_at = time.monotonic() + TRUNCATED_TITLE_WAIT_SECONDS
        while True:
            for rendered_title in find_visible_truncated_title_variants(_safe_page_source(driver), title):
                escaped = rendered_title.replace("\\", "\\\\").replace('"', '\\"')
                locator = (
                    AppiumBy.IOS_PREDICATE,
                    f'name == "{escaped}" OR label == "{escaped}" OR value == "{escaped}"',
                )
                try:
                    elements = driver.find_elements(*locator)
                except (AttributeError, NoSuchElementException, WebDriverException):
                    continue
                for element in elements:
                    if not _element_is_visible(element):
                        continue
                    _tap_element_center(driver, element)
                    return True
            if time.monotonic() >= end_at:
                break
            time.sleep(0.2)
    return False


def find_visible_truncated_title_variants(page_source: str, title: str) -> list[str]:
    """Return visible iOS title labels that are safe truncations of ``title``."""
    try:
        root = ET.fromstring(page_source)
    except ET.ParseError:
        return []

    variants: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        element_type = element.attrib.get("type", element.tag)
        if element_type != "XCUIElementTypeStaticText" or element.attrib.get("visible") == "false":
            continue
        rendered_title = next(
            (
                element.attrib.get(attribute, "").strip()
                for attribute in ("name", "label", "value")
                if element.attrib.get(attribute, "").strip()
            ),
            "",
        )
        comparable_title = rendered_title.rstrip("…").rstrip()
        if (
            rendered_title in seen
            or len(comparable_title) < MIN_TRUNCATED_TITLE_PREFIX_LENGTH
            or len(comparable_title) >= len(title)
            or not title.startswith(comparable_title)
        ):
            continue
        seen.add(rendered_title)
        variants.append(rendered_title)

    return sorted(variants, key=lambda value: len(value.rstrip("…").rstrip()), reverse=True)


def _cleanup_page_reached_end(page_source: str) -> bool:
    return any(marker in page_source for marker in ["已经到底了", "没有更多了", "暂无更多"])


def find_matching_visible_texts(
    page_source: str,
    matchers: list[str],
    *,
    required_texts: Optional[list[str]] = None,
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for value in _visible_text_values(page_source):
        text = html.unescape(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        if text.startswith("#"):
            continue
        if required_texts and not all(required_text in text for required_text in required_texts):
            continue
        if matches_test_data(text, matchers):
            matched.append(text)
    return matched


def _visible_text_values(page_source: str) -> list[str]:
    try:
        root = ET.fromstring(page_source)
    except ET.ParseError:
        return re.findall(r'(?:text|name|label|value)="([^"]+)"', page_source)

    values: list[str] = []
    for element in root.iter():
        if not _is_text_candidate_element(element):
            continue
        for attribute in ("text", "name", "label", "value"):
            value = element.attrib.get(attribute)
            if value:
                values.append(value)
                break
    return values


def _is_text_candidate_element(element: ET.Element) -> bool:
    element_type = element.attrib.get("type", element.tag)
    if element_type.startswith("XCUIElementType") and element.attrib.get("visible") == "false":
        return False
    if element_type in {"XCUIElementTypeStaticText", "XCUIElementTypeButton"}:
        return True
    if element_type.endswith("TextView") or element_type.endswith("Button"):
        return True
    if element_type.startswith("XCUIElementType"):
        return False
    return len(list(element)) == 0


def _delete_candidate(driver: WebDriver, text: str, action_texts: list[str]) -> bool:
    if not tap_matching_item(driver, text):
        return False
    time.sleep(0.5)
    if not tap_first_available_text(driver, ["更多", "...", "…"]):
        if _is_android(driver):
            _tap_android_note_more(driver)
        else:
            _tap_ios_top_right_more(driver)
    if not tap_first_available_text(driver, action_texts):
        return False
    return confirm_destructive_action(driver)


def tap_matching_item(driver: WebDriver, text: str) -> bool:
    for xpath in _candidate_xpaths(text):
        try:
            for element in driver.find_elements(AppiumBy.XPATH, xpath):
                if not _element_is_visible(element):
                    continue
                _tap_element_center(driver, element)
                return True
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
    return tap_text_if_present(driver, text, timeout=1)


def tap_first_available_text(driver: WebDriver, texts: list[str]) -> bool:
    for text in texts:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    return False


def _element_is_visible(element) -> bool:
    try:
        return bool(element.is_displayed())
    except (WebDriverException, AttributeError):
        return True


def _tap_ios_top_right_more(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "ios":
        return False
    try:
        size = driver.get_window_size()
        driver.execute_script("mobile: tap", {"x": size["width"] - 36, "y": 92})
        return True
    except (WebDriverException, KeyError, TypeError):
        return False


def confirm_destructive_action(driver: WebDriver) -> bool:
    for text in CONFIRM_TEXTS:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    return True


def _open_me_entry(driver: WebDriver, text: str) -> None:
    if tap_text_if_present(driver, text, timeout=2):
        return
    tap_text_if_present(driver, "我的", timeout=3)
    if tap_text_if_present(driver, text, timeout=5):
        return
    raise AssertionError(f"Unable to open Me entry: {text}")


def _candidate_xpaths(text: str) -> list[str]:
    escaped = _xpath_literal(text)
    return [
        f'//*[contains(@text, {escaped})]/ancestor::android.view.ViewGroup[1]',
        f'//*[contains(@text, {escaped})]/ancestor::android.view.ViewGroup[2]',
        f'//*[contains(@name, {escaped}) or contains(@label, {escaped}) or contains(@value, {escaped})]/ancestor::*[1]',
        f'//*[contains(@text, {escaped}) or contains(@name, {escaped}) or contains(@label, {escaped}) or contains(@value, {escaped})]',
    ]


def _xpath_literal(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ', \'"\', '.join(f'"{part}"' for part in parts) + ")"


def _scroll_page(driver: WebDriver) -> bool:
    try:
        swipe_vertical(driver, direction="up")
        return True
    except (WebDriverException, AttributeError):
        return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""
