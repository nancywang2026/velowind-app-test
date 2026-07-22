import pytest

from velowind_appium.modules import (
    browse_note_detail,
    favorite_note,
    like_note,
    open_first_home_message,
    share_note_to_moments,
    submit_message_comment,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


TEST_COMMENT_TEXT = "不错"


@pytest.mark.full
def test_logged_in_user_can_browse_comment_and_interact_with_note(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-first-note", lambda: open_first_home_message(driver))
    snapshot = step("browse-note-detail", lambda: browse_note_detail(driver, timeout=20))

    assert snapshot.title, "Expected the message detail to expose a title"
    assert snapshot.body, "Expected the message detail to expose content"
    assert snapshot.view_count, "Expected the message detail to expose a view count"
    assert snapshot.comment_count, "Expected the message detail to expose a comment count"
    assert snapshot.comments or snapshot.empty_comment_hint, "Expected comments or an empty-comment hint in the detail page"

    step("add-note-comment", lambda: submit_message_comment(driver, TEST_COMMENT_TEXT, timeout=20))
    like_counts = step("like-note", lambda: like_note(driver, timeout=15))
    favorite_counts = step("favorite-note", lambda: favorite_note(driver, timeout=15))
    share_target = step("share-note-to-moments", lambda: share_note_to_moments(driver, timeout=20))

    assert like_counts[0] != like_counts[1], "Expected the like count to change after tapping the like action"
    assert favorite_counts[0] != favorite_counts[1], "Expected the favorite count to change after tapping the favorite action"
    assert share_target == "朋友圈", "Expected the note to use the Moments share target"
