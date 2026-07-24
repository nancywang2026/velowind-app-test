from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import html
import os
from pathlib import Path
import re
import subprocess
import time
from xml.etree import ElementTree

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
import yaml

from velowind_appium.actions import (
    swipe_vertical,
    tap_if_present,
    tap_text_if_present,
    wait_for_any_accessibility_id_or_text,
)
from velowind_appium.auth import ensure_logged_in_if_needed, login_required_from_page_source
from velowind_appium.config import IosAppiumConfig
import velowind_appium.modules.photo_picker as photo_picker
from velowind_appium.modules.note_card_picker import tap_first_note_card


DETAIL_READY_IDS = [
    "post-detail-page",
    "message-detail-page",
    "article-detail-page",
]
DETAIL_READY_TEXTS = ["写留言", "留言", "评论", "浏览"]
COMMENT_ENTRY_IDS = [
    "post-detail-comment-entry",
    "message-comment-entry",
    "write-comment-entry",
]
COMMENT_ENTRY_TEXTS = ["写留言", "留言", "写评论"]
COMMENT_INPUT_IDS = [
    "comment-input",
    "message-comment-input",
    "post-detail-comment-input",
]
COMMENT_SUBMIT_IDS = [
    "comment-submit",
    "message-comment-submit",
    "post-detail-comment-submit",
]
COMMENT_SUBMIT_TEXTS = ["发送", "发布", "提交"]
TICKET_TOGGLE_IDS = [
    "post-ticket-toggle",
    "message-ticket-toggle",
    "ticket-toggle",
]
TICKET_TOGGLE_TEXTS = ["查看图票", "图票", "收起图票"]
PUBLISH_ENTRY_IDS = [
    "bottom-nav-publish",
    "bottom-nav-plus",
    "bottom-nav-add",
    "home-publish-entry",
    "home-create-entry",
]
PUBLISH_ENTRY_TEXTS = ["发布", "创建", "+", "＋"]
NOTE_TYPE_IDS = [
    "publish-type-note",
    "publish-type-message",
    "post-type-note",
    "note-publish-type",
]
NOTE_TYPE_TEXTS = ["笔记", "发布笔记", "图文", "动态"]
NOTE_FORM_READY_IDS = [
    "note-publish-page",
    "message-publish-page",
    "post-publish-page",
    "note-submit-button",
    "message-submit-button",
    "post-submit-button",
    "publish-submit-button",
]
NOTE_FORM_READY_TEXTS = [
    "发布笔记",
    "标题",
    "正文",
    "话题",
    "标记地点",
    "允许评论",
    "添加标题",
    "输入标题",
    "添加正文",
    "输入正文",
    "存草稿",
    "提交审核",
]
NOTE_SUCCESS_TEXTS = ["发布成功", "提交成功", "审核中", "待审核", "提交审核成功", "已发布"]
NOTE_SUCCESS_IDS = [
    "note-publish-success",
    "message-publish-success",
    "publish-success-page",
]
NOTE_SEARCH_ENTRY_IDS = [
    "home-search",
    "home-search-button",
    "search-entry",
    "note-search-entry",
]
NOTE_SEARCH_TEXTS = ["搜索", "搜索笔记", "搜索内容"]
NOTE_SEARCH_INPUT_XPATHS = [
    '//android.widget.EditText[contains(@hint, "请输入内容")]',
    '//android.widget.EditText[contains(@text, "请输入内容")]',
    "//android.widget.EditText",
    "//XCUIElementTypeSearchField",
    '//XCUIElementTypeTextField[contains(@value, "请输入内容")]',
    '//XCUIElementTypeTextField[contains(@value, "搜索")]',
    '//XCUIElementTypeTextField',
]
NOTE_SEARCH_RESULT_IDS = [
    "search-result-note-0",
    "note-search-result-0",
    "post-search-result-0",
]
NOTE_ERROR_TEXTS = ["服务开小差了，请稍后重试", "服务器内部错误", "发布失败", "提交失败"]
TITLE_FIELD_KEYWORDS = ["标题", "请输入标题", "添加标题", "输入标题"]
BODY_FIELD_KEYWORDS = ["正文", "内容", "分享", "描述", "添加正文", "输入正文"]
LOCATION_FIELD_KEYWORDS = ["标记地点", "地点", "位置"]
GENERIC_DETAIL_TEXTS = {
    "首页",
    "推荐",
    "全国",
    "评论",
    "浏览",
    "写留言",
    "留言",
    "图票",
    "查看图票",
    "收起图票",
    "发送",
    "发布",
    "提交",
}
ATTRIBUTE_PATTERN = re.compile(r'(?:name|label|value|text)="([^"]+)"')
VIEW_COUNT_PATTERN = re.compile(r"浏览(?:量)?[^\d<\"]*(\d+)")
COMMENT_COUNT_PATTERN = re.compile(r"评论(?:数)?[^\d<\"]*(\d+)")
COUNT_ONLY_PATTERN = re.compile(r"^(?:浏览|评论)\s*(\d+)$")
BOTTOM_ACTION_PATTERN = re.compile(r"^.+\s+(\d+)\s+(\d+)\s+(\d+)$")
CROPPER_VISIBLE_PATTERNS = [
    'name="publish-note-image-picker-cropper-viewport" enabled="true" visible="true"',
    'name="确认裁剪" label="确认裁剪" enabled="true" visible="true"',
    'name="裁剪图片" label="裁剪图片" enabled="true" visible="true"',
]
LOCATION_SECTION_VISIBLE_PATTERNS = [
    'name="标记地点" label="标记地点" enabled="true" visible="true"',
    'value="标记地点" name="标记地点" label="标记地点" enabled="true" visible="true"',
]
LOCATION_PICKER_VISIBLE_PATTERNS = [
    'value="标记地点" name="标记地点" label="标记地点" enabled="true" visible="true"',
    'name="搜索地点" label="搜索地点" enabled="true" visible="true"',
]
NOTE_TESTDATA_FILE = Path(__file__).resolve().parents[2] / "tests" / "message" / "testdata" / "publish_notes.yaml"


@dataclass
class MessageDetailSnapshot:
    title: str | None
    body: str | None
    view_count: str | None
    comment_count: str | None
    comments: list[str]
    empty_comment_hint: str | None
    bottom_action_counts: list[str]


@dataclass(frozen=True)
class MessageNoteDraft:
    title: str
    body: str
    topics: list[str]
    location: str
    album: str | None = None
    picture_index: int = 1
    picture_indexes: tuple[int, ...] = ()
    allow_comments: bool = True


def build_changbaishan_note_draft() -> MessageNoteDraft:
    return load_message_note_draft("publish-note-changbaishan")


def load_message_note_draft(use_case_id: str, *, testdata_path: Path | None = None) -> MessageNoteDraft:
    cases = _load_message_note_cases(testdata_path=testdata_path)
    for case in cases:
        if str(case.get("id", "")).strip() == use_case_id:
            return _build_note_draft_from_case(case)
    raise AssertionError(f"Unable to find publish note use case: {use_case_id}")


def _load_message_note_cases(*, testdata_path: Path | None = None) -> list[dict]:
    source_path = testdata_path or NOTE_TESTDATA_FILE
    data = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    use_cases = data.get("use_cases", [])
    if not isinstance(use_cases, list):
        raise AssertionError(f"Invalid publish note testdata format: {source_path}")
    return [case for case in use_cases if isinstance(case, dict)]


def list_message_note_use_case_ids(*, testdata_path: Path | None = None) -> list[str]:
    return [
        str(case.get("id", "")).strip()
        for case in _load_message_note_cases(testdata_path=testdata_path)
        if str(case.get("id", "")).strip()
    ]


def _build_note_draft_from_case(use_case: dict) -> MessageNoteDraft:
    note = use_case.get("note", {}) if isinstance(use_case.get("note"), dict) else {}
    title = str(note.get("title", "")).strip()
    body = str(note.get("body", "")).strip()
    if not title or not body:
        raise AssertionError(f"Publish note use case is missing title/body: {use_case.get('id')}")
    topics = note.get("topics", [])
    if isinstance(topics, str):
        topics = [token for token in topics.split() if token]
    if not isinstance(topics, list):
        topics = []
    raw_location = note.get("location", "")
    location = "" if raw_location is None else str(raw_location).strip()
    album = str(note.get("album", "")).strip() or None
    raw_picture_index = note.get("picture_index", 1)
    try:
        picture_index = max(1, int(raw_picture_index))
    except (TypeError, ValueError):
        picture_index = 1
    picture_indexes = _normalize_picture_indexes(note.get("picture_indexes", ()))
    allow_comments = note.get("allow_comments", True)
    if isinstance(allow_comments, str):
        allow_comments = allow_comments.strip().lower() in {"1", "true", "yes", "y", "on", "是"}
    return MessageNoteDraft(
        title=title,
        body=body,
        topics=[str(topic).strip() for topic in topics if str(topic).strip()],
        location=location,
        album=album,
        picture_index=picture_index,
        picture_indexes=picture_indexes,
        allow_comments=bool(allow_comments),
    )


def _normalize_picture_indexes(raw_value) -> tuple[int, ...]:
    if raw_value in (None, ""):
        return ()
    if isinstance(raw_value, (int, float, str)):
        values = [raw_value]
    elif isinstance(raw_value, (list, tuple)):
        values = raw_value
    else:
        return ()
    indexes: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if index < 1 or index in seen:
            continue
        indexes.append(index)
        seen.add(index)
    return tuple(indexes)


def wait_for_message_note_form(driver: WebDriver, timeout: int = 30) -> str | None:
    return wait_for_any_accessibility_id_or_text(
        driver,
        NOTE_FORM_READY_IDS,
        NOTE_FORM_READY_TEXTS,
        timeout=timeout,
    )


def publish_message_note(
    driver: WebDriver,
    draft: MessageNoteDraft,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 60,
) -> str:
    with _note_profile("open-publisher"):
        open_message_note_publisher(driver, ios_config=ios_config, timeout=timeout)
    with _note_profile("fill-form"):
        fill_message_note_form(driver, draft, timeout=timeout)
    with _note_profile("submit-note"):
        return submit_message_note(driver, timeout=timeout)


def open_message_note_publisher(
    driver: WebDriver,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 30,
) -> None:
    end_at = time.monotonic() + timeout
    if ios_config is not None:
        try:
            from velowind_appium.session import ensure_logged_in_for_publish_entry

            ensure_logged_in_for_publish_entry(driver, ios_config)
        except Exception:
            pass
    _prepare_android_publish_entry(driver)

    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if login_required_from_page_source(page_source):
            if ios_config is None:
                raise AssertionError("Publish flow reached a login page but no iOS config was provided for re-login")
            ensure_logged_in_if_needed(driver, ios_config)
            end_at = time.monotonic() + timeout
            time.sleep(1)
            continue

        if message_note_form_is_visible(page_source):
            return

        if _note_type_visible(page_source) and _tap_note_type_if_present(driver):
            if _wait_until(lambda: message_note_form_is_visible(_safe_page_source(driver)), timeout=10):
                return

        if _tap_publish_entry_if_present(driver):
            time.sleep(0.5)
            _tap_note_type_if_present(driver)
            if _wait_until(lambda: message_note_form_is_visible(_safe_page_source(driver)), timeout=10):
                return
        time.sleep(0.5)

    raise AssertionError("Unable to open the message note publisher from the home page")


def _prepare_android_publish_entry(driver: WebDriver) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return
    for _ in range(5):
        page_source = _safe_page_source(driver)
        if _android_publish_entry_ready(page_source):
            return
        if _android_share_sheet_visible(page_source):
            if _tap_android_share_close(driver):
                time.sleep(0.4)
                continue
            if _android_adb_back(driver):
                time.sleep(0.4)
                continue
            driver.back()
            time.sleep(0.4)
            continue
        if _android_search_page_visible(page_source):
            if _tap_android_header_close(driver) or _android_adb_back(driver) or _tap_android_top_back(driver):
                time.sleep(0.4)
                continue
            driver.back()
            time.sleep(0.4)
            continue
        if _android_detail_page_visible(page_source) or _android_fullscreen_preview_visible(page_source):
            if _android_adb_back(driver) or _tap_android_top_back(driver):
                time.sleep(0.4)
                continue
            driver.back()
            time.sleep(0.4)
            continue
        _tap_home_tab_fast(driver)
        time.sleep(0.3)


def _android_publish_entry_ready(page_source: str) -> bool:
    return all(text in page_source for text in ["首页", "活动", "消息", "我的"]) and "搜索" not in page_source


def _tap_home_tab_fast(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {"x": int(rect["width"] * 0.12), "y": int(rect["height"] * 0.95)},
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _android_adb_back(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    udid = (
        str(capabilities.get("appium:udid") or capabilities.get("udid") or "").strip()
        or os.environ.get("VW_ANDROID_UDID", "").strip()
    )
    if not udid:
        return False
    try:
        subprocess.run(
            ["adb", "-s", udid, "shell", "input", "keyevent", "4"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def fill_message_note_form(driver: WebDriver, draft: MessageNoteDraft, timeout: int = 60) -> None:
    wait_for_message_note_form(driver, timeout=timeout)

    with _note_profile("upload-image"):
        _upload_note_image(driver, draft)
    with _note_profile("stabilize-form-after-upload"):
        _stabilize_android_note_form_after_upload(driver, timeout=min(timeout, 15))
    with _note_profile("fill-title"):
        _fill_note_title(driver, draft.title)
    with _note_profile("fill-body"):
        _fill_note_body(driver, draft.body)
    with _note_profile("append-topics"):
        _append_note_topics_to_body(driver, draft.topics)
    if draft.location:
        with _note_profile("fill-location"):
            _fill_note_location(driver, draft.location)
    with _note_profile("set-allow-comments"):
        _set_allow_comments(driver, draft.allow_comments)


def submit_message_note(driver: WebDriver, timeout: int = 30) -> str:
    _hide_keyboard(driver)
    if not _tap_note_submit(driver):
        raise AssertionError("Unable to find the publish action on the message note form")

    end_at = time.monotonic() + timeout
    last_source = ""
    submitted_again = False
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        last_source = page_source
        success_signal = message_note_publish_success_signal(page_source)
        if success_signal:
            return success_signal
        error_signal = message_note_publish_error_signal(page_source)
        if error_signal:
            raise AssertionError(f"Message note publish failed after submit: {error_signal}")
        if not message_note_form_is_visible(page_source) and message_detail_is_visible(driver):
            return "detail-page"
        if not submitted_again and message_note_form_is_visible(page_source):
            _hide_keyboard(driver)
            _tap_note_submit(driver)
            submitted_again = True
            time.sleep(0.5)
            continue
        if tap_text_if_present(driver, "确定", timeout=1) or tap_text_if_present(driver, "知道了", timeout=1):
            time.sleep(0.5)
        time.sleep(0.2)

    raise AssertionError(f"Message note publish did not expose a success signal after submit: {last_source[:500]}")


def message_note_form_is_visible(page_source: str) -> bool:
    texts = _extract_strings(page_source)
    joined = " ".join(texts)
    return any(token in joined for token in NOTE_FORM_READY_TEXTS)


def message_note_publish_success_signal(page_source: str) -> str | None:
    texts = _extract_strings(page_source)
    for token in NOTE_SUCCESS_TEXTS:
        if token in texts or token in page_source:
            return token
    for accessibility_id in NOTE_SUCCESS_IDS:
        if accessibility_id in page_source:
            return accessibility_id
    if "审核" in page_source and "成功" in page_source:
        return "审核成功提示"
    return None


def message_note_publish_error_signal(page_source: str) -> str | None:
    texts = _extract_strings(page_source)
    for token in NOTE_ERROR_TEXTS:
        if token in texts or token in page_source:
            return token
    if "http=500" in page_source or "服务器内部错误" in page_source:
        return "服务器内部错误"
    return None


def parse_detail_snapshot(page_source: str) -> MessageDetailSnapshot:
    texts = _extract_strings(page_source)
    title = _extract_title(texts)
    body = _extract_body(texts, title)
    view_count = _extract_count(page_source, texts, VIEW_COUNT_PATTERN, "浏览")
    comment_count = _extract_count(page_source, texts, COMMENT_COUNT_PATTERN, "评论")
    comments = _extract_comments(texts)
    empty_comment_hint = next((text for text in texts if "还没有评论" in text), None)
    bottom_action_counts = _extract_android_bottom_action_counts(page_source) or _extract_bottom_action_counts(texts)
    return MessageDetailSnapshot(
        title=title,
        body=body,
        view_count=view_count,
        comment_count=comment_count,
        comments=comments,
        empty_comment_hint=empty_comment_hint,
        bottom_action_counts=bottom_action_counts,
    )


def read_message_detail_snapshot(driver: WebDriver, timeout: int = 20) -> MessageDetailSnapshot:
    end_at = time.monotonic() + timeout
    last_snapshot = MessageDetailSnapshot(None, None, None, None, [], None, [])

    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if not page_source:
            time.sleep(0.2)
            continue

        snapshot = parse_detail_snapshot(page_source)
        last_snapshot = snapshot
        if _snapshot_is_detail_ready(snapshot):
            return snapshot
        time.sleep(0.2)

    raise AssertionError(f"Message detail did not expose all expected fields: {last_snapshot}")


def submit_message_comment(driver: WebDriver, comment_text: str, timeout: int = 20) -> None:
    before_snapshot = parse_detail_snapshot(_safe_page_source(driver))
    if not (
        _tap_candidate(driver, COMMENT_ENTRY_IDS, COMMENT_ENTRY_TEXTS)
        or _tap_bottom_action_at_index(driver, 2)
    ):
        raise AssertionError("Unable to open the comment entry point from message detail")

    input_box = _find_comment_input(driver, timeout=timeout)
    _enter_comment_text(driver, input_box, comment_text)

    if not _tap_candidate(driver, COMMENT_SUBMIT_IDS, COMMENT_SUBMIT_TEXTS):
        input_box.send_keys("\n")

    _wait_for_comment_echo(driver, comment_text, before_snapshot.comment_count, timeout=timeout)


def toggle_ticket_text_and_assert_change(driver: WebDriver, timeout: int = 15) -> tuple[list[str], list[str]]:
    before_source = _safe_page_source(driver)
    before = _extract_interaction_signature(before_source)

    if not _tap_bottom_action(driver):
        raise AssertionError("Unable to find a tappable bottom action icon in message detail")

    end_at = time.monotonic() + timeout
    after = before
    while time.monotonic() < end_at:
        after_source = _safe_page_source(driver)
        after = _extract_interaction_signature(after_source)
        if after and after != before:
            return before, after
        if after_source and after_source != before_source:
            return before, after
        time.sleep(0.2)

    raise AssertionError(f"Detail interaction state did not change. before={before}, after={after}")


def message_detail_is_visible(driver: WebDriver) -> bool:
    snapshot = parse_detail_snapshot(_safe_page_source(driver))
    return _snapshot_is_detail_ready(snapshot)


def browse_note_detail(driver: WebDriver, timeout: int = 20) -> MessageDetailSnapshot:
    snapshot = read_message_detail_snapshot(driver, timeout=timeout)
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    if is_android and (snapshot.view_count is None or snapshot.comment_count is None):
        swipe_vertical(driver, direction="up")
        end_at = time.monotonic() + timeout
        latest = snapshot
        while time.monotonic() < end_at:
            latest = parse_detail_snapshot(_safe_page_source(driver))
            if latest.view_count is not None and latest.comment_count is not None:
                return latest
            time.sleep(0.2)
        return latest
    return snapshot


def open_note_search(driver: WebDriver, timeout: int = 10) -> None:
    if _note_search_visible(_safe_page_source(driver)):
        return
    _prepare_android_search_entry(driver)
    if not _tap_note_search_entry(driver):
        raise AssertionError("Unable to find the note search entry")
    if not _wait_until(lambda: _note_search_visible(_safe_page_source(driver)), timeout=timeout):
        raise AssertionError("Note search page did not appear after tapping the search entry")


def search_notes(driver: WebDriver, keyword: str, timeout: int = 10) -> None:
    search_input = _find_note_search_input(driver, timeout=timeout)
    _replace_text(search_input, keyword)
    if not (
        _tap_android_search_submit(driver)
        or _tap_note_search_submit_by_coordinate(driver)
        or _tap_texts_now(driver, ["搜索", "Search"])
        or _tap_keyboard_search(driver)
    ):
        _hide_keyboard(driver)
    if not _wait_until(lambda: _note_search_results_visible(_safe_page_source(driver), keyword), timeout=timeout):
        raise AssertionError(f"Note search results did not appear for keyword: {keyword}")


def open_first_note_search_result(driver: WebDriver, timeout: int = 20) -> None:
    if message_detail_is_visible(driver):
        return
    if not _tap_first_note_search_result(driver):
        raise AssertionError("Unable to tap the first note search result")
    if not _wait_until(lambda: message_detail_is_visible(driver), timeout=timeout):
        raise AssertionError("First note search result did not open the detail page")


def like_note(driver: WebDriver, timeout: int = 15) -> tuple[list[str], list[str]]:
    return _toggle_bottom_action_and_wait_for_change(driver, action_index=0, timeout=timeout)


def favorite_note(driver: WebDriver, timeout: int = 15) -> tuple[list[str], list[str]]:
    return _toggle_bottom_action_and_wait_for_change(driver, action_index=1, timeout=timeout)


def share_note_to_moments(driver: WebDriver, timeout: int = 20) -> str:
    if not _tap_detail_share_button(driver):
        raise AssertionError("Unable to find the note share entry point")
    if not _wait_until(lambda: _share_sheet_visible(_safe_page_source(driver)), timeout=timeout):
        raise AssertionError("Share sheet did not appear after tapping the share entry point")
    if not _tap_share_target(driver, "朋友圈"):
        raise AssertionError("Unable to find the Moments share target")
    return "朋友圈"


def _tap_publish_entry_if_present(driver: WebDriver) -> bool:
    if _tap_publish_entry_by_coordinate(driver):
        return True
    for accessibility_id in PUBLISH_ENTRY_IDS:
        if _tap_accessibility_id_now(driver, accessibility_id):
            return True
    if _tap_texts_now(driver, PUBLISH_ENTRY_TEXTS):
        return True
    for xpath in [
        '//*[@name="发布" or @label="发布" or @value="发布"]',
        '//*[@name="+" or @label="+" or @value="+"]',
        '//*[@name="＋" or @label="＋" or @value="＋"]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    try:
        rect = driver.get_window_rect()
        driver.execute_script("mobile: tap", {"x": int(rect["width"] * 0.5), "y": int(rect["height"] * 0.93)})
        return True
    except WebDriverException:
        return False


def _prepare_android_search_entry(driver: WebDriver) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return
    for _ in range(4):
        page_source = _safe_page_source(driver)
        if _android_search_entry_ready(page_source):
            return
        if _android_share_sheet_visible(page_source):
            if _tap_android_share_close(driver):
                time.sleep(0.4)
                continue
            driver.back()
            time.sleep(0.4)
            continue
        if _android_fullscreen_preview_visible(page_source):
            if _tap_android_top_back(driver):
                time.sleep(0.4)
                continue
            driver.back()
            time.sleep(0.4)
            continue
        driver.back()
        time.sleep(0.3)


def _android_search_entry_ready(page_source: str) -> bool:
    return "全国" in page_source and "推荐" in page_source and "骑行" in page_source and "搜索" not in page_source


def _android_share_sheet_visible(page_source: str) -> bool:
    return any(text in page_source for text in ["选择分享方式", "微信好友", "朋友圈"])


def _android_search_page_visible(page_source: str) -> bool:
    return "android.widget.EditText" in page_source and 'text="搜索"' in page_source


def _android_detail_page_visible(page_source: str) -> bool:
    if any(text in page_source for text in ["写留言", "共 0 条评论", "地点 |", "浏览", "评论"]):
        return True
    if any(text in page_source for text in ["首页", "活动", "消息", "我的"]):
        return False
    if _android_search_page_visible(page_source) or _android_share_sheet_visible(page_source):
        return False
    return page_source.count('resource-id="image"') >= 3 and page_source.count('text="赞"') >= 1


def _android_fullscreen_preview_visible(page_source: str) -> bool:
    return (
        not _android_share_sheet_visible(page_source)
        and "android:id/content" in page_source
        and "post-home-feed-category-pager" not in page_source
        and "发布笔记" not in page_source
        and "登录" not in page_source
        and page_source.count('resource-id="image"') <= 1
    )


def _tap_android_share_close(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        for x_ratio, y_ratio in [(0.95, 0.81), (0.95, 0.84), (0.97, 0.81)]:
            driver.execute_script(
                "mobile: tap",
                {"x": int(rect["width"] * x_ratio), "y": int(rect["height"] * y_ratio)},
            )
            time.sleep(0.2)
            if not _android_share_sheet_visible(_safe_page_source(driver)):
                return True
        return False
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_android_top_back(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {"x": int(rect["width"] * 0.06), "y": int(rect["height"] * 0.09)},
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_publish_entry_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        capabilities = getattr(driver, "capabilities", {}) or {}
        platform = str(capabilities.get("platformName", "")).lower()
        x = int(rect["width"] * 0.5)
        if platform == "android":
            for y_ratio in (0.935, 0.948, 0.958, 0.968):
                driver.execute_script("mobile: tap", {"x": x, "y": int(rect["height"] * y_ratio)})
                if _wait_until(
                    lambda: _publish_entry_opened(_safe_page_source(driver)),
                    timeout=1,
                ):
                    return True
            return False
        driver.execute_script("mobile: tap", {"x": x, "y": int(rect["height"] * 0.93)})
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _publish_entry_opened(page_source: str) -> bool:
    return (
        message_note_form_is_visible(page_source)
        or _note_type_visible(page_source)
        or _android_share_sheet_visible(page_source)
    )


def _tap_note_search_entry(driver: WebDriver) -> bool:
    if _tap_note_search_entry_by_coordinate(driver) and _wait_until(
        lambda: _note_search_visible(_safe_page_source(driver)),
        timeout=1,
    ):
        return True
    for accessibility_id in NOTE_SEARCH_ENTRY_IDS:
        if _tap_accessibility_id_now(driver, accessibility_id):
            return True
    if _tap_texts_now(driver, NOTE_SEARCH_TEXTS):
        return True
    for text in NOTE_SEARCH_TEXTS:
        for xpath in [
            f'//*[@name="{text}" or @label="{text}" or @value="{text}"]',
            f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
        ]:
            try:
                driver.find_element(AppiumBy.XPATH, xpath).click()
                return True
            except (NoSuchElementException, WebDriverException):
                continue
    return False


def _tap_note_search_entry_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        capabilities = getattr(driver, "capabilities", {}) or {}
        platform = str(capabilities.get("platformName", "")).lower()
        if platform == "android":
            for x_ratio, y_ratio in [(0.93, 0.067), (0.91, 0.072), (0.95, 0.067)]:
                driver.execute_script(
                    "mobile: tap",
                    {
                        "x": int(rect["width"] * x_ratio),
                        "y": int(rect["height"] * y_ratio),
                    },
                )
                if _wait_until(lambda: _note_search_visible(_safe_page_source(driver)), timeout=0.8):
                    return True
            return False
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.90),
                "y": int(rect["height"] * 0.11),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _note_search_visible(page_source: str) -> bool:
    if "搜索" not in page_source:
        return False
    return any(token in page_source for token in ["请输入内容", "取消", "综合", "笔记", "用户", "Search"])


def _find_note_search_input(driver: WebDriver, timeout: int = 10):
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        for xpath in NOTE_SEARCH_INPUT_XPATHS:
            try:
                return driver.find_element(AppiumBy.XPATH, xpath)
            except (NoSuchElementException, WebDriverException):
                continue
        time.sleep(0.2)
    raise AssertionError("Unable to locate the note search input")


def _tap_keyboard_search(driver: WebDriver) -> bool:
    for kwargs in [
        {"key_name": "Search"},
        {"key_name": "Return"},
        {"strategy": "pressKey", "key_name": "Search"},
    ]:
        try:
            driver.hide_keyboard(**kwargs)
            return True
        except WebDriverException:
            continue
    return False


def _tap_note_search_submit_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        capabilities = getattr(driver, "capabilities", {}) or {}
        if str(capabilities.get("platformName", "")).lower() == "android":
            for x_ratio, y_ratio in [(0.90, 0.073), (0.93, 0.073), (0.90, 0.09)]:
                driver.execute_script(
                    "mobile: tap",
                    {
                        "x": int(rect["width"] * x_ratio),
                        "y": int(rect["height"] * y_ratio),
                    },
                )
                time.sleep(0.2)
                if _android_search_request_started(_safe_page_source(driver)):
                    return True
            return False
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.90),
                "y": int(rect["height"] * 0.11),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _note_search_results_visible(page_source: str, keyword: str) -> bool:
    if not page_source:
        return False
    if any(token in page_source for token in ["暂无", "没有找到", "无结果"]):
        return False
    if "<android." in page_source:
        return _android_search_results_visible(page_source, keyword)
    from velowind_appium.modules.home_feed import note_feed_contains_type_results

    return note_feed_contains_type_results(page_source, keyword)


def _tap_android_search_submit(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    for xpath in [
        '//android.widget.TextView[@text="搜索"]',
        '//android.view.ViewGroup[.//android.widget.TextView[@text="搜索"]]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException):
            continue
        if _tap_element_center(driver, element):
            time.sleep(0.2)
            if _android_search_request_started(_safe_page_source(driver)):
                return True
        try:
            element.click()
        except WebDriverException:
            continue
        time.sleep(0.2)
        if _android_search_request_started(_safe_page_source(driver)):
            return True
    return False


def _android_search_request_started(page_source: str) -> bool:
    return "请输入内容" in page_source or "推荐" in page_source or 'resource-id="post-home-feed-category-pager"' in page_source


def _android_search_results_visible(page_source: str, keyword: str) -> bool:
    if "android.widget.EditText" not in page_source or f'text="{keyword}"' not in page_source:
        return False
    try:
        from xml.etree import ElementTree

        root = ElementTree.fromstring(page_source)
    except Exception:
        return False

    visible_titles = 0
    visible_images = 0
    for element in root.iter():
        rect = _android_bounds_to_rect(element.attrib.get("bounds", ""))
        if rect is None:
            continue
        _, top, width, height = rect
        if top < 260:
            continue
        if element.tag == "android.widget.ImageView" and element.attrib.get("resource-id") == "image" and width >= 200 and height >= 200:
            visible_images += 1
        if element.tag == "android.widget.TextView":
            text = element.attrib.get("text", "").strip()
            if len(text) >= 4 and text not in {"搜索", keyword, "推荐", "骑行", "徒步", "滑雪", "登山", "赞"} and not text.startswith("#"):
                visible_titles += 1
    return visible_images >= 1 and visible_titles >= 1


def _android_bounds_to_rect(bounds: str) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", bounds)
    if not match:
        return None
    left, top, right, bottom = (int(value) for value in match.groups())
    return left, top, right - left, bottom - top


def _tap_first_note_search_result(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        if _tap_first_android_note_search_result(driver):
            return True
    verify_open = lambda: message_detail_is_visible(driver)
    page_source = _safe_page_source(driver)
    if tap_first_note_card(
        driver,
        page_source=page_source,
        verify_open=verify_open,
        timeout=0.7,
    ):
        return True
    if _tap_first_note_search_result_by_coordinate(driver) and _wait_until(verify_open, timeout=0.8):
        return True
    swipe_vertical(driver, direction="up")
    time.sleep(0.2)
    page_source = _safe_page_source(driver)
    if tap_first_note_card(
        driver,
        page_source=page_source,
        verify_open=verify_open,
        timeout=0.7,
    ):
        return True
    if _tap_first_note_search_result_by_coordinate(driver) and _wait_until(verify_open, timeout=0.8):
        return True
    for accessibility_id in NOTE_SEARCH_RESULT_IDS:
        if _tap_accessibility_id_now(driver, accessibility_id):
            return True
    if _tap_first_visible_note_search_result(driver):
        return True
    if _tap_first_note_search_result_by_coordinate(driver):
        return True
    for xpath in [
        "(//XCUIElementTypeCollectionView//XCUIElementTypeCell)[1]",
        "(//XCUIElementTypeCollectionView//XCUIElementTypeButton)[1]",
        "(//XCUIElementTypeTable//XCUIElementTypeCell)[1]",
        "(//XCUIElementTypeTable//XCUIElementTypeButton)[1]",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _tap_first_android_note_search_result(driver: WebDriver) -> bool:
    for x_ratio, y_ratio in [(0.10, 0.35), (0.10, 0.28), (0.17, 0.40)]:
        if _tap_android_ratio_by_adb(driver, x_ratio, y_ratio) and _wait_until(
            lambda: message_detail_is_visible(driver),
            timeout=2.2,
        ):
            return True
    for xpath in [
        '(//android.widget.ImageView[@resource-id="image"])[1]',
        '(//android.widget.ImageView[@resource-id="image"])[2]',
        '(//android.widget.TextView[@text="亲子骑行"])[1]',
        '(//android.widget.TextView[contains(@text, "骑行")])[1]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException):
            continue
        if _tap_element_center(driver, element) and _wait_until(lambda: message_detail_is_visible(driver), timeout=2):
            return True
        try:
            element.click()
        except WebDriverException:
            pass
        if _wait_until(lambda: message_detail_is_visible(driver), timeout=2):
            return True
    return _tap_first_note_search_result_by_coordinate(driver)


def _tap_element_center(driver: WebDriver, element) -> bool:
    try:
        rect = element.rect
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["x"] + rect["width"] / 2),
                "y": int(rect["y"] + rect["height"] / 2),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        try:
            return _adb_tap_point(
                driver,
                int(rect["x"] + rect["width"] / 2),
                int(rect["y"] + rect["height"] / 2),
            )
        except Exception:
            return False
    return False


def _adb_tap_point(driver: WebDriver, x: int, y: int) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    udid = str(capabilities.get("udid") or capabilities.get("appium:udid") or "").strip()
    if not udid:
        return False
    try:
        subprocess.run(
            ["adb", "-s", udid, "shell", "input", "tap", str(x), str(y)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _tap_android_ratio_by_adb(driver: WebDriver, x_ratio: float, y_ratio: float) -> bool:
    try:
        rect = driver.get_window_rect()
        return _adb_tap_point(driver, int(rect["width"] * x_ratio), int(rect["height"] * y_ratio))
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_first_visible_note_search_result(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if not page_source:
        return False
    card_rect = _first_note_search_result_card_rect_from_source(page_source)
    title_candidate = _first_note_search_result_title_from_source(page_source)
    if title_candidate is not None:
        title, _ = title_candidate
        if _click_note_search_result_title(driver, title):
            return True
    title_rect = title_candidate[1] if title_candidate is not None else None
    points: list[tuple[int, int]] = []
    if card_rect is not None:
        x, y, width, height = card_rect
        points.extend(
            [
                (x + max(1, width // 2), y + int(height * 0.62)),
                (x + max(1, width // 2), y + min(120, max(24, height // 3))),
                (x + max(1, width // 2), min(y + height - 28, y + 300)),
            ]
        )
    if title_rect is not None:
        x, y, width, height = title_rect
        points.extend(
            [
                (x + max(1, width // 2), y + max(1, height // 2)),
                (x + max(1, width // 2), max(130, y - min(90, max(20, y - 130)))),
            ]
        )
    return _tap_note_search_result_points(driver, _dedupe_points(points))


def _first_note_search_result_card_rect_from_source(page_source: str) -> tuple[int, int, int, int] | None:
    rects: list[tuple[int, int, int, int]] = []
    for tag in re.findall(r"<XCUIElementTypeOther\b[^>]*>", page_source):
        attrs = _xml_tag_attrs(tag)
        text = attrs.get("name") or attrs.get("label") or attrs.get("value") or ""
        rect = _rect_from_attrs(attrs)
        if rect is None:
            continue
        x, y, width, height = rect
        if _looks_like_note_search_result_card(text, x, y, width, height):
            rects.append(rect)
    return sorted(rects, key=lambda item: (item[0], item[1]))[0] if rects else None


def _first_note_search_result_title_from_source(page_source: str) -> tuple[str, tuple[int, int, int, int]] | None:
    candidates: list[tuple[int, int, str, tuple[int, int, int, int]]] = []
    for tag in re.findall(r"<XCUIElementTypeStaticText\b[^>]*>", page_source):
        attrs = _xml_tag_attrs(tag)
        text = attrs.get("name") or attrs.get("label") or attrs.get("value") or ""
        rect = _rect_from_attrs(attrs)
        if rect is None:
            continue
        x, y, width, height = rect
        if _looks_like_note_search_result_title(text, x, y, width, height):
            candidates.append((y, x, text, rect))
    if not candidates:
        return None
    _, _, text, rect = sorted(candidates, key=lambda item: (item[1], item[0]))[0]
    return text, rect


def _click_note_search_result_title(driver: WebDriver, title: str) -> bool:
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    for xpath in [
        f'//XCUIElementTypeStaticText[@name="{escaped_title}" or @label="{escaped_title}" or @value="{escaped_title}"]',
        f'//*[contains(@name, "{escaped_title}") or contains(@label, "{escaped_title}") or contains(@value, "{escaped_title}")]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
        except (NoSuchElementException, WebDriverException):
            continue
        if _wait_until(lambda: message_detail_is_visible(driver), timeout=1.5):
            return True
    return False


def _xml_tag_attrs(tag: str) -> dict[str, str]:
    return {key: html.unescape(value) for key, value in re.findall(r'(\w+)="([^"]*)"', tag)}


def _rect_from_attrs(attrs: dict[str, str]) -> tuple[int, int, int, int] | None:
    try:
        return (
            int(float(attrs.get("x", "0"))),
            int(float(attrs.get("y", "0"))),
            int(float(attrs.get("width", "0"))),
            int(float(attrs.get("height", "0"))),
        )
    except ValueError:
        return None


def _dedupe_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    deduped: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for point in points:
        if point in seen:
            continue
        seen.add(point)
        deduped.append(point)
    return deduped


def _looks_like_note_search_result_card(text: str, x: int, y: int, width: int, height: int) -> bool:
    if y < 120 or width < 150 or width > 220 or height < 70:
        return False
    if not text or "用户" not in text:
        return False
    if "赞" not in text and not re.search(r"\s\d+\s*$", text):
        return False
    if "首页 活动 消息 我的" in text or "Vertical scroll bar" in text:
        return False
    if text.startswith("用户 "):
        return False
    return 0 <= x <= 430


def _tap_note_search_result_points(driver: WebDriver, points: list[tuple[int, int]]) -> bool:
    for x, y in points:
        for script, payload in [
            ("mobile: tap", {"x": x, "y": y}),
            ("mobile: doubleTap", {"x": x, "y": y}),
            ("mobile: touchAndHold", {"x": x, "y": y, "duration": 0.1}),
        ]:
            try:
                driver.execute_script(script, payload)
            except WebDriverException:
                continue
            if _wait_until(lambda: message_detail_is_visible(driver), timeout=1.2):
                return True
    return False


def _looks_like_note_search_result_title(text: str, x: int, y: int, width: int, height: int) -> bool:
    if y < 120 or width < 80 or height < 12:
        return False
    if not text or len(text) < 6:
        return False
    if text in GENERIC_DETAIL_TEXTS or text in {"全国", "推荐", "关注", "赞", "用户"}:
        return False
    if text.startswith("#") or text.startswith("用户"):
        return False
    if re.fullmatch(r"[0-9a-f]{16,}", text):
        return False
    if any(token in text for token in ["Vertical scroll bar", "首页 活动 消息 我的"]):
        return False
    # Search cards in the current app use two waterfall columns; keep the tap within those columns.
    return 0 <= x <= 430


def _tap_first_note_search_result_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        capabilities = getattr(driver, "capabilities", {}) or {}
        if str(capabilities.get("platformName", "")).lower() == "android":
            for x_ratio, y_ratio in [
                (0.10, 0.35),
                (0.14, 0.30),
                (0.10, 0.28),
                (0.17, 0.40),
                (0.22, 0.52),
                (0.45, 0.30),
                (0.50, 0.40),
            ]:
                driver.execute_script(
                    "mobile: tap",
                    {
                        "x": int(rect["width"] * x_ratio),
                        "y": int(rect["height"] * y_ratio),
                    },
                )
                if _wait_until(lambda: message_detail_is_visible(driver), timeout=1.5):
                    return True
            return False
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * 0.25),
                "y": int(rect["height"] * 0.38),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_note_type_if_present(driver: WebDriver) -> bool:
    for accessibility_id in NOTE_TYPE_IDS:
        if _tap_accessibility_id_now(driver, accessibility_id):
            return True
    if _tap_texts_now(driver, NOTE_TYPE_TEXTS):
        return True
    for text in NOTE_TYPE_TEXTS:
        for xpath in [
            f'//*[@name="{text}" or @label="{text}" or @value="{text}"]',
            f'//*[contains(@name, "{text}") or contains(@label, "{text}") or contains(@value, "{text}")]',
        ]:
            try:
                driver.find_element(AppiumBy.XPATH, xpath).click()
                return True
            except (NoSuchElementException, WebDriverException):
                continue
    return False


def _note_type_visible(page_source: str) -> bool:
    return any(text in page_source for text in NOTE_TYPE_TEXTS)


def _tap_accessibility_id_now(driver: WebDriver, accessibility_id: str) -> bool:
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_texts_now(driver: WebDriver, texts: list[str]) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        return any(tap_text_if_present(driver, text, timeout=1) for text in texts)

    escaped_texts = [text.replace("\\", "\\\\").replace('"', '\\"') for text in texts]
    quoted = ", ".join(f'"{text}"' for text in escaped_texts)
    predicate = f"name IN {{{quoted}}} OR label IN {{{quoted}}} OR value IN {{{quoted}}}"
    try:
        driver.find_element(AppiumBy.IOS_PREDICATE, predicate).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _fill_note_title(driver: WebDriver, title: str) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    attempts = 2 if is_android else 1
    for attempt in range(attempts):
        for keyword in TITLE_FIELD_KEYWORDS:
            if _fill_input_near_label(driver, keyword, title):
                return
        if is_android and attempt + 1 < attempts:
            wait_for_message_note_form(driver, timeout=5)
            time.sleep(0.5)
    for xpath in [
        '//XCUIElementTypeTextField[contains(@value, "标题")]',
        "//XCUIElementTypeTextField[1]",
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), title)
            _hide_keyboard(driver)
            return
        except (NoSuchElementException, WebDriverException):
            continue
    raise AssertionError("Unable to locate the note title input")


def _stabilize_android_note_form_after_upload(driver: WebDriver, timeout: int) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        wait_for_message_note_form(driver, timeout=timeout)
        return

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if message_note_form_is_visible(page_source):
            return
        if "publish-note-image-picker-cropper-viewport" in page_source or "确认裁剪" in page_source:
            _force_confirm_android_cropper(driver)
            time.sleep(0.5)
            continue
        time.sleep(0.2)

    wait_for_message_note_form(driver, timeout=1)


def _force_confirm_android_cropper(driver: WebDriver) -> bool:
    for point in [(1059, 2398), (1173, 2398), (970, 2398)]:
        if not _adb_input_tap(driver, *point):
            continue
        if _wait_until(lambda: message_note_form_is_visible(_safe_page_source(driver)), timeout=5):
            return True
        time.sleep(0.5)
    return False


def _adb_input_tap(driver: WebDriver, x: int, y: int) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    udid = (
        str(capabilities.get("appium:udid") or capabilities.get("udid") or "").strip()
        or os.environ.get("VW_ANDROID_UDID", "").strip()
    )
    if not udid:
        return False
    try:
        result = subprocess.run(
            ["adb", "-s", udid, "shell", "input", "tap", str(x), str(y)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _fill_note_body(driver: WebDriver, body: str) -> None:
    for keyword in BODY_FIELD_KEYWORDS:
        if _fill_input_near_label(driver, keyword, body, prefer_text_view=True):
            return
    for xpath in [
        '//XCUIElementTypeTextView[contains(@value, "正文") or contains(@value, "分享") or contains(@value, "内容")]',
        "//XCUIElementTypeTextView[1]",
        "(//XCUIElementTypeTextField)[2]",
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), body)
            _hide_keyboard(driver)
            return
        except (NoSuchElementException, WebDriverException):
            continue
    raise AssertionError("Unable to locate the note body input")


def _upload_note_image(driver: WebDriver, draft: MessageNoteDraft) -> None:
    with _note_profile("upload-clear-existing-images"):
        _clear_existing_note_images(driver)
    picture_indexes = _normalize_picture_indexes(draft.picture_indexes)
    expected_count = len(picture_indexes)
    first_picture_index = picture_indexes[0] if picture_indexes else draft.picture_index

    photo_chosen = _choose_note_image_from_library(
        driver,
        album_name=draft.album,
        picture_index=first_picture_index,
        picture_indexes=picture_indexes,
        select_all_from_album=bool(picture_indexes),
    )
    if not photo_chosen:
        raise AssertionError(
            "Photo library opened but no selectable photo was found. "
            "If this is a simulator, seed at least one image into Photos."
        )

    if not picture_indexes:
        return

    if _wait_for_note_selected_image_count(driver, expected_count):
        return

    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return

    current_count = _note_selected_image_count(driver)
    for picture_index in picture_indexes[current_count:]:
        if not _choose_note_image_from_library(
            driver,
            album_name=draft.album,
            picture_index=picture_index,
            picture_indexes=(),
            select_all_from_album=False,
        ):
            break
        if _wait_for_note_selected_image_count(driver, expected_count):
            return
    raise AssertionError(f"Expected {expected_count} note images after upload, got {_note_selected_image_count(driver)}")


def _choose_note_image_from_library(
    driver: WebDriver,
    *,
    album_name: str | None,
    picture_index: int,
    picture_indexes: tuple[int, ...],
    select_all_from_album: bool,
) -> bool:
    with _note_profile("upload-tap-image-plus"):
        image_plus_tapped = _tap_note_image_plus(driver)
    if not image_plus_tapped:
        raise AssertionError("Unable to find the note image plus button")

    kwargs = {
        "album_name": album_name,
        "picture_index": picture_index,
        "select_all_from_album": select_all_from_album,
        "retry_sheet_option": _tap_note_photo_library_sheet_option,
    }
    if picture_indexes:
        kwargs["picture_indexes"] = picture_indexes
    with _note_profile("upload-choose-photo-library"):
        return photo_picker.choose_photo_from_library(driver, **kwargs)


def _tap_note_photo_library_sheet_option(driver: WebDriver) -> bool:
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


def _clear_existing_note_images(driver: WebDriver, max_images: int = 9) -> None:
    page_source = _safe_page_source(driver)
    if not message_note_form_is_visible(page_source):
        return
    if not _note_selected_images_hint(page_source):
        return
    for _ in range(max_images):
        remove_buttons = _find_note_image_remove_buttons(driver)
        if not remove_buttons:
            return
        before_count = len(remove_buttons)
        if not _tap_note_image_remove_button(driver, remove_buttons[-1]):
            return
        if not _wait_until(lambda: len(_find_note_image_remove_buttons(driver)) < before_count, timeout=2):
            return


def _note_selected_image_count(driver: WebDriver) -> int:
    return len(_find_note_image_remove_buttons(driver))


def _wait_for_note_selected_image_count(driver: WebDriver, expected_count: int, timeout: int = 8) -> bool:
    return _wait_until(lambda: _note_selected_image_count(driver) >= expected_count, timeout=timeout)


def _note_selected_images_hint(page_source: str) -> bool:
    if 'resource-id="image"' in page_source and "发布笔记" in page_source:
        return True
    return any(text in page_source for text in ["删除图片", "移除图片", "删除", "移除", "已选择"])


def _find_note_image_remove_buttons(driver: WebDriver) -> list:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        return _find_android_note_image_remove_buttons(driver)
    try:
        candidates = driver.find_elements(AppiumBy.XPATH, "//XCUIElementTypeOther")
    except (AttributeError, WebDriverException):
        return []

    remove_buttons = []
    seen: set[tuple[float, float, float, float]] = set()
    for element in candidates:
        rect = getattr(element, "rect", {}) or {}
        x = float(rect.get("x", 0) or 0)
        y = float(rect.get("y", 0) or 0)
        width = float(rect.get("width", 0) or 0)
        height = float(rect.get("height", 0) or 0)
        if not (12 <= width <= 24 and 12 <= height <= 24):
            continue
        if not (120 <= y <= 180 and 70 <= x <= 390):
            continue
        key = (x, y, width, height)
        if key in seen:
            continue
        seen.add(key)
        remove_buttons.append(element)
    remove_buttons.sort(key=lambda element: ((getattr(element, "rect", {}) or {}).get("x", 0)))
    return remove_buttons


def _find_android_note_image_remove_buttons(driver: WebDriver) -> list:
    try:
        candidates = driver.find_elements(
            AppiumBy.XPATH,
            "//android.widget.HorizontalScrollView//android.view.ViewGroup",
        )
    except (AttributeError, WebDriverException):
        return []

    remove_buttons = []
    seen: set[tuple[float, float, float, float]] = set()
    for element in candidates:
        rect = getattr(element, "rect", {}) or {}
        x = float(rect.get("x", 0) or 0)
        y = float(rect.get("y", 0) or 0)
        width = float(rect.get("width", 0) or 0)
        height = float(rect.get("height", 0) or 0)
        if not (40 <= width <= 90 and 40 <= height <= 90):
            continue
        if not (250 <= y <= 450):
            continue
        if x < 250:
            continue
        key = (x, y, width, height)
        if key in seen:
            continue
        seen.add(key)
        remove_buttons.append(element)
    remove_buttons.sort(key=lambda element: ((getattr(element, "rect", {}) or {}).get("x", 0)))
    return remove_buttons


def _tap_note_image_remove_button(driver: WebDriver, element) -> bool:
    if _tap_element_center(driver, element):
        return True
    try:
        element.click()
        return True
    except WebDriverException:
        return False


def _append_note_topics_to_body(driver: WebDriver, topics: list[str]) -> None:
    if not topics:
        return
    if not (_tap_text_or_contains(driver, "#话题") or _tap_text_or_contains(driver, "话题")):
        raise AssertionError("Unable to find the #topic action on the note editor")

    for xpath in [
        '//android.widget.EditText[contains(@hint, "正文")]',
        "//XCUIElementTypeTextView[1]",
        '(//XCUIElementTypeTextField)[2]',
        '//XCUIElementTypeTextView[contains(@value, "长白山") or contains(@value, "正文") or contains(@value, "分享")]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            existing_body = _text_input_current_value(element)
            missing_topics = [topic for topic in topics if topic not in existing_body]
            combined_body = existing_body.rstrip()
            if missing_topics:
                topic_text = " ".join(missing_topics)
                combined_body = f"{combined_body} {topic_text}".strip()
            _replace_text(element, combined_body)
            _dismiss_editor_keyboard(driver)
            return
        except (NoSuchElementException, WebDriverException):
            continue
    raise AssertionError("Unable to append topics to the note body")


def _text_input_current_value(element) -> str:
    placeholder_values = {
        "正文",
        "添加正文",
        "输入正文",
        "请输入正文",
        "分享正文",
        "分享你的正文",
        "分享你的内容",
    }
    for attribute in ["text", "value", "name", "label"]:
        try:
            value = element.get_attribute(attribute)
        except (AttributeError, WebDriverException):
            continue
        text = str(value or "").strip()
        if not text:
            continue
        if text in placeholder_values:
            continue
        if text.startswith(("请输入", "添加")) and "正文" in text:
            continue
        return text
    return ""


def _tap_note_image_plus(driver: WebDriver) -> bool:
    if _tap_note_image_plus_by_coordinate(driver):
        return True
    for accessibility_id in [
        "note-image-add",
        "note-photo-add",
        "post-image-add",
        "publish-image-add",
    ]:
        if tap_if_present(driver, accessibility_id, timeout=1):
            return True
    for text in ["添加图片", "上传图片", "+", "＋"]:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    for xpath in [
        '//*[@name="+" or @label="+" or @value="+"]',
        '//*[@name="＋" or @label="＋" or @value="＋"]',
        '//XCUIElementTypeOther[contains(@name, "添加图片") or contains(@label, "添加图片")]',
        "//XCUIElementTypeOther[@x='13' and @y='161' and @width='94' and @height='94']",
        "//XCUIElementTypeOther[@x='25' and @y='115' and @width='101' and @height='100']",
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    try:
        driver.execute_script("mobile: tap", {"x": 60, "y": 206})
        return True
    except WebDriverException:
        return False


def _tap_note_image_plus_by_coordinate(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        try:
            candidates = driver.find_elements(
                AppiumBy.XPATH,
                "//android.widget.HorizontalScrollView//android.view.ViewGroup",
            )
        except (AttributeError, WebDriverException):
            candidates = []
        for candidate in candidates:
            rect = getattr(candidate, "rect", {}) or {}
            width = float(rect.get("width", 0) or 0)
            height = float(rect.get("height", 0) or 0)
            if width < 100 or height < 100:
                continue
            if not 0.75 <= width / height <= 1.25:
                continue
            if _tap_element_center(driver, candidate):
                return True
        return False

    try:
        driver.execute_script("mobile: tap", {"x": 60, "y": 206})
        return True
    except WebDriverException:
        return False


def _choose_photo_library_source(driver: WebDriver) -> bool:
    source_texts = ["从手机相册选择", "手机相册", "从相册选择", "相册"]
    if _tap_photo_source_option(driver, source_texts):
        return True
    for text in source_texts:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.5,
                "y": size["height"] * 0.87,
            },
        )
        return True
    except WebDriverException:
        return False


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


def _photo_library_visible(driver: WebDriver, timeout: int = 5) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if any(text in page_source for text in ["最近项目", "照片图库", "所有照片", "照片", "选择项目"]):
            return True
        for xpath in [
            "(//XCUIElementTypeCell)[1]",
            "(//XCUIElementTypeImage)[1]",
        ]:
            try:
                driver.find_element(AppiumBy.XPATH, xpath)
                return True
            except (NoSuchElementException, WebDriverException, AttributeError):
                continue
        time.sleep(0.2)
    return False


def _choose_local_photo(driver: WebDriver, *, picture_index: int = 1, album_name: str | None = None) -> bool:
    normalized_index = max(1, picture_index)
    if album_name and not _open_photo_album(driver, album_name):
        return False
    if album_name:
        if not _select_all_album_photos(driver):
            return False
        return _confirm_system_photo_picker_selection(driver)

    if _tap_photo_grid_candidate(driver, normalized_index):
        if _confirm_note_image_cropper(driver):
            return True
        return _confirm_system_photo_picker_selection(driver)
    return False


def _open_photo_album(driver: WebDriver, album_name: str) -> bool:
    if _photo_album_title(driver) == album_name:
        return True
    if not _switch_photo_picker_to_collections(driver):
        return False
    for _ in range(4):
        if _tap_named_element_center(driver, album_name):
            time.sleep(0.5)
            if _photo_album_title(driver) == album_name:
                return True
        try:
            swipe_vertical(driver, direction="up")
        except WebDriverException:
            pass
        time.sleep(0.3)
    return False


def _tap_photo_grid_candidate(driver: WebDriver, picture_index: int) -> bool:
    candidates = _find_photo_grid_candidates(driver)
    if not candidates:
        return False
    target_index = min(max(1, picture_index), len(candidates)) - 1
    rect = _rect_snapshot(candidates[target_index])
    if rect is None:
        return False
    return _tap_rect_center(driver, rect)


def _select_all_album_photos(driver: WebDriver) -> bool:
    if _tap_all_photo_grid_selection_badges(driver):
        return True
    return _tap_all_photo_grid_candidates(driver)


def _tap_all_photo_grid_selection_badges(driver: WebDriver) -> bool:
    badges = _find_photo_grid_selection_badges(driver)
    rects = [rect for rect in (_rect_snapshot(badge) for badge in badges) if rect is not None]
    tapped_any = False
    for rect in rects:
        if _tap_rect_center(driver, rect):
            tapped_any = True
            time.sleep(0.2)
    return tapped_any


def _find_photo_grid_selection_badges(driver: WebDriver) -> list:
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
    candidates = _find_photo_grid_candidates(driver)
    rects = [rect for rect in (_rect_snapshot(candidate) for candidate in candidates) if rect is not None]
    tapped_any = False
    for rect in rects:
        if _tap_rect_center(driver, rect):
            tapped_any = True
            time.sleep(0.2)
    return tapped_any


def _find_photo_grid_candidates(driver: WebDriver) -> list:
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


def _photo_album_title(driver: WebDriver) -> str | None:
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


def _switch_photo_picker_to_collections(driver: WebDriver) -> bool:
    if _photo_album_title(driver) not in {None, "选择最多9张照片。"}:
        return True
    if not _tap_text_or_contains(driver, "精选集"):
        return False
    time.sleep(0.5)
    return True


def _confirm_note_image_cropper(driver: WebDriver, timeout: int = 10) -> bool:
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


def _confirm_system_photo_picker_selection(driver: WebDriver, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if any(text in page_source for text in ["选择最多", "1张照片", "照片"]):
            tapped_done = False
            for accessibility_id in ["Add"]:
                if _tap_accessibility_id_now(driver, accessibility_id):
                    tapped_done = True
                    break
            if not tapped_done:
                for text in ["完成", "添加"]:
                    if _tap_text_or_contains(driver, text):
                        tapped_done = True
                        break
            if tapped_done:
                return _wait_until(lambda: _photo_picker_transition_completed(driver), timeout=10)
        time.sleep(0.2)
    return False


def _cropper_visible(page_source: str) -> bool:
    return any(pattern in page_source for pattern in CROPPER_VISIBLE_PATTERNS)


def _photo_picker_transition_completed(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if _cropper_visible(page_source):
        if getattr(driver, "_cropper_confirmed_once", False):
            return True
        return _confirm_note_image_cropper(driver, timeout=5)
    return not any(text in page_source for text in ["选择最多9张照片。", 'name="Add" label="完成"'])


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


def _fill_note_location(driver: WebDriver, location: str) -> None:
    if _should_skip_note_location(location):
        return
    _prepare_note_location_section(driver)
    if _open_note_location_picker(driver):
        if _choose_note_location_option(driver, location):
            return
        if _choose_note_location_option(driver, location):
            return
    raise AssertionError("Unable to select a note location option")


def _should_skip_note_location(location: str) -> bool:
    normalized = (location or "").strip()
    return normalized in {"", "不标记地点", "none", "skip"}


def _open_note_location_picker(driver: WebDriver) -> bool:
    for text in ["不标记地点", "标记地点", "地点"]:
        if _tap_text_or_contains(driver, text):
            return True
    return False


def _prepare_note_location_section(driver: WebDriver) -> None:
    _dismiss_editor_keyboard(driver)
    page_source = _safe_page_source(driver)
    if _cropper_visible(page_source):
        raise AssertionError("Unable to prepare note location while the image cropper is visible")
    if _location_section_visible(page_source):
        return
    for _ in range(3):
        _dismiss_editor_keyboard(driver)
        page_source = _safe_page_source(driver)
        if _cropper_visible(page_source):
            raise AssertionError("Unable to prepare note location while the image cropper is visible")
        if _location_section_visible(page_source):
            return
        try:
            swipe_vertical(driver, direction="up")
        except WebDriverException:
            pass
        time.sleep(0.3)
        page_source = _safe_page_source(driver)
        if _cropper_visible(page_source):
            raise AssertionError("Unable to prepare note location while the image cropper is visible")
        if _location_section_visible(page_source):
            return


def _location_section_visible(page_source: str) -> bool:
    return any(pattern in page_source for pattern in LOCATION_SECTION_VISIBLE_PATTERNS)


def _choose_note_location_option(driver: WebDriver, location: str) -> bool:
    if _location_picker_visible(_safe_page_source(driver)):
        if _search_note_location_from_picker(driver, location):
            return _choose_first_valid_location_from_picker(driver)
        return _choose_first_valid_location_from_picker(driver)

    option_elements = _find_visible_location_option_elements(driver)
    if not option_elements:
        return False

    for element in option_elements:
        if _tap_element_center(driver, element):
            return True
    return False


def _location_picker_visible(page_source: str) -> bool:
    if "android.widget.EditText" in page_source and "搜索地点" in page_source:
        return True
    return any(pattern in page_source for pattern in LOCATION_PICKER_VISIBLE_PATTERNS)


def _search_note_location_from_picker(driver: WebDriver, location: str) -> bool:
    normalized = (location or "").strip()
    if not normalized:
        return False
    search_input = _find_location_search_input(driver)
    if search_input is None:
        return False
    try:
        _replace_text(search_input, normalized)
    except WebDriverException:
        return False
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        _hide_keyboard(driver)
        _tap_text_or_contains(driver, "搜索")
    time.sleep(0.5)
    return True


def _find_location_search_input(driver: WebDriver):
    for xpath in [
        '//android.widget.EditText[contains(@hint, "搜索地点") or contains(@text, "搜索地点")]',
        '//*[@name="搜索地点" or @label="搜索地点" or @value="搜索地点"]',
        '//*[contains(@name, "搜索地点") or contains(@label, "搜索地点") or contains(@value, "搜索地点")]',
        '//XCUIElementTypeTextField[contains(@value, "搜索")]',
        '//XCUIElementTypeSearchField',
    ]:
        try:
            return driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException):
            continue
    return None


def _choose_first_valid_location_from_picker(driver: WebDriver) -> bool:
    result_elements = _find_location_result_elements(driver)
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    for element in result_elements:
        if _tap_location_result(driver, element) and _wait_until(
            lambda: not _location_picker_visible(_safe_page_source(driver)),
            timeout=5,
        ):
            return True
        if not is_android:
            continue
        for refreshed_element in _find_location_result_elements(driver):
            if _tap_element_center(driver, refreshed_element) and _wait_until(
                lambda: not _location_picker_visible(_safe_page_source(driver)),
                timeout=5,
            ):
                return True
        return False
    return False


def _tap_location_result(driver: WebDriver, element) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        rect = _rect_snapshot(element)
        if rect is not None:
            try:
                driver.execute_script(
                    "mobile: tap",
                    {
                        "x": rect["x"] + rect["width"] / 2,
                        "y": rect["y"] + min(rect["height"] * 0.55, rect["height"] - 8.0),
                    },
                )
                return True
            except WebDriverException:
                pass
    return _tap_element_center(driver, element)


def _find_location_result_elements(driver: WebDriver) -> list:
    positioned_elements = []
    seen: set[tuple[str, float, float, float, float]] = set()
    for xpath in [
        "//android.widget.TextView",
        '//XCUIElementTypeOther[@visible="true"]',
        '//XCUIElementTypeStaticText[@visible="true"]',
    ]:
        try:
            candidates = driver.find_elements(AppiumBy.XPATH, xpath)
        except (AttributeError, WebDriverException):
            continue
        for element in candidates:
            name = _element_name(element)
            rect = _rect_snapshot(element)
            if rect is None:
                continue
            if not _looks_like_location_result(name, rect):
                continue
            key = (
                name,
                float(rect.get("x", 0) or 0),
                float(rect.get("y", 0) or 0),
                float(rect.get("width", 0) or 0),
                float(rect.get("height", 0) or 0),
            )
            if key in seen:
                continue
            seen.add(key)
            positioned_elements.append((rect["y"], rect["x"], element))
    positioned_elements.sort(key=lambda item: (item[0], item[1]))
    return [element for _, _, element in positioned_elements]


def _looks_like_location_result(name: str, rect: dict) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    if any(token in text for token in ["标记地点", "不标记地点", "搜索地点", "没有找到匹配地点", "Vertical scroll bar", "Horizontal scroll bar"]):
        return False
    x = float(rect.get("x", 0) or 0)
    y = float(rect.get("y", 0) or 0)
    width = float(rect.get("width", 0) or 0)
    height = float(rect.get("height", 0) or 0)
    if "省" not in text and "市" not in text and "区" not in text and "路" not in text and "号" not in text:
        return False
    if width < 250 or height < 40 or height > 120:
        return False
    if y < 160:
        return False
    return True


def _find_visible_location_option_elements(driver: WebDriver) -> list:
    xpaths = [
        '//*[@name="标记地点" or @label="标记地点" or @value="标记地点"]'
        '/following::XCUIElementTypeScrollView[1]//XCUIElementTypeStaticText[@visible="true"]',
        '//*[@name="标记地点" or @label="标记地点" or @value="标记地点"]'
        '/following::XCUIElementTypeScrollView[1]//XCUIElementTypeOther[@visible="true"]',
    ]
    seen: set[tuple[str, float, float, float, float]] = set()
    elements: list = []
    for xpath in xpaths:
        try:
            candidates = driver.find_elements(AppiumBy.XPATH, xpath)
        except (AttributeError, WebDriverException):
            continue
        for element in candidates:
            name = _element_name(element)
            rect = getattr(element, "rect", {}) or {}
            if not _looks_like_location_option(name, rect):
                continue
            key = (
                name,
                float(rect.get("x", 0)),
                float(rect.get("y", 0)),
                float(rect.get("width", 0)),
                float(rect.get("height", 0)),
            )
            if key in seen:
                continue
            seen.add(key)
            elements.append(element)
    elements.sort(key=lambda element: ((getattr(element, "rect", {}) or {}).get("x", 0)))
    return elements


def _looks_like_location_option(name: str, rect: dict) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    if any(token in text for token in ["标记地点", "允许评论", "发布笔记", "存草稿", "Vertical scroll bar", "Horizontal scroll bar"]):
        return False
    if len(text) > 20:
        return False
    width = rect.get("width", 0) or 0
    height = rect.get("height", 0) or 0
    if width <= 0 or height <= 0:
        return False
    return True


def _element_name(element) -> str:
    for attribute in ["text", "name", "label", "value"]:
        try:
            value = element.get_attribute(attribute)
        except WebDriverException:
            value = None
        if value:
            return str(value)
    return ""


def _tap_element_center(driver: WebDriver, element) -> bool:
    rect = _rect_snapshot(element)
    if rect is None:
        return False
    if _tap_rect_center(driver, rect):
        return True
    try:
        element.click()
        return True
    except WebDriverException:
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


def _set_allow_comments(driver: WebDriver, allow_comments: bool) -> None:
    if allow_comments:
        if "不允许评论" in _safe_page_source(driver):
            _tap_text_or_contains(driver, "允许评论")
        return
    for text in ["允许评论", "评论"]:
        if _tap_text_or_contains(driver, text):
            return


def _fill_input_near_label(
    driver: WebDriver,
    keyword: str,
    value: str,
    *,
    prefer_text_view: bool = False,
) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        try:
            element = driver.find_element(
                AppiumBy.XPATH,
                f'//android.widget.EditText[contains(@hint, "{keyword}") or contains(@text, "{keyword}")]',
            )
            _replace_text(element, value)
            _hide_keyboard(driver)
            return True
        except (NoSuchElementException, WebDriverException):
            pass

    element_types = ["XCUIElementTypeTextView", "XCUIElementTypeTextField"] if prefer_text_view else [
        "XCUIElementTypeTextField",
        "XCUIElementTypeTextView",
    ]
    for element_type in element_types:
        for xpath in [
            f'//*[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]/following::{element_type}[1]',
            f'//{element_type}[contains(@name, "{keyword}") or contains(@label, "{keyword}") or contains(@value, "{keyword}")]',
        ]:
            try:
                _replace_text(driver.find_element(AppiumBy.XPATH, xpath), value)
                _hide_keyboard(driver)
                return True
            except (NoSuchElementException, WebDriverException):
                continue
    return False


def _fill_first_available_text_input(driver: WebDriver, value: str) -> bool:
    for xpath in [
        '//XCUIElementTypeTextField[@value="" or not(@value) or contains(@value, "请输入")]',
        '//XCUIElementTypeTextView[@value="" or not(@value) or contains(@value, "请输入")]',
        "//XCUIElementTypeTextField[1]",
        "//XCUIElementTypeTextView[1]",
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), value)
            _hide_keyboard(driver)
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _replace_text(element, value: str) -> None:
    element.click()
    try:
        element.clear()
    except WebDriverException:
        pass
    element.send_keys(value)


def _hide_keyboard(driver: WebDriver) -> None:
    for kwargs in [
        {},
        {"key_name": "Done"},
        {"key_name": "Return"},
        {"key_name": "Next"},
        {"strategy": "pressKey", "key_name": "Done"},
    ]:
        try:
            driver.hide_keyboard(**kwargs)
            return
        except WebDriverException:
            continue
    _dismiss_keyboard_with_safe_tap(driver)


def _dismiss_editor_keyboard(driver: WebDriver) -> None:
    if _tap_editor_done(driver) and _wait_until(
        lambda: not _keyboard_visible(_safe_page_source(driver)),
        timeout=3,
    ):
        time.sleep(0.2)
        return
    for kwargs in [
        {},
        {"key_name": "Done"},
        {"key_name": "Return"},
        {"key_name": "Next"},
        {"strategy": "pressKey", "key_name": "Done"},
    ]:
        try:
            driver.hide_keyboard(**kwargs)
            break
        except WebDriverException:
            continue
    time.sleep(0.2)


def _tap_editor_done(driver: WebDriver) -> bool:
    try:
        element = driver.find_element(
            AppiumBy.XPATH,
            '//XCUIElementTypeOther[@visible="true" and (@name="完成" or @label="完成" or @value="完成")]',
        )
    except (NoSuchElementException, WebDriverException, AttributeError):
        return False
    return _tap_element_center(driver, element)


def _keyboard_visible(page_source: str) -> bool:
    return bool(re.search(r'<XCUIElementTypeKeyboard\b[^>]*\bvisible="true"', page_source))


def _tap_outside_editor(driver: WebDriver) -> None:
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.9,
                "y": size["height"] * 0.18,
            },
        )
    except WebDriverException:
        pass


def _dismiss_keyboard_with_safe_tap(driver: WebDriver) -> None:
    for text in ["完成", "收起键盘", "隐藏", "确定"]:
        if tap_text_if_present(driver, text, timeout=1):
            time.sleep(0.2)
            return
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.9,
                "y": size["height"] * 0.18,
            },
        )
        time.sleep(0.2)
    except WebDriverException:
        pass


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


def _confirm_overlay(driver: WebDriver) -> None:
    for text in ["确定", "完成", "保存"]:
        if tap_text_if_present(driver, text, timeout=1):
            return


def _tap_note_submit(driver: WebDriver) -> bool:
    for accessibility_id in ["note-submit-button", "message-submit-button", "post-submit-button", "publish-submit-button"]:
        if tap_if_present(driver, accessibility_id, timeout=2):
            return True
    submit_element = _find_bottom_submit_element(driver)
    if submit_element is not None and _tap_element_center(driver, submit_element):
        return True
    for text in ["发布", "提交", "提交审核"]:
        if tap_text_if_present(driver, text, timeout=2):
            return True
    return False


def _find_bottom_submit_element(driver: WebDriver):
    try:
        size = driver.get_window_size()
        min_y = size["height"] * 0.75
    except WebDriverException:
        min_y = 700

    candidates = []
    for xpath in [
        '//android.widget.TextView[@text="发布笔记"]',
        '//*[@name="发布笔记" or @label="发布笔记" or @value="发布笔记"]',
        '//*[contains(@name, "发布笔记") or contains(@label, "发布笔记") or contains(@value, "发布笔记")]',
    ]:
        try:
            candidates.extend(driver.find_elements(AppiumBy.XPATH, xpath))
        except (AttributeError, WebDriverException):
            continue

    best_element = None
    best_y = -1
    for element in candidates:
        rect = getattr(element, "rect", {}) or {}
        y = rect.get("y", 0) or 0
        height = rect.get("height", 0) or 0
        width = rect.get("width", 0) or 0
        if y < min_y or height <= 0 or width <= 0:
            continue
        if y > best_y:
            best_element = element
            best_y = y
    return best_element


def _wait_until(predicate, timeout: int) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if predicate():
            return True
        time.sleep(0.2)
    return False


def _extract_strings(page_source: str) -> list[str]:
    values = ATTRIBUTE_PATTERN.findall(page_source)
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = html.unescape(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _extract_title(texts: list[str]) -> str | None:
    for text in texts:
        if _looks_like_title(text):
            return text
    return None


def _extract_body(texts: list[str], title: str | None) -> str | None:
    candidates = [
        text for text in texts
        if text != title and len(text) >= 10 and not _contains_detail_meta(text)
    ]
    return max(candidates, key=len) if candidates else None


def _extract_count(page_source: str, texts: list[str], pattern: re.Pattern[str], keyword: str) -> str | None:
    if "<android." not in page_source:
        match = pattern.search(page_source)
        if match:
            return match.group(1)

    for index, text in enumerate(texts):
        if keyword not in text:
            continue
        if keyword == "评论":
            count_match = re.fullmatch(r"(?:评论(?:数)?\s*(\d+)|共\s*(\d+)\s*条评论)", text)
        else:
            count_match = re.fullmatch(r"(?:浏览(?:量)?\s*(\d+)|(\d+)\s*浏览)", text)
        if count_match:
            return next(group for group in count_match.groups() if group is not None)
        if text in {keyword, f"{keyword}数", f"{keyword}量"} and index > 0 and texts[index - 1].isdigit():
            return texts[index - 1]
    return None


def _extract_comments(texts: list[str]) -> list[str]:
    comments: list[str] = []
    for text in texts:
        if text in GENERIC_DETAIL_TEXTS or "图票" in text or (
            _contains_detail_meta(text) and not text.startswith("自动化评论")
        ):
            continue
        if (
            text.startswith("自动化评论")
            or any(marker in text for marker in ("：", ":", "回复", "不错", "好", "赞"))
        ) and len(text) >= 4:
            comments.append(text)
    return comments


def _extract_bottom_action_counts(texts: list[str]) -> list[str]:
    for index, text in enumerate(texts):
        if text.startswith("用户 ") and index + 1 < len(texts):
            candidate = texts[index + 1].split()
            if len(candidate) == 3 and all(part.isdigit() for part in candidate):
                return candidate
        match = BOTTOM_ACTION_PATTERN.search(text)
        if match:
            return list(match.groups())
    for index in range(len(texts) - 2):
        candidate = texts[index : index + 3]
        if all(part.isdigit() for part in candidate):
            return candidate
    return []


def _extract_android_bottom_action_counts(page_source: str) -> list[str]:
    return [entry[0] for entry in _android_bottom_action_entries(page_source)]


def _android_bottom_action_entries(page_source: str) -> list[tuple[str, int, int, int, int]]:
    if "<android." not in page_source:
        return []

    rows: dict[int, list[tuple[str, int, int, int, int]]] = {}
    for tag in re.findall(r"<android\.widget\.TextView\b[^>]*>", page_source):
        text_match = re.search(r'\btext="(\d+)"', tag)
        bounds_match = re.search(r'\bbounds="\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"', tag)
        if not text_match or not bounds_match:
            continue
        left, top, right, bottom = (int(value) for value in bounds_match.groups())
        rows.setdefault(top, []).append((text_match.group(1), left, top, right, bottom))

    candidate_rows = [entries for entries in rows.values() if len(entries) >= 3]
    if not candidate_rows:
        return []
    bottom_row = max(candidate_rows, key=lambda entries: entries[0][2])
    return sorted(bottom_row, key=lambda entry: entry[1])[:3]


def _snapshot_is_detail_ready(snapshot: MessageDetailSnapshot) -> bool:
    if not snapshot.title or not snapshot.body:
        return False
    return bool(
        (snapshot.view_count and snapshot.comment_count)
        or len(snapshot.bottom_action_counts) >= 3
    )


def _extract_interaction_signature(page_source: str) -> list[str]:
    snapshot = parse_detail_snapshot(page_source)
    signature = []
    if snapshot.comment_count:
        signature.append(f"comments:{snapshot.comment_count}")
    if snapshot.bottom_action_counts:
        signature.append(f"bottom:{','.join(snapshot.bottom_action_counts)}")
    for match in re.findall(r"回复\s*\d+", page_source):
        signature.append(match)
    return signature


def _looks_like_title(text: str) -> bool:
    return (
        4 <= len(text) <= 40
        and not _contains_detail_meta(text)
        and text not in GENERIC_DETAIL_TEXTS
        and ("\n" not in text)
    )


def _contains_detail_meta(text: str) -> bool:
    return any(keyword in text for keyword in ("浏览", "评论", "留言", "图票"))


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""


def _note_profile_enabled() -> bool:
    return os.getenv("VW_ACTIVITY_PROFILE", "").strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def _note_profile(label: str):
    started_at = time.monotonic()
    yield
    if _note_profile_enabled():
        elapsed = time.monotonic() - started_at
        print(f"[note-profile] {label}: {elapsed:.2f}s", flush=True)


def _tap_candidate(driver: WebDriver, accessibility_ids: list[str], texts: list[str]) -> bool:
    for accessibility_id in accessibility_ids:
        if tap_if_present(driver, accessibility_id, timeout=2):
            return True
    for text in texts:
        if tap_text_if_present(driver, text, timeout=2):
            return True
    return False


def _tap_ticket_toggle(driver: WebDriver) -> bool:
    if _tap_candidate(driver, TICKET_TOGGLE_IDS, TICKET_TOGGLE_TEXTS):
        return True

    for xpath in [
        '//*[@name="查看图票" or @label="查看图票" or @value="查看图票"]',
        '//*[@name="图票" or @label="图票" or @value="图票"]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, TimeoutException, WebDriverException):
            continue
    return False


def _tap_bottom_action(driver: WebDriver) -> bool:
    return _tap_bottom_action_at_index(driver, 0)


def _toggle_bottom_action_and_wait_for_change(
    driver: WebDriver,
    *,
    action_index: int,
    timeout: int,
) -> tuple[list[str], list[str]]:
    before_counts = parse_detail_snapshot(_safe_page_source(driver)).bottom_action_counts
    if len(before_counts) <= action_index:
        raise AssertionError(f"Bottom action counts did not expose index {action_index}: {before_counts}")
    if not _tap_bottom_action_at_index(driver, action_index):
        raise AssertionError(f"Unable to tap bottom action at index {action_index}")

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        after_counts = parse_detail_snapshot(_safe_page_source(driver)).bottom_action_counts
        if len(after_counts) > action_index and after_counts[action_index] != before_counts[action_index]:
            return before_counts, after_counts
        time.sleep(0.2)
    raise AssertionError(
        f"Bottom action at index {action_index} did not change. before={before_counts}"
    )


def _tap_bottom_action_at_index(driver: WebDriver, action_index: int) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        return _tap_android_bottom_action_by_source(driver, action_index)
    if _tap_ios_bottom_action_by_source(driver, action_index):
        return True
    candidates = _find_bottom_action_elements(driver)
    if len(candidates) <= action_index:
        return False
    return _tap_element_center(driver, candidates[action_index])


def _tap_android_bottom_action_by_source(driver: WebDriver, action_index: int) -> bool:
    page_source = _safe_page_source(driver)
    entries = _android_bottom_action_entries(page_source)
    if len(entries) <= action_index:
        return False
    _, left, top, right, bottom = entries[action_index]
    try:
        driver.execute_script(
            "mobile: tap",
            {"x": (left + right) // 2, "y": (top + bottom) // 2},
        )
        return True
    except (AttributeError, WebDriverException):
        return False


def _tap_ios_bottom_action_by_source(driver: WebDriver, action_index: int) -> bool:
    entries = _ios_bottom_action_entries(_safe_page_source(driver))
    if len(entries) <= action_index:
        return False
    _, left, top, _right, bottom = entries[action_index]
    icon_size = max(1, bottom - top)
    try:
        driver.execute_script(
            "mobile: tap",
            {"x": left + icon_size // 2, "y": top + icon_size // 2},
        )
        return True
    except (AttributeError, WebDriverException):
        return False


def _ios_bottom_action_entries(page_source: str) -> list[tuple[str, int, int, int, int]]:
    if "<XCUIElementType" not in page_source:
        return []
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return []

    rows: dict[int, list[tuple[str, int, int, int, int]]] = {}
    for element in root.iter():
        attributes = element.attrib
        if attributes.get("visible") == "false" or attributes.get("enabled") == "false":
            continue
        text = _source_element_text(attributes)
        if not text.isdigit():
            continue
        rect = _source_element_rect(attributes)
        if rect is None:
            continue
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if not (45 <= width <= 85 and 20 <= height <= 36 and top >= 700):
            continue
        rows.setdefault(top, []).append((text, left, top, right, bottom))

    candidate_rows = [entries for entries in rows.values() if len(entries) >= 3]
    if not candidate_rows:
        return []
    bottom_row = max(candidate_rows, key=lambda entries: entries[0][2])
    return sorted(bottom_row, key=lambda entry: entry[1])[:3]


def _source_element_text(attributes: dict[str, str]) -> str:
    for attribute in ("text", "name", "label", "value"):
        value = re.sub(r"\s+", " ", attributes.get(attribute, "") or "").strip()
        if value:
            return value
    return ""


def _source_element_rect(attributes: dict[str, str]) -> tuple[int, int, int, int] | None:
    try:
        left = int(float(attributes.get("x", "")))
        top = int(float(attributes.get("y", "")))
        width = int(float(attributes.get("width", "")))
        height = int(float(attributes.get("height", "")))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return (left, top, left + width, top + height)


def _find_bottom_action_elements(driver: WebDriver) -> list:
    try:
        candidates = driver.find_elements(AppiumBy.XPATH, "//XCUIElementTypeOther")
    except (AttributeError, WebDriverException):
        return []

    action_elements = []
    seen: set[tuple[float, float, float, float]] = set()
    for element in candidates:
        rect = getattr(element, "rect", {}) or {}
        x = float(rect.get("x", 0) or 0)
        y = float(rect.get("y", 0) or 0)
        width = float(rect.get("width", 0) or 0)
        height = float(rect.get("height", 0) or 0)
        if not (45 <= width <= 70 and 20 <= height <= 32):
            continue
        if y < 780:
            continue
        key = (x, y, width, height)
        if key in seen:
            continue
        seen.add(key)
        action_elements.append(element)
    action_elements.sort(key=lambda element: ((getattr(element, "rect", {}) or {}).get("x", 0)))
    return action_elements


def _tap_detail_share_button(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        try:
            rect = driver.get_window_rect()
            driver.execute_script(
                "mobile: tap",
                {"x": int(rect["width"] * 0.95), "y": int(rect["height"] * 0.09)},
            )
            return True
        except (AttributeError, KeyError, TypeError, WebDriverException):
            return False

    try:
        candidates = driver.find_elements(AppiumBy.XPATH, "//XCUIElementTypeOther")
    except (AttributeError, WebDriverException):
        candidates = []

    share_candidate = None
    best_x = -1.0
    for element in candidates:
        rect = getattr(element, "rect", {}) or {}
        x = float(rect.get("x", 0) or 0)
        y = float(rect.get("y", 0) or 0)
        width = float(rect.get("width", 0) or 0)
        height = float(rect.get("height", 0) or 0)
        if not (35 <= width <= 50 and 35 <= height <= 50):
            continue
        if y > 120:
            continue
        if x > best_x:
            best_x = x
            share_candidate = element
    if share_candidate is not None and _tap_element_center(driver, share_candidate):
        return True
    return False


def _share_sheet_visible(page_source: str) -> bool:
    return any(token in page_source for token in ["朋友圈", "微信好友", "发送给朋友", "微信"])


def _tap_share_target(driver: WebDriver, target_text: str) -> bool:
    if tap_text_if_present(driver, target_text, timeout=2):
        return True
    for xpath in [
        f'//*[@name="{target_text}" or @label="{target_text}" or @value="{target_text}"]',
        f'//*[contains(@name, "{target_text}") or contains(@label, "{target_text}") or contains(@value, "{target_text}")]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _find_comment_input(driver: WebDriver, timeout: int):
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        for accessibility_id in COMMENT_INPUT_IDS:
            try:
                return driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id)
            except (NoSuchElementException, WebDriverException):
                continue

        for xpath in [
            '//android.widget.EditText[@hint="写留言" or @text="写留言"]',
            '//XCUIElementTypeTextView',
            '//XCUIElementTypeTextField',
            '//*[@name="留言" or @label="留言" or @value="留言"]',
        ]:
            try:
                return driver.find_element(AppiumBy.XPATH, xpath)
            except (NoSuchElementException, WebDriverException):
                continue
        time.sleep(0.2)

    raise AssertionError("Unable to locate the message comment input")


def _enter_comment_text(driver: WebDriver, input_box, comment_text: str) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"

    try:
        input_box.click()
    except (AttributeError, WebDriverException):
        pass
    try:
        input_box.clear()
    except WebDriverException:
        pass

    if is_ios:
        for enter_method in (
            lambda: input_box.set_value(comment_text),
            lambda: input_box.send_keys(comment_text),
        ):
            try:
                enter_method()
            except (AttributeError, WebDriverException):
                continue
            if _wait_until(lambda: _comment_input_contains(input_box, comment_text), timeout=2):
                return
            try:
                input_box.clear()
            except WebDriverException:
                pass
        raise AssertionError(f"Unable to enter the full comment text on iOS: {comment_text}")

    input_box.send_keys(comment_text)


def _comment_input_contains(input_box, expected_text: str) -> bool:
    for attribute in ["value", "name", "label", "text"]:
        try:
            actual = str(input_box.get_attribute(attribute) or "")
        except (AttributeError, WebDriverException):
            continue
        if expected_text in actual:
            return True
    return False


def _wait_for_comment_echo(
    driver: WebDriver,
    comment_text: str,
    previous_comment_count: str | None,
    timeout: int = 20,
) -> None:
    end_at = time.monotonic() + timeout
    expected_prefix = comment_text[:6]
    previous_count = int(previous_comment_count) if previous_comment_count and previous_comment_count.isdigit() else None

    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        snapshot = parse_detail_snapshot(page_source)
        current_count = int(snapshot.comment_count) if snapshot.comment_count and snapshot.comment_count.isdigit() else None

        if comment_text in page_source or expected_prefix in page_source:
            return
        if previous_count is not None and current_count is not None and current_count > previous_count:
            return
        if snapshot.comments and any(expected_prefix in comment for comment in snapshot.comments):
            return
        time.sleep(0.2)
    raise AssertionError(f"Submitted comment did not appear in the detail page: {comment_text}")
