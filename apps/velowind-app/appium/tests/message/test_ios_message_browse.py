import pytest

from velowind_appium.modules import (
    open_first_home_message,
    read_message_detail_snapshot,
    submit_message_comment,
    toggle_ticket_text_and_assert_change,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


TEST_COMMENT_TEXT = "自动化测试留言"


@pytest.mark.full
def test_normal_user_can_browse_and_comment_message(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("swipe-home-feed", lambda: open_first_home_message(driver))
    snapshot = step("read-message-detail", lambda: read_message_detail_snapshot(driver, timeout=20))

    assert snapshot.title, "Expected the message detail to expose a title"
    assert snapshot.body, "Expected the message detail to expose content"
    assert snapshot.view_count, "Expected the message detail to expose a view count"
    assert snapshot.comment_count, "Expected the message detail to expose a comment count"
    assert snapshot.comments or snapshot.empty_comment_hint, "Expected comments or an empty-comment hint in the detail page"

    step("write-comment", lambda: submit_message_comment(driver, TEST_COMMENT_TEXT, timeout=20))
    ticket_texts = step("toggle-ticket-text", lambda: toggle_ticket_text_and_assert_change(driver, timeout=15))

    assert ticket_texts[0] != ticket_texts[1], "Expected the bottom action count next to the icon to change after tapping"
