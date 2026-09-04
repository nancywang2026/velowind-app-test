from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import html
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from xml.etree import ElementTree

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from PIL import Image, ImageChops
import yaml

from velowind_appium.actions import (
    accessibility_id as locator_accessibility_id,
    swipe_vertical,
    tap_first,
    tap_accessibility_id_or_text_if_present,
    tap_if_present,
    tap_text_if_present,
    wait_for_first,
    wait_for_any_accessibility_id_or_text,
    ios_predicate as locator_ios_predicate,
    xpath as locator_xpath,
)
from velowind_appium.auth import ensure_logged_in_if_needed, login_required_from_page_source
from velowind_appium.config import IosAppiumConfig
from velowind_appium.image_validation import (
    compare_images_for_publish_note,
    crop_image_from_screenshot,
    find_largest_visible_image_bounds,
    find_note_detail_image_bounds,
)
from velowind_appium.video_validation import (
    compare_video_to_frames,
    find_note_detail_video_bounds,
)
from velowind_appium.reporting import allure, attach_file_if_present
import velowind_appium.modules.photo_picker as photo_picker
from velowind_appium.modules.note_card_picker import tap_first_note_card


DETAIL_READY_IDS = [
    "post-detail-page",
    "message-detail-page",
    "article-detail-page",
    "post-detail-banner-pager",
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
PUBLISH_ENTRY_PRIMARY_ID = "bottom-nav-center-action"
NOTE_IMAGE_ENTRY_PRIMARY_ID = "publish-note-image-entry-button"
NOTE_VIDEO_ENTRY_PRIMARY_ID = "publish-note-video-entry-button"

PUBLISH_ENTRY_IDS = [
    PUBLISH_ENTRY_PRIMARY_ID,
    "bottom-nav-publish",
    "bottom-nav-plus",
    "bottom-nav-add",
    "home-publish-entry",
    "home-create-entry",
]
PUBLISH_ENTRY_TEXTS = ["发布", "创建", "+", "＋"]

PUBLISH_ENTRY_CANDIDATES = [
    locator_accessibility_id(PUBLISH_ENTRY_PRIMARY_ID),
    locator_accessibility_id("bottom-nav-publish"),
    locator_accessibility_id("bottom-nav-plus"),
    locator_accessibility_id("bottom-nav-add"),
    locator_accessibility_id("home-publish-entry"),
    locator_accessibility_id("home-create-entry"),
    *[locator_ios_predicate(f'name == "{value}" OR label == "{value}" OR value == "{value}"') for value in PUBLISH_ENTRY_TEXTS],
]
NOTE_TYPE_CANDIDATES = [
    locator_accessibility_id("publish-type-note"),
    locator_accessibility_id("note-publish-type"),
    locator_ios_predicate('name == "发布笔记" OR label == "发布笔记" OR value == "发布笔记"'),
    locator_ios_predicate('name == "笔记" OR label == "笔记" OR value == "笔记"'),
]
NOTE_TITLE_CANDIDATES = [
    locator_accessibility_id("note-title-input"),
    locator_ios_predicate('type == "XCUIElementTypeTextField" AND (value CONTAINS "标题" OR label CONTAINS "标题")'),
    locator_xpath('//XCUIElementTypeTextField[contains(@value, "标题")]'),
    locator_xpath("//XCUIElementTypeTextField[1]"),
]
NOTE_BODY_CANDIDATES = [
    locator_accessibility_id("note-body-input"),
    locator_ios_predicate('type == "XCUIElementTypeTextView" AND (value CONTAINS "正文" OR value CONTAINS "分享" OR value CONTAINS "内容")'),
    locator_xpath('//XCUIElementTypeTextView[contains(@value, "正文") or contains(@value, "分享") or contains(@value, "内容")]'),
    locator_xpath("//XCUIElementTypeTextView[1]"),
]
NOTE_SUBMIT_CANDIDATES = [
    locator_accessibility_id("note-submit-button"),
    locator_accessibility_id("message-submit-button"),
    locator_accessibility_id("post-submit-button"),
    locator_accessibility_id("publish-submit-button"),
    locator_ios_predicate('name == "提交审核" OR label == "提交审核" OR value == "提交审核"'),
    locator_ios_predicate('name == "发布" OR label == "发布" OR value == "发布"'),
]
PUBLISH_SHEET_TEXTS = ["选择发布类型"]
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
VIDEO_UPLOAD_PROGRESS_TEXTS = ["进行中", "上传中", "上传进度"]
PUBLISHED_NOTE_VIDEO_LOADING_TEXTS = ["正在缓冲视频...", "post-detail-video-loading"]
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
    "笔记",
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
SYSTEM_MESSAGE_TIME_PATTERN = re.compile(r"^\d{2}-\d{2}\s+\d{2}:\d{2}$")
ANDROID_COMMENT_TIME_PATTERN = re.compile(r"^(?:刚刚|\d+\s*(?:秒|分钟|小时|天|周|个月|年)前)$")
SYSTEM_MESSAGE_SKIP_TEXTS = {
    "消息",
    "系统消息",
    "系统通知",
    "笔记",
    "活动",
    "我的",
    "笔记 活动",
    "消息 我的",
    "笔记 活动 消息 我的",
    "Vertical scroll bar, 1 page",
    "Horizontal scroll bar, 1 page",
}
SUPPORTED_SOURCE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_LAST_PUBLISH_NOTE_IMAGE_VALIDATION_ARTIFACTS = ()
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
    'name="搜索地点" label="搜索地点" enabled="true" visible="true"',
    'value="搜索地点"',
    'placeholderValue="搜索地点"',
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
class SystemMessageSnapshot:
    page_visible: bool
    category: str | None
    timestamp: str | None
    title: str | None
    body: str | None

    def is_basic_system_message_visible(self) -> bool:
        return bool(self.page_visible and self.category and self.timestamp and self.title and self.body)


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
    media_type: str = "image"
    media_source: str = "library"
    camera_record_seconds: float | None = None
    video_index: int = 1
    source_video: str = ""
    caption_image: str = ""


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
    raw_video_index = note.get("video_index", 1)
    try:
        video_index = max(1, int(raw_video_index))
    except (TypeError, ValueError):
        video_index = 1
    return MessageNoteDraft(
        title=title,
        body=body,
        topics=[str(topic).strip() for topic in topics if str(topic).strip()],
        location=location,
        album=album,
        picture_index=picture_index,
        picture_indexes=picture_indexes,
        allow_comments=bool(allow_comments),
        media_type=str(note.get("media_type", "image")).strip().lower() or "image",
        media_source=str(note.get("media_source", "library")).strip().lower() or "library",
        camera_record_seconds=_optional_float(note.get("camera_record_seconds")),
        video_index=video_index,
        source_video=str(note.get("source_video", "")).strip(),
        caption_image=str(note.get("caption_image", "")).strip(),
    )


def _optional_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


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
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if message_note_form_is_visible(page_source):
            return "message-note-form"
        time.sleep(0.2)
    raise TimeoutException("Message note form did not become ready")


def publish_message_note(
    driver: WebDriver,
    draft: MessageNoteDraft,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 60,
    video_source_path: Path | None = None,
) -> str:
    if draft.media_type == "video" and draft.media_source == "camera":
        # A session-scoped driver can retain the source path recorded by a
        # previous album-video case. A newly recorded camera clip has no such
        # local source unless the caller explicitly supplies one, so never
        # compare it against stale media from the preceding test.
        try:
            delattr(driver, "_publish_note_source_video_path")
        except AttributeError:
            pass
    effective_video_source_path = video_source_path
    if draft.media_type == "video" and draft.media_source != "camera":
        android_source = _pull_android_selected_video_source(driver, video_index=draft.video_index)
        if android_source is not None:
            effective_video_source_path = android_source
    with _note_profile("open-publisher"):
        open_message_note_publisher(driver, ios_config=ios_config, timeout=timeout)
    with _note_profile("fill-form"):
        fill_message_note_form(driver, draft, timeout=timeout)
    with _note_profile("submit-note"):
        success_signal = submit_message_note(
            driver,
            timeout=timeout,
            allow_video_upload_progress=draft.media_type == "video",
            published_title=draft.title,
        )
    if draft.media_type == "video" and success_signal == "视频上传中":
        with _note_profile("hold-video-upload-progress"):
            success_signal = wait_for_video_upload_completion(
                driver,
                timeout=timeout,
                observed_signal=success_signal,
            )
    if draft.media_type == "image":
        with _note_profile("validate-published-image"):
            _validate_published_note_image_matches_uploaded_preview(
                driver,
                timeout=min(timeout, 20),
                title=draft.title,
            )
    elif draft.media_type == "video" and (
        effective_video_source_path is not None or getattr(driver, "_publish_note_source_video_path", None)
    ):
        with _note_profile("validate-published-video"):
            _validate_published_note_video_matches_source(
                driver,
                source_path=effective_video_source_path,
                title=draft.title,
                timeout=min(timeout, 30),
            )
    return success_signal


def _pull_android_selected_video_source(driver: WebDriver, *, video_index: int) -> Path | None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return None
    udid = (
        str(capabilities.get("appium:udid") or capabilities.get("udid") or "").strip()
        or os.environ.get("VW_ANDROID_UDID", "").strip()
    )
    if not udid:
        raise AssertionError("Android video source verification requires a device udid")
    command = [
        "adb",
        "-s",
        udid,
        "shell",
        "content",
        "query",
        "--uri",
        "content://media/external/video/media",
        "--projection",
        "_data:date_modified",
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AssertionError("Unable to query Android videos for source verification") from error
    if result.returncode != 0:
        raise AssertionError(f"Unable to query Android videos: {(result.stderr or '').strip()}")
    candidates: list[tuple[int, str]] = []
    for line in (result.stdout or "").splitlines():
        match = re.search(r"_data=(.*), date_modified=(\d+)$", line.strip())
        if match:
            candidates.append((int(match.group(2)), match.group(1)))
    candidates.sort(key=lambda item: item[0], reverse=True)
    target_index = max(1, int(video_index)) - 1
    if target_index >= len(candidates):
        raise AssertionError(f"Android video source index is unavailable: index={video_index} count={len(candidates)}")
    remote_path = candidates[target_index][1]
    suffix = Path(remote_path).suffix.lower() or ".mp4"
    local_path = _publish_note_artifact_dir() / f"android-selected-source-video-{int(time.time())}{suffix}"
    try:
        pull_result = subprocess.run(
            ["adb", "-s", udid, "pull", remote_path, str(local_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AssertionError(f"Unable to pull Android selected source video: {remote_path}") from error
    if pull_result.returncode != 0 or not local_path.is_file():
        raise AssertionError(
            f"Unable to pull Android selected source video: {remote_path} stderr={(pull_result.stderr or '').strip()}"
        )
    setattr(driver, "_publish_note_source_video_path", str(local_path))
    return local_path


def wait_for_video_upload_completion(
    driver: WebDriver,
    timeout: int = 90,
    *,
    hold_seconds: float | None = None,
    observed_signal: str | None = None,
) -> str:
    """Treat the visible post-submit upload progress as the success signal.

    The app performs video upload asynchronously on the ``我的笔记`` page and
    may keep the progress label visible for a long time.  Waiting for that
    label to disappear makes the test fail even after the publish flow has
    succeeded.  We therefore observe the signal, keep the Appium session alive
    for a short grace period, and return the progress signal itself.
    """
    if hold_seconds is None:
        try:
            hold_seconds = max(0.0, float(os.environ.get("VW_VIDEO_UPLOAD_HOLD_SECONDS", "5")))
        except (TypeError, ValueError):
            hold_seconds = 5.0
    if observed_signal == "视频上传中":
        time.sleep(hold_seconds)
        return observed_signal
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if "我的笔记" in page_source and any(token in page_source for token in VIDEO_UPLOAD_PROGRESS_TEXTS):
            time.sleep(hold_seconds)
            return "视频上传中"
        time.sleep(0.5)
    raise AssertionError("Video upload progress was not visible after submitting the note")


def open_message_note_publisher(
    driver: WebDriver,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 30,
) -> None:
    _prepare_android_publish_entry(driver)

    end_at = time.monotonic() + timeout

    def _form_or_login_visible() -> bool:
        page_source = _safe_page_source(driver)
        return message_note_form_is_visible(page_source) or login_required_from_page_source(page_source)

    def _raise_if_login_required(page_source: str) -> None:
        if login_required_from_page_source(page_source):
            raise AssertionError(
                "Publish flow reached a login page; session is not logged in. "
                "The logged_in_session fixture should authenticate before business steps."
            )

    def _recover_from_login_page() -> bool:
        if ios_config is None:
            return False
        if not getattr(ios_config, "login_username", None) or not getattr(ios_config, "login_password", None):
            return False
        return ensure_logged_in_if_needed(driver, ios_config)

    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if login_required_from_page_source(page_source):
            if _recover_from_login_page():
                continue
            _raise_if_login_required(page_source)

        if message_note_form_is_visible(page_source):
            return

        if _publish_sheet_visible(page_source) and _tap_note_type_if_present(driver):
            if _wait_until(_form_or_login_visible, timeout=10):
                page_source = _safe_page_source(driver)
                if login_required_from_page_source(page_source) and _recover_from_login_page():
                    continue
                _raise_if_login_required(page_source)
                if message_note_form_is_visible(page_source):
                    return

        if _tap_publish_entry_if_present(driver):
            _tap_note_type_if_present(driver)
            if _wait_until(_form_or_login_visible, timeout=10):
                page_source = _safe_page_source(driver)
                if login_required_from_page_source(page_source) and _recover_from_login_page():
                    continue
                _raise_if_login_required(page_source)
                if message_note_form_is_visible(page_source):
                    return
            _raise_if_login_required(_safe_page_source(driver))
        time.sleep(0.5)

    page_source = _safe_page_source(driver)
    _raise_if_login_required(page_source)
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

    with _note_profile("upload-media"):
        if draft.media_type == "video":
            _upload_note_media(driver, draft)
        else:
            _upload_note_image(driver, draft)
    if draft.media_type == "image":
        with _note_profile("validate-uploaded-image"):
            _ensure_note_source_image_recorded(driver)
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


def submit_message_note(
    driver: WebDriver,
    timeout: int = 30,
    *,
    allow_video_upload_progress: bool = False,
    published_title: str | None = None,
) -> str:
    _hide_keyboard(driver)
    if not _tap_note_submit(driver):
        raise AssertionError("Unable to find the publish action on the message note form")

    end_at = time.monotonic() + timeout
    last_source = ""
    submitted_again = False
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        last_source = page_source
        if allow_video_upload_progress:
            if published_title is None:
                success_signal = message_note_publish_success_signal(
                    page_source,
                    allow_video_upload_progress=True,
                )
            else:
                success_signal = message_note_publish_success_signal(
                    page_source,
                    allow_video_upload_progress=True,
                    published_title=published_title,
                )
        else:
            if published_title is None:
                success_signal = message_note_publish_success_signal(page_source)
            else:
                success_signal = message_note_publish_success_signal(page_source, published_title=published_title)
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
    if not page_source:
        return False
    if any(accessibility_id in page_source for accessibility_id in NOTE_FORM_READY_IDS):
        return True
    if any(text in page_source for text in PUBLISH_SHEET_TEXTS) and "发布活动" in page_source:
        return False
    has_publish_title = "发布笔记" in page_source
    has_title_input = any(text in page_source for text in ["添加标题", "输入标题", "请输入标题", 'placeholderValue="添加标题"'])
    has_body_input = any(text in page_source for text in ["添加正文", "输入正文", "请输入正文", 'XCUIElementTypeTextView', "android.widget.EditText"])
    has_form_action = any(text in page_source for text in ["标记地点", "允许评论", "存草稿", "提交审核"])
    if has_publish_title and (has_form_action or (has_title_input and has_body_input)):
        return True
    texts = _extract_strings(page_source)
    joined = " ".join(texts)
    return has_form_action and any(token in joined for token in NOTE_FORM_READY_TEXTS if token != "发布笔记")


def message_note_publish_success_signal(
    page_source: str,
    *,
    allow_video_upload_progress: bool = False,
    published_title: str | None = None,
) -> str | None:
    texts = _extract_strings(page_source)
    for token in NOTE_SUCCESS_TEXTS:
        if token in texts or token in page_source:
            return token
    for accessibility_id in NOTE_SUCCESS_IDS:
        if accessibility_id in page_source:
            return accessibility_id
    if allow_video_upload_progress and "我的笔记" in page_source:
        if any(token in page_source for token in VIDEO_UPLOAD_PROGRESS_TEXTS):
            return "视频上传中"
    if (
        published_title
        and "我的笔记" in page_source
        and any(
            _published_note_title_matches(text, published_title)
            for text in _extract_visible_message_texts(page_source) or texts
        )
        and not message_note_form_is_visible(page_source)
    ):
        return "我的笔记"
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
    comments = _dedupe_preserve_order([*_extract_comments(texts), *_extract_android_comments(page_source)])
    empty_comment_hint = next((text for text in texts if "还没有评论" in text), None)
    bottom_action_counts = _extract_android_bottom_action_counts(page_source) or _extract_bottom_action_counts(texts)
    if comment_count is None and len(bottom_action_counts) >= 3:
        comment_count = bottom_action_counts[2]
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
        if _snapshot_is_detail_ready(snapshot) or _android_image_note_detail_ready(page_source, snapshot):
            return snapshot
        time.sleep(0.2)

    raise AssertionError(f"Message detail did not expose all expected fields: {last_snapshot}")


def open_system_message_page(driver: WebDriver, timeout: int = 15) -> SystemMessageSnapshot:
    snapshot = parse_system_message_snapshot(_safe_page_source(driver))
    if snapshot.is_basic_system_message_visible():
        return snapshot

    if not _tap_messages_tab(driver):
        raise AssertionError("Unable to tap the Messages tab")

    reloaded_network_error = False

    def _system_messages_entry_visible() -> bool:
        nonlocal reloaded_network_error
        page_source = _safe_page_source(driver)
        if "系统消息" in page_source:
            return True
        if not reloaded_network_error and _messages_network_error_visible(page_source):
            reloaded_network_error = tap_text_if_present(driver, "重新加载", timeout=1)
        return False

    if not _wait_until(_system_messages_entry_visible, timeout=timeout):
        raise AssertionError("Messages page did not expose the System Messages entry")

    if not tap_text_if_present(driver, "系统消息", timeout=2):
        raise AssertionError("Unable to tap the System Messages entry")

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        snapshot = parse_system_message_snapshot(_safe_page_source(driver))
        if snapshot.is_basic_system_message_visible():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"System message page did not expose expected detail fields: {snapshot}")


def _messages_network_error_visible(page_source: str) -> bool:
    return "重新加载" in page_source and (
        "Network Error" in page_source
        or "通知加载失败" in page_source
        or "加载失败" in page_source
    )


def parse_system_message_snapshot(page_source: str) -> SystemMessageSnapshot:
    texts = _extract_visible_message_texts(page_source)
    joined_text = " ".join(texts)
    timestamp_index = next((index for index, text in enumerate(texts) if SYSTEM_MESSAGE_TIME_PATTERN.match(text)), None)
    category = None
    title = None
    body = None
    timestamp = texts[timestamp_index] if timestamp_index is not None else None

    if timestamp_index is not None:
        for candidate in reversed(texts[max(0, timestamp_index - 4):timestamp_index]):
            if candidate in {"系统通知", "内容通知", "活动通知"} or _looks_like_system_message_value(candidate):
                category = candidate
                break
        following = [
            text
            for text in texts[timestamp_index + 1:]
            if _looks_like_system_message_value(text) and not SYSTEM_MESSAGE_TIME_PATTERN.match(text)
        ]
        if following:
            title = following[0]
            body = following[1] if len(following) > 1 else title

    return SystemMessageSnapshot(
        page_visible="系统消息" in joined_text,
        category=category,
        timestamp=timestamp,
        title=title,
        body=body,
    )


def submit_message_comment(driver: WebDriver, comment_text: str, timeout: int = 20) -> None:
    with _note_profile("comment-read-before-snapshot"):
        before_snapshot = parse_detail_snapshot(_safe_page_source(driver))
    with _note_profile("comment-close-ios-preview"):
        _close_ios_image_preview_if_visible(driver)
    input_box = None
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"

    opened_entry = False
    if is_ios:
        with _note_profile("comment-tap-ios-bottom-action"):
            opened_entry = _tap_bottom_action_at_index(driver, 2)
        if opened_entry:
            try:
                with _note_profile("comment-find-input-after-ios-bottom-action"):
                    input_box = _find_comment_input(driver, timeout=min(timeout, 2))
            except AssertionError:
                input_box = None

    if input_box is None:
        with _note_profile("comment-tap-candidate-entry"):
            opened_entry = _tap_candidate(driver, COMMENT_ENTRY_IDS, COMMENT_ENTRY_TEXTS)
    if input_box is None and opened_entry:
        try:
            with _note_profile("comment-find-input-after-candidate"):
                input_box = _find_comment_input(driver, timeout=min(timeout, 2))
        except AssertionError:
            input_box = None

    if input_box is None and _tap_bottom_action_at_index(driver, 2):
        with _note_profile("comment-find-input-after-fallback-bottom-action"):
            input_box = _find_comment_input(driver, timeout=timeout)

    if input_box is None:
        raise AssertionError("Unable to open the comment entry point from message detail")

    with _note_profile("comment-enter-text"):
        _enter_comment_text(driver, input_box, comment_text)

    with _note_profile("comment-submit"):
        submitted = is_ios and _tap_ios_visible_text_from_source(driver, COMMENT_SUBMIT_TEXTS)
        if not submitted:
            submitted = _tap_candidate(driver, COMMENT_SUBMIT_IDS, COMMENT_SUBMIT_TEXTS)
        if not submitted:
            input_box.send_keys("\n")

    with _note_profile("comment-wait-echo"):
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
    page_source = _safe_page_source(driver)
    if _detail_shell_is_visible(page_source):
        return True
    snapshot = parse_detail_snapshot(page_source)
    return _snapshot_is_detail_ready(snapshot)


def browse_note_detail(driver: WebDriver, timeout: int = 20) -> MessageDetailSnapshot:
    snapshot = read_message_detail_snapshot(driver, timeout=timeout)
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    if is_android and (
        not _android_detail_interaction_metadata_visible(snapshot)
        or _android_detail_needs_comment_probe(snapshot)
    ):
        swipe_vertical(driver, direction="up")
        end_at = time.monotonic() + timeout
        latest = snapshot
        while time.monotonic() < end_at:
            latest = _merge_detail_snapshots(snapshot, parse_detail_snapshot(_safe_page_source(driver)))
            if (
                _android_detail_interaction_metadata_visible(latest)
                and not _android_detail_needs_comment_probe(latest)
            ):
                return latest
            time.sleep(0.2)
        return latest
    return snapshot


def open_note_search(driver: WebDriver, timeout: int = 10) -> None:
    with _note_profile("open-note-search-initial-source"):
        page_source = _safe_page_source(driver)
    if _note_search_visible(page_source):
        return
    _prepare_android_search_entry(driver)
    with _note_profile("open-note-search-tap-entry"):
        tapped_entry = _tap_note_search_entry(driver)
    if not tapped_entry:
        raise AssertionError("Unable to find the note search entry")
    with _note_profile("open-note-search-wait-visible"):
        visible = _wait_until(lambda: _note_search_visible(_safe_page_source(driver)), timeout=timeout)
    if not visible:
        raise AssertionError("Note search page did not appear after tapping the search entry")


def search_notes(driver: WebDriver, keyword: str, timeout: int = 10) -> None:
    with _note_profile("search-notes-find-input"):
        search_input = _find_note_search_input(driver, timeout=timeout)
    with _note_profile("search-notes-replace-text"):
        _replace_text(search_input, keyword)
    with _note_profile("search-notes-submit"):
        submitted = (
            _tap_android_search_submit(driver)
            or _tap_note_search_submit_by_coordinate(driver)
            or _tap_texts_now(driver, ["搜索", "Search"])
            or _tap_keyboard_search(driver)
        )
    if not submitted:
        _hide_keyboard(driver)
    with _note_profile("search-notes-wait-results"):
        results_visible = _wait_until(lambda: _note_search_results_visible(_safe_page_source(driver), keyword), timeout=timeout)
    if not results_visible:
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
    with _note_profile("share-tap-detail-button"):
        tapped_share = _tap_detail_share_button(driver)
    if not tapped_share:
        raise AssertionError("Unable to find the note share entry point")
    with _note_profile("share-wait-sheet"):
        sheet_visible = _wait_until(lambda: _share_sheet_visible(_safe_page_source(driver)), timeout=timeout)
    if not sheet_visible:
        raise AssertionError("Share sheet did not appear after tapping the share entry point")
    with _note_profile("share-tap-target-moments"):
        tapped_target = _tap_share_target(driver, "朋友圈")
    if not tapped_target:
        raise AssertionError("Unable to find the Moments share target")
    with _note_profile("share-confirm-after-target"):
        confirmed = _confirm_share_after_target(driver, timeout=timeout)
    if not confirmed:
        raise AssertionError("Unable to confirm the Moments share")
    with _note_profile("share-return-home"):
        _return_to_home_after_share(driver, timeout=timeout)
    return "朋友圈"


def _tap_publish_entry_if_present(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    platform = str(capabilities.get("platformName", "")).lower()
    if _tap_publish_trigger_and_verify(
        driver,
        lambda: _tap_test_id_now(driver, PUBLISH_ENTRY_PRIMARY_ID),
    ):
        return True
    if platform == "android":
        # The Android bottom navigation exposes the publish plus button through
        # resource-id. Prefer that stable semantic locator over coordinates.
        page_source = _safe_page_source(driver)
        for resource_id in PUBLISH_ENTRY_IDS:
            if resource_id not in page_source:
                continue
            if _tap_publish_trigger_and_verify(
                driver,
                lambda resource_id=resource_id: _tap_resource_id_now(driver, resource_id),
            ):
                return True
        if _tap_publish_entry_by_coordinate(driver, y_ratios=(0.948,)):
            return True

    if platform == "ios":
        if tap_first(
            driver,
            PUBLISH_ENTRY_CANDIDATES,
            logical_name="publish entry",
            timeout=0.8,
            required=False,
        ):
            if _wait_until(lambda: _publish_entry_opened(_safe_page_source(driver)), timeout=1):
                return True
    if _tap_publish_entry_by_coordinate(driver):
        return True
    for accessibility_id in PUBLISH_ENTRY_IDS:
        if _tap_publish_trigger_and_verify(
            driver,
            lambda accessibility_id=accessibility_id: _tap_accessibility_id_now(driver, accessibility_id),
        ):
            return True
    for text in PUBLISH_ENTRY_TEXTS:
        if _tap_publish_trigger_and_verify(
            driver,
            lambda text=text: tap_text_if_present(driver, text, timeout=1),
        ):
            return True
    for xpath in [
        '//*[@name="发布" or @label="发布" or @value="发布"]',
        '//*[@name="+" or @label="+" or @value="+"]',
        '//*[@name="＋" or @label="＋" or @value="＋"]',
    ]:
        if _tap_publish_trigger_and_verify(
            driver,
            lambda xpath=xpath: _tap_xpath_now(driver, xpath),
        ):
            return True
    try:
        rect = driver.get_window_rect()
        driver.execute_script("mobile: tap", {"x": int(rect["width"] * 0.5), "y": int(rect["height"] * 0.93)})
        return _wait_until(lambda: _publish_entry_opened(_safe_page_source(driver)), timeout=1)
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_publish_trigger_and_verify(driver: WebDriver, tap_action) -> bool:
    try:
        tapped = tap_action()
    except WebDriverException:
        return False
    if not tapped:
        return False
    return _wait_until(lambda: _publish_entry_opened(_safe_page_source(driver)), timeout=1)


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
    if "android.widget.EditText" in page_source and 'text="搜索"' in page_source:
        return True
    return "com.android.quicksearchbox" in page_source and any(text in page_source for text in ["应用推荐", "热搜榜", "搜索"])


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


def _tap_android_header_close(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        for x_ratio, y_ratio in [(0.93, 0.09), (0.95, 0.09), (0.91, 0.09)]:
            driver.execute_script(
                "mobile: tap",
                {"x": int(rect["width"] * x_ratio), "y": int(rect["height"] * y_ratio)},
            )
            time.sleep(0.2)
            if _android_publish_entry_ready(_safe_page_source(driver)):
                return True
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_publish_entry_by_coordinate(
    driver: WebDriver,
    *,
    y_ratios: tuple[float, ...] = (0.935, 0.948, 0.958, 0.968),
) -> bool:
    try:
        rect = driver.get_window_rect()
        capabilities = getattr(driver, "capabilities", {}) or {}
        platform = str(capabilities.get("platformName", "")).lower()
        x = int(rect["width"] * 0.5)
        if platform == "android":
            for y_ratio in y_ratios:
                driver.execute_script("mobile: tap", {"x": x, "y": int(rect["height"] * y_ratio)})
                if _wait_until(
                    lambda: _publish_entry_opened(_safe_page_source(driver)),
                    timeout=1,
                ):
                    return True
            return False
        driver.execute_script("mobile: tap", {"x": x, "y": int(rect["height"] * 0.86)})
        return _wait_until(
            lambda: _publish_entry_opened(_safe_page_source(driver)),
            timeout=1,
        )
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _publish_entry_opened(page_source: str) -> bool:
    return (
        message_note_form_is_visible(page_source)
        or _publish_sheet_visible(page_source)
        or _android_share_sheet_visible(page_source)
    )


def _tap_note_search_entry(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"
    if is_ios and _tap_note_search_entry_by_coordinate(driver):
        return True
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
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"
    ios_selectors = [
        (AppiumBy.IOS_CLASS_CHAIN, "**/XCUIElementTypeSearchField"),
        (AppiumBy.IOS_CLASS_CHAIN, "**/XCUIElementTypeTextField"),
        (
            AppiumBy.IOS_PREDICATE,
            'type == "XCUIElementTypeSearchField" OR type == "XCUIElementTypeTextField"',
        ),
    ]
    while time.monotonic() < end_at:
        if is_ios:
            for by, value in ios_selectors:
                try:
                    return driver.find_element(by, value)
                except (NoSuchElementException, WebDriverException):
                    continue
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
        with _note_profile("search-result-android-fast-path"):
            tapped_android = _tap_first_android_note_search_result(driver)
        if tapped_android:
            return True
    verify_open = lambda: message_detail_is_visible(driver)
    with _note_profile("search-result-page-source"):
        page_source = _safe_page_source(driver)
    with _note_profile("search-result-visible-fast-path"):
        tapped_visible = _tap_first_visible_note_search_result(driver, page_source=page_source)
    if tapped_visible:
        return True
    with _note_profile("search-result-generic-note-card"):
        tapped_generic = tap_first_note_card(
            driver,
            page_source=page_source,
            verify_open=verify_open,
            timeout=0.7,
        )
    if tapped_generic:
        return True
    with _note_profile("search-result-coordinate-first"):
        tapped_coordinate = _tap_first_note_search_result_by_coordinate(driver) and _wait_until(
            verify_open,
            timeout=0.8,
        )
    if tapped_coordinate:
        return True
    with _note_profile("search-result-swipe-next-page"):
        swipe_vertical(driver, direction="up")
        time.sleep(0.2)
    with _note_profile("search-result-page-source-after-swipe"):
        page_source = _safe_page_source(driver)
    with _note_profile("search-result-generic-note-card-after-swipe"):
        tapped_after_swipe = tap_first_note_card(
            driver,
            page_source=page_source,
            verify_open=verify_open,
            timeout=0.7,
        )
    if tapped_after_swipe:
        return True
    with _note_profile("search-result-coordinate-after-swipe"):
        tapped_coordinate_after_swipe = _tap_first_note_search_result_by_coordinate(driver) and _wait_until(
            verify_open,
            timeout=0.8,
        )
    if tapped_coordinate_after_swipe:
        return True
    for accessibility_id in NOTE_SEARCH_RESULT_IDS:
        with _note_profile(f"search-result-accessibility-{accessibility_id}"):
            tapped_accessibility_id = _tap_accessibility_id_now(driver, accessibility_id)
        if tapped_accessibility_id:
            return True
    with _note_profile("search-result-coordinate-final"):
        tapped_coordinate_final = _tap_first_note_search_result_by_coordinate(driver)
    if tapped_coordinate_final:
        return True
    for xpath in [
        "(//XCUIElementTypeCollectionView//XCUIElementTypeCell)[1]",
        "(//XCUIElementTypeCollectionView//XCUIElementTypeButton)[1]",
        "(//XCUIElementTypeTable//XCUIElementTypeCell)[1]",
        "(//XCUIElementTypeTable//XCUIElementTypeButton)[1]",
    ]:
        try:
            with _note_profile(f"search-result-xpath-{xpath}"):
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


def _tap_first_visible_note_search_result(driver: WebDriver, *, page_source: str | None = None) -> bool:
    page_source = page_source or _safe_page_source(driver)
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
    predicate = f'name == "{escaped_title}" OR label == "{escaped_title}" OR value == "{escaped_title}"'
    try:
        driver.find_element(AppiumBy.IOS_PREDICATE, predicate).click()
    except (NoSuchElementException, WebDriverException):
        pass
    else:
        if _wait_until(lambda: message_detail_is_visible(driver), timeout=1.5):
            return True
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
    if _bottom_tabs_signature_in_text(text) or "Vertical scroll bar" in text:
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
    if "Vertical scroll bar" in text or _bottom_tabs_signature_in_text(text):
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
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "ios" and tap_first(
        driver,
        NOTE_TYPE_CANDIDATES,
        logical_name="note publish type",
        timeout=0.8,
        required=False,
    ):
        return True
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


def _bottom_tabs_signature_in_text(text: str) -> bool:
    return "首页 活动 消息 我的" in text or "笔记 活动 消息 我的" in text


def _note_type_visible(page_source: str) -> bool:
    return _publish_sheet_visible(page_source)


def _publish_sheet_visible(page_source: str) -> bool:
    if not page_source or message_note_form_is_visible(page_source):
        return False
    if any(text in page_source for text in PUBLISH_SHEET_TEXTS):
        return True
    return "发布笔记" in page_source and "发布活动" in page_source


def _tap_accessibility_id_now(driver: WebDriver, accessibility_id: str) -> bool:
    try:
        driver.find_element(AppiumBy.ACCESSIBILITY_ID, accessibility_id).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_resource_id_now(driver: WebDriver, resource_id: str) -> bool:
    try:
        driver.find_element(AppiumBy.ID, resource_id).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_test_id_now(driver: WebDriver, test_id: str) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    platform = str(capabilities.get("platformName", "")).lower()
    locator = AppiumBy.ID if platform == "android" else AppiumBy.ACCESSIBILITY_ID
    try:
        driver.find_element(locator, test_id).click()
        return True
    except (AttributeError, NoSuchElementException, WebDriverException):
        return False


def _tap_xpath_now(driver: WebDriver, xpath: str) -> bool:
    try:
        driver.find_element(AppiumBy.XPATH, xpath).click()
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
    if not is_android:
        element = wait_for_first(
            driver,
            NOTE_TITLE_CANDIDATES,
            logical_name="note title input",
            timeout=2,
            required=False,
        )
        if element is not None:
            _replace_text(element, title)
            _hide_keyboard(driver)
            return
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
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        element = wait_for_first(
            driver,
            NOTE_BODY_CANDIDATES,
            logical_name="note body input",
            timeout=2,
            required=False,
        )
        if element is not None:
            _replace_text(element, body)
            _hide_keyboard(driver)
            return
    for keyword in BODY_FIELD_KEYWORDS:
        if _fill_input_near_label(driver, keyword, body, prefer_text_view=True):
            return
    if _fill_android_emulator_note_body_from_placeholder(driver, body):
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


def _fill_android_emulator_note_body_from_placeholder(driver: WebDriver, body: str) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if not _is_android_emulator_capabilities(capabilities):
        return False

    for placeholder in ["添加正文", "输入正文", "请输入正文", "正文"]:
        if not tap_text_if_present(driver, placeholder, timeout=1):
            continue
        time.sleep(0.2)
        for xpath in [
            '//android.widget.EditText[@focused="true"]',
            '//android.widget.EditText[contains(@hint, "正文") or contains(@text, "正文")]',
            "(//android.widget.EditText)[last()]",
        ]:
            try:
                _replace_text(driver.find_element(AppiumBy.XPATH, xpath), body)
                _hide_keyboard(driver)
                return True
            except (NoSuchElementException, WebDriverException):
                continue
    return False


def _is_android_emulator_capabilities(capabilities: dict) -> bool:
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    udid = str(capabilities.get("appium:udid") or capabilities.get("udid") or "").strip()
    device_name = str(capabilities.get("appium:deviceName") or capabilities.get("deviceName") or "").lower()
    return udid.startswith("emulator-") or "emulator" in device_name


def _upload_note_image(driver: WebDriver, draft: MessageNoteDraft) -> None:
    _upload_note_media(driver, draft)


def _upload_note_media(driver: WebDriver, draft: MessageNoteDraft) -> None:
    if draft.media_type == "video":
        _clear_existing_note_images(driver)
        if not _tap_note_video_entry(driver):
            raise AssertionError("Unable to find the note video upload button")
        if draft.media_source == "camera":
            if not photo_picker.choose_video_from_camera(
                driver,
                record_seconds=draft.camera_record_seconds or 3,
            ):
                raise AssertionError("Video camera opened but recording could not be completed.")
        else:
            if not photo_picker.choose_video_from_library(
                driver,
                album_name=draft.album,
                video_index=draft.video_index,
            ):
                raise AssertionError(
                    "Video library opened but no selectable video was found. "
                    "Seed at least one video into Photos on the device."
                )
        return
    if draft.media_type != "image":
        raise AssertionError(f"Unsupported note media type: {draft.media_type}")
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
    _record_note_selected_album_image_source(driver, draft)

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


def _ensure_note_source_image_recorded(driver: WebDriver) -> None:
    source_path = getattr(driver, "_publish_note_album_source_image_path", None)
    if source_path is None:
        raise AssertionError("Selected album image source was not recorded before publishing")
    if not Path(source_path).exists():
        raise AssertionError(f"Selected album image source is missing before publishing: {source_path}")


def _validate_published_note_image_matches_uploaded_preview(
    driver: WebDriver,
    *,
    timeout: int = 20,
    title: str | None = None,
) -> None:
    source_path = getattr(driver, "_publish_note_album_source_image_path", None)
    if source_path is None:
        raise AssertionError("Selected album image source was not recorded before publishing")
    source_path = Path(source_path)
    if not source_path.exists():
        raise AssertionError(f"Selected album image source is missing before publishing: {source_path}")
    if not message_detail_is_visible(driver):
        if title:
            _open_published_note_detail_from_my_notes(driver, title, timeout=timeout)
        elif not _wait_until(lambda: message_detail_is_visible(driver), timeout=timeout):
            raise AssertionError("Published note detail did not become visible for pixel validation")
    if not _wait_until(lambda: find_note_detail_image_bounds(_safe_page_source(driver)) is not None, timeout=timeout):
        raise AssertionError("Unable to locate the published note detail image for pixel validation")

    bounds = find_note_detail_image_bounds(_safe_page_source(driver))
    if bounds is None:
        raise AssertionError("Unable to locate the published note detail image for pixel validation")
    image_bounds = _open_published_note_image_viewer(driver, bounds, timeout=timeout)
    detail_image = _capture_image_bounds(driver, image_bounds)
    detail_path = _publish_note_validation_detail_path()
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_image.save(detail_path)
    result = compare_images_for_publish_note(source_path, detail_path)
    if not result.is_valid:
        attachments = _save_publish_note_image_validation_artifacts(source_path, detail_path, result)
        setattr(driver, "_publish_note_image_validation_artifacts", attachments)
        raise AssertionError(f"Published note image does not match the selected album image: {result}")


def _validate_published_note_video_matches_source(
    driver: WebDriver,
    *,
    source_path: Path | None,
    title: str | None = None,
    timeout: int = 30,
) -> None:
    selected_source = Path(source_path or getattr(driver, "_publish_note_source_video_path", "")).expanduser()
    if not selected_source.is_file():
        raise AssertionError(f"Selected video source is missing before content validation: {selected_source}")
    if not message_detail_is_visible(driver):
        if not title:
            raise AssertionError("Published video detail did not become visible for content validation")
        _open_published_note_detail_from_my_notes(driver, title, timeout=timeout)

    end_at = time.monotonic() + timeout
    bounds = None
    while time.monotonic() < end_at:
        bounds = find_note_detail_video_bounds(_safe_page_source(driver))
        if bounds is not None:
            break
        time.sleep(0.3)
    if bounds is None:
        raise AssertionError("Unable to locate the published note video for content validation")

    _wait_for_published_note_video_ready(driver, timeout=timeout)
    actual_frames, frame_paths = _capture_published_note_video_frames(driver, bounds)
    try:
        result = compare_video_to_frames(
            selected_source,
            actual_frames,
            # Device screenshots are intentionally limited to four, but the
            # source video needs a denser timeline so an arbitrary playback
            # moment is compared with the same scene instead of the nearest
            # one of only four unrelated source moments.
            sample_count=_video_validation_source_sample_count(),
        )
    except Exception as error:
        raise AssertionError(f"Unable to compare the published video with its source: {error}") from error
    summary_path = _publish_note_video_validation_summary_path()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        "\n".join(
            [
                f"source_path={selected_source}",
                f"sampled_frame_paths={','.join(str(path) for path in frame_paths)}",
                f"comparison={result}",
                *_publish_note_video_frame_summary_lines(result, frame_paths),
            ]
        ),
        encoding="utf-8",
    )
    mismatch_artifacts = (
        _save_publish_note_video_mismatch_artifacts(actual_frames, result)
        if not result.is_valid
        else {}
    )
    comparisons_by_index = {
        comparison.actual_frame_index: comparison
        for comparison in getattr(result, "frame_comparisons", ())
    }
    for index, frame_path in enumerate(frame_paths, start=1):
        comparison = comparisons_by_index.get(index)
        if comparison is None:
            attachment_name = f"publish-note-video-validation-actual-frame-{index:02d}.png"
        else:
            status = _publish_note_video_frame_status(result, comparison)
            attachment_name = (
                f"{status}-actual-frame-{index:02d}-"
                f"similarity-{comparison.similarity:.6f}.png"
            )
        attach_file_if_present(
            frame_path,
            name=attachment_name,
            attachment_type=allure.attachment_type.PNG,
        )
        for artifact_path, artifact_name in mismatch_artifacts.get(index, ()):
            attach_file_if_present(
                artifact_path,
                name=artifact_name,
                attachment_type=allure.attachment_type.PNG,
            )
    attach_file_if_present(summary_path, name="publish-note-video-validation.txt", attachment_type=allure.attachment_type.TEXT)
    if not result.is_valid:
        mismatch_summary = ", ".join(
            f"frame-{comparison.actual_frame_index:02d}(similarity={comparison.similarity:.6f})"
            for comparison in getattr(result, "frame_comparisons", ())
            if not comparison.is_valid
        ) or "none identified by per-frame similarity"
        raise AssertionError(
            "Published note video does not match the source video; "
            f"mismatched screenshots: {mismatch_summary}; comparison={result}"
        )


def _publish_note_video_frame_summary_lines(result, frame_paths: list[Path]) -> list[str]:
    paths_by_index = {index: path for index, path in enumerate(frame_paths, start=1)}
    lines: list[str] = []
    for comparison in getattr(result, "frame_comparisons", ()):
        status = _publish_note_video_frame_status(result, comparison)
        lines.append(
            f"actual_frame_{comparison.actual_frame_index:02d}="
            f"status={status},"
            f"similarity={comparison.similarity:.6f},"
            f"matched_source_frame={comparison.matched_source_frame_index:02d},"
            f"path={paths_by_index.get(comparison.actual_frame_index, '')}"
        )
    return lines


def _publish_note_video_frame_status(result, comparison) -> str:
    if comparison.is_valid:
        return "MATCH"
    if result.is_valid:
        return "LOW-SIMILARITY"
    return "MISMATCH"


def _save_publish_note_video_mismatch_artifacts(
    actual_frames: list[Image.Image],
    result,
) -> dict[int, tuple[tuple[Path, str], ...]]:
    artifact_dir = _publish_note_artifact_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"publish-note-video-validation-{int(time.time())}"
    artifacts: dict[int, tuple[tuple[Path, str], ...]] = {}
    for comparison in getattr(result, "frame_comparisons", ()):
        if comparison.is_valid:
            continue
        actual_offset = comparison.actual_frame_index - 1
        if actual_offset < 0 or actual_offset >= len(actual_frames):
            continue
        actual_frame = actual_frames[actual_offset].convert("RGB")
        source_frame = comparison.matched_source_frame.convert("RGB")
        prefix = (
            f"MISMATCH-frame-{comparison.actual_frame_index:02d}-"
            f"similarity-{comparison.similarity:.6f}"
        )
        source_path = artifact_dir / f"{base_name}-{prefix}-source.png"
        diff_path = artifact_dir / f"{base_name}-{prefix}-diff.png"
        source_frame.save(source_path)
        ImageChops.difference(source_frame.resize(actual_frame.size), actual_frame).save(diff_path)
        artifacts[comparison.actual_frame_index] = (
            (
                source_path,
                f"{prefix}-matched-source-frame-{comparison.matched_source_frame_index:02d}.png",
            ),
            (diff_path, f"{prefix}-diff.png"),
        )
    return artifacts


def _wait_for_published_note_video_ready(driver: WebDriver, timeout: int = 30) -> None:
    end_at = time.monotonic() + timeout
    ready_polls = 0
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _published_note_video_loading_visible(page_source):
            ready_polls = 0
        else:
            ready_polls += 1
            if ready_polls >= 2:
                return
        time.sleep(0.3)
    raise AssertionError("Published note video stayed in a loading state too long")


def _published_note_video_loading_visible(page_source: str) -> bool:
    return any(token in page_source for token in PUBLISHED_NOTE_VIDEO_LOADING_TEXTS)


def _video_validation_source_sample_count() -> int:
    try:
        return max(
            4,
            min(120, int(os.environ.get("VW_VIDEO_VALIDATION_SOURCE_SAMPLE_COUNT", "24"))),
        )
    except ValueError:
        return 24


def _capture_published_note_video_frames(
    driver: WebDriver,
    bounds,
    *,
    sample_count: int | None = None,
    seconds: float | None = None,
) -> tuple[list[Image.Image], list[Path]]:
    """Sample the player with screenshots so validation does not need Appium ffmpeg."""
    artifact_dir = _publish_note_artifact_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if sample_count is None:
        try:
            sample_count = max(2, min(12, int(os.environ.get("VW_VIDEO_VALIDATION_SAMPLE_COUNT", "4"))))
        except ValueError:
            sample_count = 4
    if seconds is None:
        try:
            seconds = max(1.0, min(20.0, float(os.environ.get("VW_VIDEO_VALIDATION_RECORD_SECONDS", "8"))))
        except ValueError:
            seconds = 8.0
    sample_count = max(1, int(sample_count))
    interval = float(seconds) / max(1, sample_count - 1)
    try:
        frame_ready_attempts = max(
            1,
            min(30, int(os.environ.get("VW_VIDEO_VALIDATION_FRAME_READY_ATTEMPTS", "10"))),
        )
    except ValueError:
        frame_ready_attempts = 10
    frames: list[Image.Image] = []
    frame_paths: list[Path] = []
    try:
        window = driver.get_window_size()
        window_size = (int(window["width"]), int(window["height"]))
        for index in range(sample_count):
            if index:
                time.sleep(interval)
            frame = _capture_loaded_published_note_video_frame(
                driver,
                bounds,
                window_size=window_size,
                frame_index=index + 1,
                max_attempts=frame_ready_attempts,
            )
            frame_path = artifact_dir / f"publish-note-video-validation-{int(time.time())}-{index + 1}.png"
            frame.save(frame_path)
            frames.append(frame)
            frame_paths.append(frame_path)
    except (AttributeError, KeyError, TypeError, WebDriverException) as error:
        raise AssertionError("Unable to capture the published note video on the device") from error
    if not frames:
        raise AssertionError("Appium returned no screenshots for the published video")
    return frames, frame_paths


def _capture_loaded_published_note_video_frame(
    driver: WebDriver,
    bounds,
    *,
    window_size: tuple[int, int],
    frame_index: int,
    max_attempts: int,
) -> Image.Image:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    for _attempt in range(max_attempts):
        # Android hierarchy serialization is unusually expensive on the video
        # detail page (several seconds per read). Loading has already been
        # checked once before sampling, so avoid reading the same hierarchy
        # before and after every Android screenshot. A blank-frame check still
        # protects us from accepting an unrendered player surface.
        if not is_android and _published_note_video_loading_visible(_safe_page_source(driver)):
            time.sleep(0.3)
            continue
        screenshot_png = driver.get_screenshot_as_png()
        frame = crop_image_from_screenshot(
            screenshot_png,
            bounds,
            window_size=window_size,
        )
        loading_after_capture = (
            False
            if is_android
            else _published_note_video_loading_visible(_safe_page_source(driver))
        )
        if not loading_after_capture and _published_note_video_frame_has_rendered_content(frame):
            return frame
        time.sleep(0.3)
    raise AssertionError(
        f"Published note video screenshot {frame_index} was still loading or blank "
        f"after {max_attempts} attempts"
    )


def _published_note_video_frame_has_rendered_content(frame: Image.Image) -> bool:
    grayscale = frame.convert("L")
    pixel_count = grayscale.width * grayscale.height
    if pixel_count <= 0:
        return False
    near_black_pixel_count = sum(grayscale.histogram()[:12])
    return near_black_pixel_count / pixel_count < 0.98


def _publish_note_video_validation_summary_path() -> Path:
    return _publish_note_artifact_dir() / f"publish-note-video-validation-{int(time.time())}.txt"


def _open_published_note_detail_from_my_notes(driver: WebDriver, title: str, *, timeout: int = 20) -> None:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    reset_android_list_to_top = False
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if message_detail_is_visible(driver):
            return
        if is_android and _my_notes_list_visible(page_source) and not reset_android_list_to_top:
            reset_android_list_to_top = True
            for _ in range(8):
                try:
                    swipe_vertical(driver, direction="down")
                except (WebDriverException, AttributeError):
                    break
                time.sleep(0.4)
            continue
        if _tap_published_note_title(driver, title, page_source=page_source):
            if _wait_until(lambda: message_detail_is_visible(driver), timeout=5):
                return
        if not _my_notes_list_visible(page_source):
            if tap_text_if_present(driver, "我的笔记", timeout=1):
                continue
            if tap_text_if_present(driver, "我的", timeout=1):
                continue
        if not _scroll_my_notes_list(driver):
            break
        time.sleep(0.3)
    raise AssertionError(f"Unable to open published note detail from My Notes for title: {title}")


def _my_notes_list_visible(page_source: str) -> bool:
    return "我的笔记" in page_source and (
        any(token in page_source for token in ["发布", "草稿箱", "我的发布"])
        or all(token in page_source for token in ["笔记", "收藏", "点赞"])
    )


def _tap_published_note_title(driver: WebDriver, title: str, *, page_source: str | None = None) -> bool:
    page_source = page_source or _safe_page_source(driver)
    if not page_source:
        return False
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    if is_android and _tap_android_published_note_title_prefix(driver, title):
        return True
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    for xpath in [
        f'//XCUIElementTypeStaticText[contains(@name, "{escaped_title}") or contains(@label, "{escaped_title}") or contains(@value, "{escaped_title}") or contains(@text, "{escaped_title}")]',
        f'//*[contains(@text, "{escaped_title}") or contains(@name, "{escaped_title}") or contains(@label, "{escaped_title}") or contains(@value, "{escaped_title}")]',
        f'//*[contains(@name, "{escaped_title}") or contains(@label, "{escaped_title}") or contains(@value, "{escaped_title}")]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException):
            continue
        rect = _rect_snapshot(element)
        if is_android and rect is not None:
            tapped = _adb_input_tap(
                driver,
                int(rect["x"] + rect["width"] / 2),
                int(rect["y"] + rect["height"] / 2),
            )
        else:
            try:
                element.click()
                tapped = True
            except WebDriverException:
                tapped = rect is not None and _tap_rect_center(driver, rect)
        if not tapped:
            continue
        if _wait_until(lambda: message_detail_is_visible(driver), timeout=1.5):
            return True
    title_rect = _visible_ios_published_note_title_rect(page_source, title)
    if title_rect is not None and _tap_rect_center(driver, title_rect):
        return True
    return tap_text_if_present(driver, title, timeout=1)


def _tap_android_published_note_title_prefix(driver: WebDriver, title: str) -> bool:
    normalized_title = str(title or "").strip()
    if not normalized_title:
        return False
    minimum_prefix_length = max(10, (len(normalized_title) * 3 + 4) // 5)
    prefix = normalized_title[:minimum_prefix_length]
    escaped_prefix = prefix.replace("\\", "\\\\").replace('"', '\\"')
    try:
        candidates = driver.find_elements(
            AppiumBy.XPATH,
            f'//android.widget.TextView[contains(@text, "{escaped_prefix}")]',
        )
    except (AttributeError, WebDriverException):
        return False
    for candidate in candidates:
        try:
            candidate_text = str(candidate.get_attribute("text") or "")
        except (AttributeError, WebDriverException):
            continue
        if not _published_note_title_matches(candidate_text, normalized_title):
            continue
        rect = _rect_snapshot(candidate)
        if rect is None:
            continue
        if _adb_input_tap(
            driver,
            int(rect["x"] + rect["width"] / 2),
            int(rect["y"] + rect["height"] / 2),
        ):
            return True
    return False


def _visible_ios_published_note_title_rect(page_source: str, title: str) -> dict[str, float] | None:
    if "<XCUIElementType" not in page_source or not title:
        return None
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None

    candidates: list[tuple[int, int, int, dict[str, float]]] = []
    for element in root.iter():
        attributes = element.attrib
        if attributes.get("visible", "true").lower() == "false":
            continue
        if attributes.get("enabled", "true").lower() == "false":
            continue
        text = _source_element_text(attributes)
        if not _published_note_title_matches(text, title):
            continue
        rect = _source_element_rect(attributes)
        if rect is None:
            continue
        left, top, right, bottom = rect
        tag_name = element.tag.rsplit("}", 1)[-1]
        type_rank = 0 if tag_name == "XCUIElementTypeStaticText" else 1
        exact_rank = 0 if text == title else 1
        candidates.append(
            (
                exact_rank,
                type_rank,
                top,
                {
                    "x": float(left),
                    "y": float(top),
                    "width": float(right - left),
                    "height": float(bottom - top),
                },
            )
        )
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[:3])[3]


def _published_note_title_matches(candidate: str, title: str) -> bool:
    normalized_candidate = " ".join((candidate or "").split()).strip()
    normalized_title = " ".join((title or "").split()).strip()
    if not normalized_candidate or not normalized_title:
        return False
    if normalized_candidate == normalized_title:
        return True
    # iOS may expose repeated title text from nested SwiftUI accessibility
    # nodes (for example, the same title three times in one StaticText).
    if normalized_title in normalized_candidate:
        return True
    if not normalized_title.startswith(normalized_candidate):
        return False
    minimum_prefix_length = max(10, (len(normalized_title) * 3 + 4) // 5)
    return len(normalized_candidate) >= minimum_prefix_length


def _scroll_my_notes_list(driver: WebDriver) -> bool:
    try:
        swipe_vertical(driver, direction="up")
        return True
    except (WebDriverException, AttributeError):
        return False


def _open_published_note_image_viewer(driver: WebDriver, bounds, *, timeout: int):
    if not _tap_image_bounds_center(driver, bounds):
        return bounds
    if not _wait_until(lambda: find_largest_visible_image_bounds(_safe_page_source(driver)) is not None, timeout=min(timeout, 5)):
        return bounds
    viewer_bounds = find_largest_visible_image_bounds(_safe_page_source(driver))
    return viewer_bounds or bounds


def _tap_image_bounds_center(driver: WebDriver, bounds) -> bool:
    try:
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(bounds.x + bounds.width / 2),
                "y": int(bounds.y + bounds.height / 2),
            },
        )
        return True
    except (AttributeError, TypeError, WebDriverException):
        return False


def _capture_image_bounds(driver: WebDriver, bounds):
    try:
        screenshot_png = driver.get_screenshot_as_png()
        window = driver.get_window_size()
    except (AttributeError, KeyError, TypeError, WebDriverException) as error:
        raise AssertionError("Unable to capture note image for pixel validation") from error

    return crop_image_from_screenshot(
        screenshot_png,
        bounds,
        window_size=(int(window["width"]), int(window["height"])),
    )


def _publish_note_artifact_dir() -> Path:
    return Path(os.environ.get("VW_APPIUM_ARTIFACT_DIR", ".tmp/appium-ios-device")).expanduser()


def _publish_note_validation_detail_path() -> Path:
    artifact_dir = _publish_note_artifact_dir()
    base_name = f"publish-note-image-validation-{int(time.time())}"
    return artifact_dir / f"{base_name}-detail-image.png"


def _save_publish_note_image_validation_artifacts(source_path: Path, detail_path: Path, result):
    global _LAST_PUBLISH_NOTE_IMAGE_VALIDATION_ARTIFACTS
    artifact_dir = _publish_note_artifact_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"publish-note-image-validation-{int(time.time())}"
    diff_path = artifact_dir / f"{base_name}-diff.png"
    summary_path = artifact_dir / f"{base_name}.txt"
    with Image.open(source_path) as source_image, Image.open(detail_path) as detail_image:
        source = source_image.convert("RGB")
        detail = detail_image.convert("RGB")
        diff_source = source.resize(detail.size)
        ImageChops.difference(diff_source, detail).save(diff_path)
    summary_path.write_text(
        "\n".join(
            [
                f"source_path={source_path}",
                f"detail_path={detail_path}",
                f"comparison={result}",
            ]
        ),
        encoding="utf-8",
    )
    attachments = (
        (source_path, "publish-note-image-validation-source.png", allure.attachment_type.PNG),
        (detail_path, "publish-note-image-validation-detail.png", allure.attachment_type.PNG),
        (diff_path, "publish-note-image-validation-diff.png", allure.attachment_type.PNG),
        (summary_path, "publish-note-image-validation.txt", allure.attachment_type.TEXT),
    )
    _LAST_PUBLISH_NOTE_IMAGE_VALIDATION_ARTIFACTS = attachments
    _attach_publish_note_image_validation_artifacts(attachments)
    return attachments


def attach_recorded_publish_note_image_validation_artifacts(driver: WebDriver) -> None:
    attachments = getattr(driver, "_publish_note_image_validation_artifacts", ()) or _LAST_PUBLISH_NOTE_IMAGE_VALIDATION_ARTIFACTS
    _attach_publish_note_image_validation_artifacts(attachments)


def _attach_publish_note_image_validation_artifacts(attachments) -> None:
    for path, name, attachment_type in attachments:
        attach_file_if_present(path, name=name, attachment_type=attachment_type)


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


def _record_note_cropper_image(driver: WebDriver) -> None:
    bounds = find_largest_visible_image_bounds(_safe_page_source(driver))
    if bounds is None:
        return
    setattr(driver, "_publish_note_uploaded_preview_image", _capture_image_bounds(driver, bounds))


def _record_note_selected_album_image_source(driver: WebDriver, draft: MessageNoteDraft) -> None:
    source_path = _resolve_note_selected_album_image_source(draft)
    selected_index = _selected_note_picture_index(draft)
    if source_path is None:
        album = draft.album or "<default>"
        raise AssertionError(f"Unable to resolve selected album image source: album={album} index={selected_index}")

    artifact_dir = _publish_note_artifact_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    album_label = _safe_artifact_name(draft.album or "default-album")
    copied_path = artifact_dir / f"publish-note-album-source-{album_label}-index-{selected_index}-{source_path.name}"
    shutil.copy2(source_path, copied_path)
    setattr(driver, "_publish_note_album_source_image_path", copied_path)
    setattr(
        driver,
        "_publish_note_album_source_position",
        f"album={draft.album or '<default>'} index={selected_index} source={source_path.name}",
    )


def _resolve_note_selected_album_image_source(draft: MessageNoteDraft) -> Path | None:
    media_dir = _note_source_media_dir()
    selected_index = _selected_note_picture_index(draft)
    source_dir = media_dir / draft.album if draft.album else media_dir
    if not source_dir.exists() or not source_dir.is_dir():
        return None
    source_files = sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SOURCE_IMAGE_SUFFIXES
    )
    if selected_index < 1 or selected_index > len(source_files):
        return None
    return source_files[selected_index - 1]


def _selected_note_picture_index(draft: MessageNoteDraft) -> int:
    picture_indexes = _normalize_picture_indexes(draft.picture_indexes)
    if picture_indexes:
        return picture_indexes[0]
    return max(1, int(draft.picture_index or 1))


def _note_source_media_dir() -> Path:
    raw_value = os.environ.get("VW_ANDROID_MEDIA_DIR", "").strip()
    if raw_value:
        return Path(raw_value).expanduser()
    return photo_picker.DEFAULT_ANDROID_MEDIA_DIR


def _safe_artifact_name(value: str) -> str:
    return re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("_") or "image"


def _tap_note_photo_library_sheet_option(driver: WebDriver) -> bool:
    try:
        size = driver.get_window_size()
        driver.execute_script(
            "mobile: tap",
            {
                "x": size["width"] * 0.5,
                "y": size["height"] * 0.93,
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
    platform_name = str((getattr(driver, "capabilities", {}) or {}).get("platformName", "")).lower()
    if platform_name == "ios" and _append_note_topics_to_ios_body_by_source(driver, topics):
        return
    topic_action_visible = _tap_text_or_contains(driver, "#话题") or _tap_text_or_contains(driver, "话题")
    if not topic_action_visible:
        if platform_name == "android":
            _focus_android_note_body_for_topic_action(driver)
        else:
            _focus_ios_note_body_for_topic_action(driver)
        topic_action_visible = _tap_note_topic_action(driver)
    if not topic_action_visible and platform_name not in {"android", "ios"}:
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


def _append_note_topics_to_ios_body_by_source(driver: WebDriver, topics: list[str]) -> bool:
    element = _find_ios_input_from_page_source_geometry(driver, "正文", prefer_text_view=True)
    if element is None:
        return False
    existing_body = _text_input_current_value(element)
    missing_topics = [topic for topic in topics if topic not in existing_body]
    if not missing_topics:
        _dismiss_editor_keyboard(driver)
        return True
    combined_body = f"{existing_body.rstrip()} {' '.join(missing_topics)}".strip()
    _replace_text(element, combined_body)
    _dismiss_editor_keyboard(driver)
    return True


def _focus_android_note_body_for_topic_action(driver: WebDriver) -> bool:
    try:
        element = driver.find_element(AppiumBy.XPATH, '//android.widget.EditText[contains(@hint, "正文")]')
        element.click()
        time.sleep(0.2)
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _focus_ios_note_body_for_topic_action(driver: WebDriver) -> bool:
    try:
        candidates = driver.find_elements(AppiumBy.IOS_CLASS_CHAIN, "**/XCUIElementTypeTextView")
    except (AttributeError, WebDriverException):
        candidates = []
    for element in candidates:
        rect = getattr(element, "rect", {}) or {}
        width = float(rect.get("width", 0) or 0)
        height = float(rect.get("height", 0) or 0)
        if width < 120 or height < 40:
            continue
        try:
            element.click()
            time.sleep(0.4)
            return True
        except WebDriverException:
            continue
    try:
        driver.find_element(AppiumBy.XPATH, "//XCUIElementTypeTextView[1]").click()
        time.sleep(0.4)
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _tap_note_topic_action(driver: WebDriver, timeout: float = 2.0) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if _tap_text_or_contains(driver, "#话题") or _tap_text_or_contains(driver, "话题"):
            return True
        time.sleep(0.2)
    return False


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
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_ios = str(capabilities.get("platformName", "")).lower() == "ios"
    if _tap_test_id_now(driver, NOTE_IMAGE_ENTRY_PRIMARY_ID):
        if _wait_for_note_photo_picker_opened(driver):
            return True
    if not is_ios and _tap_android_note_image_plus_from_source(driver):
        return True
    if not is_ios and _tap_note_image_plus_by_coordinate(driver):
        return True
    for accessibility_id in [
        "note-image-add",
        "note-photo-add",
        "post-image-add",
        "publish-image-add",
    ]:
        if tap_if_present(driver, accessibility_id, timeout=1) and (
            not is_ios or _wait_for_note_photo_picker_opened(driver)
        ):
            return True
    for text in ["添加图片", "上传图片", "+", "＋"]:
        if tap_text_if_present(driver, text, timeout=1) and (
            not is_ios or _wait_for_note_photo_picker_opened(driver)
        ):
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
            if not is_ios or _wait_for_note_photo_picker_opened(driver):
                return True
        except (NoSuchElementException, WebDriverException):
            continue
    if is_ios:
        if _tap_ios_note_image_plus_from_source(driver):
            return True
        return _tap_note_image_plus_by_coordinate(driver)
    try:
        driver.execute_script("mobile: tap", {"x": 60, "y": 206})
        return True
    except WebDriverException:
        return False


def _tap_note_video_entry(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if _tap_test_id_now(driver, NOTE_VIDEO_ENTRY_PRIMARY_ID):
        return True
    if str(capabilities.get("platformName", "")).lower() == "android":
        try:
            size = driver.get_window_size()
            # The Android publish media card is split horizontally: photo on
            # top, video on bottom. Keep the tap away from the divider.
            driver.execute_script(
                "mobile: tap",
                {"x": size["width"] * 0.098, "y": size["height"] * 0.212},
            )
            return True
        except (AttributeError, KeyError, TypeError, WebDriverException):
            pass
    for accessibility_id in ["note-video-add", "publish-video-add", "post-video-add"]:
        if tap_if_present(driver, accessibility_id, timeout=1):
            return True
    for text in ["添加视频", "上传视频", "视频"]:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    if str(capabilities.get("platformName", "")).lower() == "ios":
        for x, y in [(60, 199), (60, 206), (60, 190)]:
            try:
                driver.execute_script("mobile: tap", {"x": x, "y": y})
                return True
            except WebDriverException:
                continue
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

        # The updated publish card is rendered by the app shell without a
        # clickable Android accessibility node. Its image half is stable at
        # roughly 10% of the screen width and 16% of the screen height.
        try:
            size = driver.get_window_size()
            driver.execute_script(
                "mobile: tap",
                {"x": size["width"] * 0.098, "y": size["height"] * 0.157},
            )
            if _wait_for_note_photo_picker_opened(driver):
                return True
        except (AttributeError, KeyError, TypeError, WebDriverException):
            pass
        return False

    try:
        rect = driver.get_window_rect()
        points = [
            (60, 170),
            (int(rect["width"] * 0.15), int(rect["height"] * 0.19)),
            (int(rect["width"] * 0.15), int(rect["height"] * 0.20)),
            (int(rect["width"] * 0.13), int(rect["height"] * 0.18)),
        ]
    except (AttributeError, KeyError, TypeError):
        points = [(60, 170), (66, 190), (56, 180)]

    for x, y in points:
        try:
            driver.execute_script("mobile: tap", {"x": x, "y": y})
        except WebDriverException:
            continue
        if _wait_for_note_photo_picker_opened(driver):
            return True
    return False


def _tap_android_note_image_plus_from_source(driver: WebDriver) -> bool:
    source = _safe_page_source(driver)
    if not source:
        return False
    try:
        root = ElementTree.fromstring(source)
    except ElementTree.ParseError:
        return False

    candidates: list[tuple[int, int, int, int, bool]] = []
    for element in root.iter():
        if element.tag not in {
            "android.view.ViewGroup",
            "android.widget.ImageView",
            "android.widget.FrameLayout",
            "android.widget.LinearLayout",
        }:
            continue
        attrs = element.attrib
        if attrs.get("visible", "true").lower() == "false":
            continue
        try:
            x = int(float(attrs.get("x", "0")))
            y = int(float(attrs.get("y", "0")))
            width = int(float(attrs.get("width", "0")))
            height = int(float(attrs.get("height", "0")))
        except (TypeError, ValueError):
            continue
        if x > 150 or y < 110 or y > 700 or width < 70 or height < 70:
            continue
        ratio = width / height if height else 0
        is_updated_media_card = (
            attrs.get("resource-id") == "image"
            and width >= 150
            and height >= 200
        )
        if not is_updated_media_card and not 0.65 <= ratio <= 1.5:
            continue
        searchable = " ".join(
            str(attrs.get(attribute, ""))
            for attribute in ("resource-id", "content-desc", "text", "name", "label", "value", "type")
        ).lower()
        if not is_updated_media_card and not any(
            token in searchable for token in ("image", "图片", "上传", "添加", "+", "＋")
        ):
            continue
        candidates.append((y, x, width, height, is_updated_media_card))

    for y, x, width, height, is_updated_media_card in sorted(set(candidates)):
        try:
            driver.execute_script(
                "mobile: tap",
                {
                    "x": x + width // 2,
                    "y": y + (height // 10 if is_updated_media_card else height // 4),
                },
            )
        except WebDriverException:
            continue
        if _wait_for_note_photo_picker_opened(driver):
            return True
    return False


def _tap_ios_note_image_plus_from_source(driver: WebDriver) -> bool:
    source = _safe_page_source(driver)
    if not source:
        return False
    try:
        root = ElementTree.fromstring(source)
    except ElementTree.ParseError:
        return False

    candidates: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        if element.tag not in {
            "XCUIElementTypeOther",
            "XCUIElementTypeImage",
            "XCUIElementTypeButton",
        }:
            continue
        if element.attrib.get("visible", "true").lower() == "false":
            continue
        try:
            x = int(float(element.attrib.get("x", "0")))
            y = int(float(element.attrib.get("y", "0")))
            width = int(float(element.attrib.get("width", "0")))
            height = int(float(element.attrib.get("height", "0")))
        except (TypeError, ValueError):
            continue
        if y < 90 or y > 340 or width < 70 or height < 70:
            continue
        ratio = width / height if height else 0
        if not 0.65 <= ratio <= 1.5:
            continue
        searchable = " ".join(
            str(element.attrib.get(attribute, ""))
            for attribute in ("name", "label", "value", "type")
        ).lower()
        if not any(token in searchable for token in ("image", "图片", "上传", "添加", "+", "＋")):
            continue
        candidates.append((y, x, width, height))

    for y, x, width, height in sorted(set(candidates)):
        try:
            driver.execute_script(
                "mobile: tap",
                {"x": x + width // 2, "y": y + height // 4},
            )
        except WebDriverException:
            continue
        if _wait_for_note_photo_picker_opened(driver):
            return True

    tiny_icon_candidates: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        if element.tag not in {
            "XCUIElementTypeOther",
            "XCUIElementTypeImage",
            "XCUIElementTypeButton",
        }:
            continue
        if element.attrib.get("visible", "true").lower() == "false":
            continue
        try:
            x = int(float(element.attrib.get("x", "0")))
            y = int(float(element.attrib.get("y", "0")))
            width = int(float(element.attrib.get("width", "0")))
            height = int(float(element.attrib.get("height", "0")))
        except (TypeError, ValueError):
            continue
        if not (0 <= x <= 120 and 120 <= y <= 260 and 16 <= width <= 40 and 16 <= height <= 40):
            continue
        tiny_icon_candidates.append((y, x, width, height))

    for y, x, width, height in sorted(set(tiny_icon_candidates)):
        try:
            driver.execute_script(
                "mobile: tap",
                {"x": x + width // 2, "y": y + height // 2},
            )
        except WebDriverException:
            continue
        if _wait_for_note_photo_picker_opened(driver):
            return True
    return False


def _wait_for_note_photo_picker_opened(driver: WebDriver, timeout: int = 2) -> bool:
    return _wait_until(lambda: _note_photo_picker_opened(driver), timeout=timeout)


def _note_photo_picker_opened(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    return any(
        marker in page_source
        for marker in [
            "从手机相册选择",
            "手机相册",
            "从相册选择",
            "照片图库",
            "最近项目",
            "所有照片",
            "选择项目",
            "选择最多9张照片。",
            "PUPickerContainer",
            "photosView_content_scroll_view",
        ]
    )


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
    with _note_profile("fill-location-prepare-section"):
        _prepare_note_location_section(driver)
    with _note_profile("fill-location-open-picker"):
        picker_opened = _open_note_location_picker(driver)
    if picker_opened:
        with _note_profile("fill-location-choose-option-primary"):
            if _choose_note_location_option(driver, location):
                return
        with _note_profile("fill-location-choose-option-retry"):
            if _choose_note_location_option(driver, location):
                return
    raise AssertionError("Unable to select a note location option")


def _should_skip_note_location(location: str) -> bool:
    normalized = (location or "").strip()
    return normalized in {"", "不标记地点", "none", "skip"}


def _open_note_location_picker(driver: WebDriver) -> bool:
    for _ in range(2):
        _dismiss_editor_keyboard(driver)
        if _location_picker_visible(_safe_page_source(driver)):
            return True
        if _tap_note_location_label(driver) and _wait_until(
            lambda: _location_picker_visible(_safe_page_source(driver)),
            timeout=2,
        ):
            return True
        for text in ["不标记地点", "标记地点"]:
            if _tap_text_or_contains(driver, text) and _wait_until(
                lambda: _location_picker_visible(_safe_page_source(driver)),
                timeout=2,
            ):
                return True
        if _tap_note_location_entry_by_coordinate(driver) and _wait_until(
            lambda: _location_picker_visible(_safe_page_source(driver)),
            timeout=2,
        ):
            return True
    return False


def _tap_note_location_label(driver: WebDriver) -> bool:
    predicate = 'name == "标记地点" OR label == "标记地点" OR value == "标记地点"'
    try:
        elements = driver.find_elements(AppiumBy.IOS_PREDICATE, predicate)
    except (AttributeError, WebDriverException):
        elements = []
    candidates = []
    for element in elements:
        rect = _rect_snapshot(element)
        if rect is None:
            continue
        height = float(rect.get("height", 0) or 0)
        y = float(rect.get("y", 0) or 0)
        if height > 80:
            continue
        candidates.append((y, element))
    for _, element in sorted(candidates, key=lambda item: item[0], reverse=True):
        if _tap_element_center(driver, element):
            return True
    return False


def _tap_note_location_entry_by_coordinate(driver: WebDriver) -> bool:
    try:
        rect = driver.get_window_rect()
        tap_points = [
            (int(rect["width"] * 0.20), int(rect["height"] * 0.62)),
            (int(rect["width"] * 0.20), int(rect["height"] * 0.68)),
            (int(rect["width"] * 0.50), int(rect["height"] * 0.62)),
        ]
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False
    for x, y in tap_points:
        try:
            driver.execute_script("mobile: tap", {"x": x, "y": y})
        except WebDriverException:
            continue
        time.sleep(0.2)
        if _location_picker_visible(_safe_page_source(driver)):
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
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "ios":
        return _search_ios_note_location_from_picker(driver, normalized)

    search_input = _find_location_search_input(driver)
    if search_input is None:
        return False
    try:
        _replace_text(search_input, normalized)
    except WebDriverException:
        return False
    if str(capabilities.get("platformName", "")).lower() == "android":
        _wait_until(lambda: _android_location_search_ready(driver), timeout=10)
        return True
    else:
        _hide_keyboard(driver)
        _tap_text_or_contains(driver, "搜索")
    time.sleep(0.5)
    return True


def _search_ios_note_location_from_picker(driver: WebDriver, location: str) -> bool:
    search_input = _find_ios_location_search_input(driver)
    if search_input is None:
        return False
    try:
        search_input.click()
        try:
            search_input.clear()
        except WebDriverException:
            pass
        try:
            search_input.set_value(location)
        except (AttributeError, WebDriverException):
            search_input.send_keys(location)
    except WebDriverException:
        return False
    if not _wait_until(lambda: location in _safe_page_source(driver), timeout=2):
        return False
    _hide_keyboard(driver)
    _tap_text_or_contains(driver, "搜索")
    time.sleep(0.5)
    return True


def _find_ios_location_search_input(driver: WebDriver):
    xpaths = [
        (
            '//XCUIElementTypeTextField['
            '@value="搜索地点" or @name="搜索地点" or @label="搜索地点" or @placeholderValue="搜索地点"'
            ']'
        ),
        '//*[contains(@name, "搜索地点") or contains(@label, "搜索地点")]/descendant::XCUIElementTypeTextField[1]',
        '//XCUIElementTypeSearchField',
        '//XCUIElementTypeTextField',
    ]
    candidates = []
    for xpath in xpaths:
        try:
            elements = driver.find_elements(AppiumBy.XPATH, xpath)
        except (AttributeError, WebDriverException):
            continue
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                rect = element.rect
            except (AttributeError, WebDriverException):
                continue
            if _rect_snapshot(element) is None:
                continue
            candidates.append((float(rect.get("y", 0) or 0), float(rect.get("height", 0) or 0), element))
        if candidates:
            break
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


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


def _android_location_search_ready(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if "没有找到匹配地点" in page_source:
        return True
    return bool(_find_location_result_elements(driver))


def _choose_first_valid_location_from_picker(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    is_android = str(capabilities.get("platformName", "")).lower() == "android"
    if not is_android and _tap_first_ios_location_result_from_source(driver):
        return _wait_until(
            lambda: not _location_picker_visible(_safe_page_source(driver)),
            timeout=3,
        )

    result_elements = _find_location_result_elements(driver)
    for element in result_elements:
        if _tap_location_result(driver, element) and _wait_until(
            lambda: not _location_picker_visible(_safe_page_source(driver)),
            timeout=5,
        ):
            return True
        if not is_android:
            continue
        refreshed_elements = _find_location_result_elements(driver)
        for refreshed_element in refreshed_elements:
            if _tap_element_center(driver, refreshed_element) and _wait_until(
                lambda: not _location_picker_visible(_safe_page_source(driver)),
                timeout=5,
            ):
                return True
        for refreshed_element in refreshed_elements or [element]:
            if _tap_android_location_result_row(driver, refreshed_element) and _wait_until(
                lambda: not _location_picker_visible(_safe_page_source(driver)),
                timeout=5,
            ):
                return True
        return False
    return False


def _tap_first_ios_location_result_from_source(driver: WebDriver) -> bool:
    result_rect = _first_ios_location_result_rect_from_source(_safe_page_source(driver))
    if result_rect is None:
        return False
    left, top, right, bottom = result_rect
    try:
        driver.execute_script(
            "mobile: tap",
            {"x": (left + right) // 2, "y": (top + bottom) // 2},
        )
        return True
    except (AttributeError, WebDriverException):
        return False


def _first_ios_location_result_rect_from_source(page_source: str) -> tuple[int, int, int, int] | None:
    if "<XCUIElementType" not in page_source:
        return None
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None

    candidates: list[tuple[int, int, tuple[int, int, int, int]]] = []
    for element in root.iter():
        if element.tag not in {"XCUIElementTypeOther", "XCUIElementTypeStaticText"}:
            continue
        attrs = element.attrib
        if attrs.get("visible") == "false" or attrs.get("enabled") == "false":
            continue
        rect = _source_element_rect(attrs)
        if rect is None:
            continue
        left, top, right, bottom = rect
        name = _source_element_text(attrs)
        if not _looks_like_location_result(name, {"x": left, "y": top, "width": right - left, "height": bottom - top}):
            continue
        candidates.append((top, left, rect))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item[0], item[1]))[0][2]


def _tap_android_location_result_row(driver: WebDriver, element) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "android":
        return False
    text = _element_name(element).strip()
    if not text:
        return False
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    for xpath in [
        (
            f'(//android.widget.ScrollView//*[contains(@text, "{escaped}") '
            'and not(self::android.widget.EditText)]/ancestor::android.view.ViewGroup[1])[1]'
        ),
        (
            f'(//android.widget.ScrollView//*[contains(@text, "{escaped}") '
            'and not(self::android.widget.EditText)]/ancestor::android.view.ViewGroup[2])[1]'
        ),
    ]:
        try:
            row = driver.find_element(AppiumBy.XPATH, xpath)
        except (NoSuchElementException, WebDriverException, AttributeError):
            continue
        rect = _rect_snapshot(row)
        if rect is not None and _tap_rect_center(driver, rect):
            return True
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

    if str(capabilities.get("platformName", "")).lower() == "ios":
        element = _find_ios_input_from_page_source_geometry(driver, keyword, prefer_text_view=prefer_text_view)
        if element is not None:
            try:
                _replace_text(element, value)
                _hide_keyboard(driver)
                return True
            except WebDriverException:
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


def _find_ios_input_from_page_source_geometry(
    driver: WebDriver,
    keyword: str,
    *,
    prefer_text_view: bool = False,
):
    page_source = _safe_page_source(driver)
    target = _ios_input_target_from_page_source(page_source, keyword, prefer_text_view=prefer_text_view)
    if target is None:
        return None
    element_type, rect = target
    xpath = _ios_element_xpath_for_rect(element_type, rect)
    try:
        return driver.find_element(AppiumBy.XPATH, xpath)
    except (NoSuchElementException, WebDriverException, AttributeError):
        return None


def _ios_input_target_from_page_source(
    page_source: str,
    keyword: str,
    *,
    prefer_text_view: bool = False,
) -> tuple[str, dict[str, str]] | None:
    if "<XCUIElementType" not in page_source:
        return None
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None

    labels: list[tuple[int, int, int, int]] = []
    fields: list[tuple[str, tuple[int, int, int, int], dict[str, str]]] = []
    for element in root.iter():
        attrs = element.attrib
        if attrs.get("visible") == "false" or attrs.get("enabled") == "false":
            continue
        rect = _source_element_rect(attrs)
        if rect is None:
            continue
        tag_name = element.tag.rsplit("}", 1)[-1]
        text = _source_element_text(attrs)
        if keyword in text:
            labels.append(rect)
        if tag_name in {"XCUIElementTypeTextField", "XCUIElementTypeTextView"}:
            fields.append((tag_name, rect, attrs))

    candidates: list[tuple[int, int, str, dict[str, str]]] = []
    for label_rect in labels:
        for element_type, field_rect, attrs in fields:
            distance = _ios_input_label_distance(label_rect, field_rect)
            if distance is None:
                continue
            type_rank = 0 if (
                (prefer_text_view and element_type == "XCUIElementTypeTextView")
                or (not prefer_text_view and element_type == "XCUIElementTypeTextField")
            ) else 1
            rect_attrs = {key: attrs[key] for key in ("x", "y", "width", "height") if key in attrs}
            if len(rect_attrs) != 4:
                continue
            candidates.append((distance, type_rank, element_type, rect_attrs))
    if not candidates:
        return None
    _distance, _type_rank, element_type, rect_attrs = sorted(candidates, key=lambda item: (item[0], item[1]))[0]
    return element_type, rect_attrs


def _ios_input_label_distance(
    label_rect: tuple[int, int, int, int],
    field_rect: tuple[int, int, int, int],
) -> int | None:
    label_left, label_top, label_right, label_bottom = label_rect
    field_left, field_top, field_right, field_bottom = field_rect
    if field_bottom < label_top:
        return None
    vertical_gap = max(0, field_top - label_bottom)
    horizontal_gap = 0
    if field_right < label_left:
        horizontal_gap = label_left - field_right
    elif label_right < field_left:
        horizontal_gap = field_left - label_right
    if vertical_gap > 220 or horizontal_gap > 260:
        return None
    return vertical_gap * 1000 + horizontal_gap


def _ios_element_xpath_for_rect(element_type: str, rect: dict[str, str]) -> str:
    return (
        f'//{element_type}[@visible="true" and @x="{rect["x"]}" and @y="{rect["y"]}" '
        f'and @width="{rect["width"]}" and @height="{rect["height"]}"]'
    )


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
    try:
        element.set_value(value)
        return
    except (AttributeError, WebDriverException):
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
    if _keyboard_visible(_safe_page_source(driver)):
        _dismiss_keyboard_with_safe_tap(driver)
    time.sleep(0.2)


def _tap_editor_done(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "完成", timeout=0.5):
        return True
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
    if tap_first(
        driver,
        NOTE_SUBMIT_CANDIDATES,
        logical_name="note submit button",
        timeout=0.8,
        required=False,
    ):
        return True
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


def _extract_visible_message_texts(page_source: str) -> list[str]:
    if not page_source:
        return []
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        extracted = _extract_strings(page_source)
        return extracted or _combine_system_message_date_tokens(page_source.split())

    texts: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        raw_text = (
            element.attrib.get("text", "")
            or element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
        )
        normalized = " ".join(html.unescape(raw_text).split())
        if not normalized or normalized in seen:
            continue
        if len(normalized) > 160 and any(token in normalized for token in ["全国 推荐", "Vertical scroll bar"]):
            continue
        seen.add(normalized)
        texts.append(normalized)
    return texts


def _combine_system_message_date_tokens(texts: list[str]) -> list[str]:
    combined: list[str] = []
    index = 0
    while index < len(texts):
        if (
            index + 1 < len(texts)
            and re.fullmatch(r"\d{2}-\d{2}", texts[index])
            and re.fullmatch(r"\d{2}:\d{2}", texts[index + 1])
        ):
            combined.append(f"{texts[index]} {texts[index + 1]}")
            index += 2
            continue
        combined.append(texts[index])
        index += 1
    return combined


def _looks_like_system_message_value(text: str) -> bool:
    if not text or text in SYSTEM_MESSAGE_SKIP_TEXTS:
        return False
    if "条未读" in text or "Vertical scroll bar" in text or "Horizontal scroll bar" in text:
        return False
    return True


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


def _extract_android_comments(page_source: str) -> list[str]:
    if "<android." not in page_source:
        return []

    entries: list[tuple[str, int, int, int, int]] = []
    for tag in re.findall(r"<android\.widget\.TextView\b[^>]*>", page_source):
        text_match = re.search(r'\btext="([^"]+)"', tag)
        bounds_match = re.search(r'\bbounds="\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"', tag)
        if not text_match or not bounds_match:
            continue
        text = text_match.group(1).strip()
        if not text:
            continue
        left, top, right, bottom = (int(value) for value in bounds_match.groups())
        entries.append((text, left, top, right, bottom))

    if not entries:
        return []

    comment_header_bottom = 0
    for text, _left, _top, _right, bottom in entries:
        if "评论" in text and ("共" in text or text.startswith("评论")):
            comment_header_bottom = max(comment_header_bottom, bottom)

    bottom_action_entries = _android_bottom_action_entries(page_source)
    bottom_bar_top = min((entry[2] for entry in bottom_action_entries), default=None)
    if comment_header_bottom <= 0:
        return _extract_android_structured_comment_bodies(entries, bottom_bar_top)

    comments: list[str] = []
    excluded = {"回复", "删除", "写留言", "评论", "点赞", "收藏", "分享", "赞", "消息", "我的", "活动", "笔记"}
    for text, left, top, _right, _bottom in entries:
        if top <= comment_header_bottom:
            continue
        if bottom_bar_top is not None and top >= bottom_bar_top - 120:
            continue
        if left < 120:
            continue
        if (
            text in excluded
            or text in GENERIC_DETAIL_TEXTS
            or text.isdigit()
            or re.fullmatch(r"\d+\s*分钟前", text)
        ):
            continue
        if _contains_detail_meta(text) or "评论" in text:
            continue
        below_texts = [
            entry[0]
            for entry in entries
            if abs(entry[1] - left) <= 30 and 0 < entry[2] - top <= 120
        ]
        if (
            below_texts
            and not ANDROID_COMMENT_TIME_PATTERN.fullmatch(below_texts[0])
            and not any(marker in text for marker in ("：", ":", "不错", "好", "赞"))
        ):
            continue
        comments.append(text)
    return _dedupe_preserve_order(comments)


def _extract_android_structured_comment_bodies(
    entries: list[tuple[str, int, int, int, int]],
    bottom_bar_top: int | None,
) -> list[str]:
    comments: list[str] = []
    excluded = {"回复", "删除", "写留言", "评论", "点赞", "收藏", "分享", "赞", "消息", "我的", "活动", "笔记"}
    for text, left, top, _right, _bottom in entries:
        if not ANDROID_COMMENT_TIME_PATTERN.fullmatch(text):
            continue
        if bottom_bar_top is not None and top >= bottom_bar_top - 120:
            continue
        row_actions = [
            entry[0]
            for entry in entries
            if entry[1] > left + 300 and abs(entry[2] - top) <= 35 and entry[0] in {"回复", "删除"}
        ]
        if not row_actions:
            continue
        same_column_above = [
            entry
            for entry in entries
            if abs(entry[1] - left) <= 30 and 0 < top - entry[2] <= 180
        ]
        for candidate, _candidate_left, _candidate_top, _candidate_right, _candidate_bottom in reversed(same_column_above):
            if (
                candidate in excluded
                or candidate in GENERIC_DETAIL_TEXTS
                or candidate.isdigit()
                or ANDROID_COMMENT_TIME_PATTERN.fullmatch(candidate)
                or _contains_detail_meta(candidate)
            ):
                continue
            comments.append(candidate)
            break
    return _dedupe_preserve_order(comments)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


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
    return _android_detail_interaction_metadata_visible(snapshot) or bool(snapshot.view_count and snapshot.comment_count)


def _android_image_note_detail_ready(page_source: str, snapshot: MessageDetailSnapshot) -> bool:
    return bool(
        "<android." in page_source
        and _detail_shell_is_visible(page_source)
        and snapshot.title
        and not snapshot.body
        and _android_detail_interaction_metadata_visible(snapshot)
    )


def _android_detail_interaction_metadata_visible(snapshot: MessageDetailSnapshot) -> bool:
    return bool(snapshot.comment_count or len(snapshot.bottom_action_counts) >= 3)


def _android_detail_needs_comment_probe(snapshot: MessageDetailSnapshot) -> bool:
    return bool(
        snapshot.comment_count
        and snapshot.comment_count != "0"
        and not snapshot.comments
        and not snapshot.empty_comment_hint
    )


def _merge_detail_snapshots(
    first: MessageDetailSnapshot,
    latest: MessageDetailSnapshot,
) -> MessageDetailSnapshot:
    return MessageDetailSnapshot(
        title=latest.title or first.title,
        body=latest.body or first.body,
        view_count=latest.view_count or first.view_count,
        comment_count=latest.comment_count or first.comment_count,
        comments=_dedupe_preserve_order([*first.comments, *latest.comments]),
        empty_comment_hint=latest.empty_comment_hint or first.empty_comment_hint,
        bottom_action_counts=latest.bottom_action_counts or first.bottom_action_counts,
    )


def _detail_shell_is_visible(page_source: str) -> bool:
    return any(token in page_source for token in DETAIL_READY_IDS)


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


def _tap_messages_tab(driver: WebDriver) -> bool:
    return tap_accessibility_id_or_text_if_present(driver, "bottom-nav-messages", "消息", timeout=5)


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


def _tap_ios_visible_text_from_source(driver: WebDriver, texts: list[str]) -> bool:
    page_source = _safe_page_source(driver)
    if "<XCUIElementType" not in page_source:
        return False
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return False

    text_set = set(texts)
    candidates: list[tuple[int, int, int]] = []
    for element in root.iter():
        attrs = element.attrib
        if attrs.get("visible") == "false" or attrs.get("enabled") == "false":
            continue
        if _source_element_text(attrs) not in text_set:
            continue
        rect = _source_element_rect(attrs)
        if rect is None:
            continue
        left, top, right, bottom = rect
        candidates.append(((right - left) * (bottom - top), (left + right) // 2, (top + bottom) // 2))
    if not candidates:
        return False

    _, x, y = min(candidates)
    try:
        driver.execute_script("mobile: tap", {"x": x, "y": y})
        return True
    except (AttributeError, WebDriverException):
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

    after_counts = _wait_for_bottom_action_count_change(driver, action_index, before_counts, timeout)
    if after_counts is not None:
        return before_counts, after_counts

    if _tap_bottom_action_element_center_at_index(driver, action_index):
        after_counts = _wait_for_bottom_action_count_change(driver, action_index, before_counts, timeout)
        if after_counts is not None:
            return before_counts, after_counts

    raise AssertionError(
        f"Bottom action at index {action_index} did not change. before={before_counts}"
    )


def _wait_for_bottom_action_count_change(
    driver: WebDriver,
    action_index: int,
    before_counts: list[str],
    timeout: int,
) -> list[str] | None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        after_counts = parse_detail_snapshot(_safe_page_source(driver)).bottom_action_counts
        if len(after_counts) > action_index and after_counts[action_index] != before_counts[action_index]:
            return after_counts
        time.sleep(0.2)
    return None


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


def _tap_bottom_action_element_center_at_index(driver: WebDriver, action_index: int) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "android":
        return _tap_android_bottom_action_by_source(driver, action_index, tap_count=True)
    candidates = _find_bottom_action_elements(driver)
    if len(candidates) <= action_index:
        return False
    return _tap_element_center(driver, candidates[action_index])


def _close_ios_image_preview_if_visible(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() != "ios":
        return False

    page_source = _safe_page_source(driver)
    if not _ios_image_preview_visible(page_source):
        return False

    rect = _ios_preview_close_rect(page_source)
    if rect is None:
        try:
            window = driver.get_window_rect()
            x = int(float(window["width"]) * 0.92)
            y = int(float(window["height"]) * 0.10)
        except (AttributeError, KeyError, TypeError, WebDriverException):
            return False
    else:
        left, top, right, bottom = rect
        x = (left + right) // 2
        y = (top + bottom) // 2

    try:
        driver.execute_script("mobile: tap", {"x": x, "y": y})
    except (AttributeError, WebDriverException):
        return False

    _wait_until(lambda: not _ios_image_preview_visible(_safe_page_source(driver)), timeout=2)
    return True


def _ios_image_preview_visible(page_source: str) -> bool:
    if "post-detail-preview-pager" not in page_source:
        return False
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return False
    return any(
        element.attrib.get("name") == "post-detail-preview-pager"
        and element.attrib.get("visible") != "false"
        for element in root.iter()
    )


def _ios_preview_close_rect(page_source: str) -> tuple[int, int, int, int] | None:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None

    window_width = 0
    candidates: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        attributes = element.attrib
        if attributes.get("visible") == "false" or attributes.get("enabled") == "false":
            continue
        rect = _source_element_rect(attributes)
        if rect is None:
            continue
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        window_width = max(window_width, right)
        if top <= 130 and 25 <= width <= 55 and 25 <= height <= 55:
            candidates.append(rect)

    if not candidates:
        return None
    right_edge_threshold = int(window_width * 0.75) if window_width else 300
    right_candidates = [rect for rect in candidates if rect[0] >= right_edge_threshold]
    if not right_candidates:
        return None
    return max(right_candidates, key=lambda rect: (rect[0], -rect[1]))


def _tap_android_bottom_action_by_source(
    driver: WebDriver,
    action_index: int,
    *,
    tap_count: bool = False,
) -> bool:
    page_source = _safe_page_source(driver)
    entries = _android_bottom_action_entries(page_source)
    if len(entries) <= action_index:
        return False
    _, left, top, right, bottom = entries[action_index]
    height = max(1, bottom - top)
    # React Native exposes the numeric label but not the Pressable as clickable
    # on Android. The SVG action icon sits immediately to the label's left and
    # is the reliable hit target. Keep the label center as the retry target.
    x = (left + right) // 2 if tap_count else left - height // 2
    try:
        driver.execute_script(
            "mobile: tap",
            {"x": x, "y": (top + bottom) // 2},
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
    platform = str(capabilities.get("platformName", "")).lower()
    if platform == "android":
        if _tap_android_detail_share_button_from_source(driver):
            return True
        try:
            rect = driver.get_window_rect()
            driver.execute_script(
                "mobile: tap",
                {"x": int(rect["width"] * 0.95), "y": int(rect["height"] * 0.09)},
            )
            return True
        except (AttributeError, KeyError, TypeError, WebDriverException):
            return False
    if platform == "ios" and _tap_ios_detail_share_button_from_source(driver):
        return True
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
        if y > 260:
            continue
        if x > best_x:
            best_x = x
            share_candidate = element
    if share_candidate is not None and _tap_element_center(driver, share_candidate):
        return True
    return False


def _tap_ios_detail_share_button_from_source(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if "<XCUIElementType" not in page_source:
        return False
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return False

    candidates: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        if element.tag != "XCUIElementTypeOther":
            continue
        attrs = element.attrib
        if attrs.get("visible") == "false" or attrs.get("enabled") == "false":
            continue
        rect = _source_element_rect(attrs)
        if rect is None:
            continue
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if not (35 <= width <= 50 and 35 <= height <= 50):
            continue
        if top > 260:
            continue
        candidates.append(rect)
    if not candidates:
        return False

    left, top, right, bottom = max(candidates, key=lambda rect: rect[0])
    try:
        driver.execute_script(
            "mobile: tap",
            {"x": (left + right) // 2, "y": (top + bottom) // 2},
        )
        return True
    except (AttributeError, WebDriverException):
        return False


def _tap_android_detail_share_button_from_source(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if "<android." not in page_source:
        return False
    try:
        rect = driver.get_window_rect()
        screen_width = int(rect.get("width") or 0)
    except (AttributeError, TypeError, ValueError, WebDriverException):
        screen_width = 0

    candidates: list[tuple[int, int, int, int]] = []
    for tag in re.findall(r"<android\.view\.ViewGroup\b[^>]*>", page_source):
        bounds_match = re.search(r'\bbounds="\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"', tag)
        if not bounds_match:
            continue
        left, top, right, bottom = (int(value) for value in bounds_match.groups())
        width = right - left
        height = bottom - top
        if not (60 <= width <= 180 and 45 <= height <= 140):
            continue
        if not (90 <= top <= 380):
            continue
        if screen_width and left < screen_width * 0.65:
            continue
        candidates.append((left, top, right, bottom))

    if not candidates:
        return False
    left, top, right, bottom = max(candidates, key=lambda bounds: (bounds[2], bounds[0]))
    try:
        driver.execute_script("mobile: tap", {"x": int((left + right) / 2), "y": int((top + bottom) / 2)})
        return True
    except WebDriverException:
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


def _confirm_share_after_target(driver: WebDriver, timeout: int = 20) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "ios":
        if _tap_share_confirm_by_coordinate(driver):
            if _wait_until(lambda: _share_returned_to_detail(driver), timeout=timeout):
                return True
    if _wait_until(lambda: _share_returned_to_detail(driver), timeout=3):
        return True

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        for text in ["发送", "发表", "分享", "确定"]:
            if tap_text_if_present(driver, text, timeout=1):
                return _wait_until(lambda: _share_returned_to_detail(driver), timeout=timeout)
        if _tap_share_confirm_by_coordinate(driver):
            return _wait_until(lambda: _share_returned_to_detail(driver), timeout=timeout)
        if _share_returned_to_detail(driver):
            return True
        time.sleep(0.3)
    return False


def _share_returned_to_detail(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    return not _share_sheet_visible(page_source) and message_detail_is_visible(driver)


def _tap_share_confirm_by_coordinate(driver: WebDriver) -> bool:
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() not in {"android", "ios"}:
        return False
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {"x": int(rect["width"] * 0.88), "y": int(rect["height"] * 0.08)},
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _tap_android_share_confirm_by_coordinate(driver: WebDriver) -> bool:
    return _tap_share_confirm_by_coordinate(driver)


def _return_to_home_after_share(driver: WebDriver, timeout: int = 20) -> bool:
    if not message_detail_is_visible(driver):
        return True
    capabilities = getattr(driver, "capabilities", {}) or {}
    if str(capabilities.get("platformName", "")).lower() == "ios" and _tap_ios_detail_back_button_from_source(driver):
        return _wait_until(lambda: not message_detail_is_visible(driver), timeout=timeout)
    try:
        driver.back()
    except WebDriverException:
        if not _tap_android_top_back(driver):
            return False
    return _wait_until(lambda: not message_detail_is_visible(driver), timeout=timeout)


def _tap_ios_detail_back_button_from_source(driver: WebDriver) -> bool:
    page_source = _safe_page_source(driver)
    if "<XCUIElementType" not in page_source:
        return False
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return False

    candidates: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        if element.tag != "XCUIElementTypeOther":
            continue
        attrs = element.attrib
        if attrs.get("visible") == "false" or attrs.get("enabled") == "false":
            continue
        rect = _source_element_rect(attrs)
        if rect is None:
            continue
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if not (35 <= width <= 50 and 35 <= height <= 50):
            continue
        if top > 260:
            continue
        candidates.append(rect)
    if not candidates:
        return False

    left, top, right, bottom = min(candidates, key=lambda rect: rect[0])
    try:
        driver.execute_script(
            "mobile: tap",
            {"x": (left + right) // 2, "y": (top + bottom) // 2},
        )
        return True
    except (AttributeError, WebDriverException):
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
