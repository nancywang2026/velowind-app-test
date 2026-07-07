from __future__ import annotations

from dataclasses import dataclass
import html
import re
import time

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from velowind_appium.actions import swipe_vertical, tap_if_present, tap_text_if_present


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


@dataclass
class MessageDetailSnapshot:
    title: str | None
    body: str | None
    view_count: str | None
    comment_count: str | None
    comments: list[str]
    empty_comment_hint: str | None
    bottom_action_counts: list[str]


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
    except WebDriverException:
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
    for xpath in [
        '(//XCUIElementTypeOther[@name="0"])[1]',
        '(//XCUIElementTypeOther[@name="1"])[1]',
        '(//XCUIElementTypeOther[@name="0"])[2]',
    ]:
        try:
            driver.find_element(AppiumBy.XPATH, xpath).click()
            return True
        except (NoSuchElementException, TimeoutException, WebDriverException):
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
