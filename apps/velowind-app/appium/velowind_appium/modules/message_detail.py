from __future__ import annotations

from dataclasses import dataclass
import html
from pathlib import Path
import re
import time

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
]
NOTE_FORM_READY_TEXTS = ["发布笔记", "标题", "正文", "话题", "标记地点", "允许评论"]
NOTE_SUCCESS_TEXTS = ["发布成功", "提交成功", "审核中", "待审核", "提交审核成功", "已发布"]
NOTE_SUCCESS_IDS = [
    "note-publish-success",
    "message-publish-success",
    "publish-success-page",
]
NOTE_ERROR_TEXTS = ["服务开小差了，请稍后重试", "服务器内部错误", "发布失败", "提交失败"]
TITLE_FIELD_KEYWORDS = ["标题", "请输入标题"]
BODY_FIELD_KEYWORDS = ["正文", "内容", "分享", "描述"]
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
ATTRIBUTE_PATTERN = re.compile(r'(?:name|label|value)="([^"]+)"')
VIEW_COUNT_PATTERN = re.compile(r"浏览(?:量)?\D*(\d+)")
COMMENT_COUNT_PATTERN = re.compile(r"评论(?:数)?\D*(\d+)")
COUNT_ONLY_PATTERN = re.compile(r"^(?:浏览|评论)\s*(\d+)$")
BOTTOM_ACTION_PATTERN = re.compile(r"用户\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)")
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
    allow_comments = note.get("allow_comments", True)
    if isinstance(allow_comments, str):
        allow_comments = allow_comments.strip().lower() in {"1", "true", "yes", "y", "on", "是"}
    return MessageNoteDraft(
        title=title,
        body=body,
        topics=[str(topic).strip() for topic in topics if str(topic).strip()],
        location=location,
        album=album,
        allow_comments=bool(allow_comments),
    )


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
    open_message_note_publisher(driver, ios_config=ios_config, timeout=timeout)
    fill_message_note_form(driver, draft, timeout=timeout)
    return submit_message_note(driver, timeout=timeout)


def open_message_note_publisher(
    driver: WebDriver,
    *,
    ios_config: IosAppiumConfig | None = None,
    timeout: int = 30,
) -> None:
    end_at = time.monotonic() + timeout

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


def fill_message_note_form(driver: WebDriver, draft: MessageNoteDraft, timeout: int = 60) -> None:
    wait_for_message_note_form(driver, timeout=timeout)

    _upload_note_image(driver, draft)
    _fill_note_title(driver, draft.title)
    _fill_note_body(driver, draft.body)
    _append_note_topics_to_body(driver, draft.topics)
    if draft.location:
        _fill_note_location(driver, draft.location)
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
    bottom_action_counts = _extract_bottom_action_counts(texts)
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
        if snapshot.title and snapshot.body and snapshot.view_count and snapshot.comment_count:
            return snapshot
        time.sleep(0.2)

    raise AssertionError(f"Message detail did not expose all expected fields: {last_snapshot}")


def submit_message_comment(driver: WebDriver, comment_text: str, timeout: int = 20) -> None:
    before_snapshot = parse_detail_snapshot(_safe_page_source(driver))
    if not _tap_candidate(driver, COMMENT_ENTRY_IDS, COMMENT_ENTRY_TEXTS):
        raise AssertionError("Unable to open the comment entry point from message detail")

    input_box = _find_comment_input(driver, timeout=timeout)
    try:
        input_box.clear()
    except WebDriverException:
        pass
    input_box.send_keys(comment_text)

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
    return bool(snapshot.title and snapshot.body and snapshot.view_count and snapshot.comment_count)


def browse_note_detail(driver: WebDriver, timeout: int = 20) -> MessageDetailSnapshot:
    return read_message_detail_snapshot(driver, timeout=timeout)


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
    escaped_texts = [text.replace("\\", "\\\\").replace('"', '\\"') for text in texts]
    quoted = ", ".join(f'"{text}"' for text in escaped_texts)
    predicate = f"name IN {{{quoted}}} OR label IN {{{quoted}}} OR value IN {{{quoted}}}"
    try:
        driver.find_element(AppiumBy.IOS_PREDICATE, predicate).click()
        return True
    except (NoSuchElementException, WebDriverException):
        return False


def _fill_note_title(driver: WebDriver, title: str) -> None:
    for keyword in TITLE_FIELD_KEYWORDS:
        if _fill_input_near_label(driver, keyword, title):
            return
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
    _clear_existing_note_images(driver)
    if not _tap_note_image_plus(driver):
        raise AssertionError("Unable to find the note image plus button")

    if photo_picker.choose_photo_from_library(
        driver,
        album_name=draft.album,
        retry_sheet_option=_tap_note_photo_library_sheet_option,
    ):
        return

    raise AssertionError(
        "Photo library opened but no selectable photo was found. "
        "If this is a simulator, seed at least one image into Photos."
    )


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
    if not message_note_form_is_visible(_safe_page_source(driver)):
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


def _find_note_image_remove_buttons(driver: WebDriver) -> list:
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

    topic_text = " " + " ".join(topics)
    for xpath in [
        "//XCUIElementTypeTextView[1]",
        '(//XCUIElementTypeTextField)[2]',
        '//XCUIElementTypeTextView[contains(@value, "长白山") or contains(@value, "正文") or contains(@value, "分享")]',
    ]:
        try:
            element = driver.find_element(AppiumBy.XPATH, xpath)
            element.click()
            element.send_keys(topic_text)
            _dismiss_editor_keyboard(driver)
            return
        except (NoSuchElementException, WebDriverException):
            continue
    raise AssertionError("Unable to append topics to the note body")


def _tap_note_image_plus(driver: WebDriver) -> bool:
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
    if _location_section_visible(_safe_page_source(driver)):
        return
    for _ in range(3):
        _dismiss_editor_keyboard(driver)
        if _location_section_visible(_safe_page_source(driver)):
            return
        try:
            swipe_vertical(driver, direction="up")
        except WebDriverException:
            pass
        time.sleep(0.3)
        if _location_section_visible(_safe_page_source(driver)):
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
    _hide_keyboard(driver)
    _tap_text_or_contains(driver, "搜索")
    time.sleep(0.5)
    return True


def _find_location_search_input(driver: WebDriver):
    for xpath in [
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
    for element in result_elements:
        if _tap_element_center(driver, element) and _wait_until(
            lambda: not _location_picker_visible(_safe_page_source(driver)),
            timeout=5,
        ):
            return True
    return False


def _find_location_result_elements(driver: WebDriver) -> list:
    elements = []
    seen: set[tuple[str, float, float, float, float]] = set()
    for xpath in [
        '//XCUIElementTypeOther[@visible="true"]',
        '//XCUIElementTypeStaticText[@visible="true"]',
    ]:
        try:
            candidates = driver.find_elements(AppiumBy.XPATH, xpath)
        except (AttributeError, WebDriverException):
            continue
        for element in candidates:
            name = _element_name(element)
            rect = getattr(element, "rect", {}) or {}
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
            elements.append(element)
    elements.sort(key=lambda element: ((getattr(element, "rect", {}) or {}).get("y", 0), (getattr(element, "rect", {}) or {}).get("x", 0)))
    return elements


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
    if width < 250 or height < 40:
        return False
    if x > 40 or y < 450:
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
    for attribute in ["name", "label", "value"]:
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
    _hide_keyboard(driver)
    _tap_outside_editor(driver)
    time.sleep(0.2)


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
    match = pattern.search(page_source)
    if match:
        return match.group(1)

    for text in texts:
        if keyword not in text:
            continue
        count_match = COUNT_ONLY_PATTERN.match(text)
        if count_match:
            return count_match.group(1)
        digits = re.search(r"(\d+)", text)
        if digits:
            return digits.group(1)
    return None


def _extract_comments(texts: list[str]) -> list[str]:
    comments: list[str] = []
    for text in texts:
        if text in GENERIC_DETAIL_TEXTS or "图票" in text or _contains_detail_meta(text):
            continue
        if any(marker in text for marker in ("：", ":", "回复", "不错", "好", "赞")) and len(text) >= 4:
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
    return []


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
    candidates = _find_bottom_action_elements(driver)
    if len(candidates) <= action_index:
        return False
    return _tap_element_center(driver, candidates[action_index])


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
