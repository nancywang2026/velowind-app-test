import pytest

from velowind_appium.modules import (
    browse_note_detail,
    # favorite_note,
    # like_note,
    open_first_note_search_result,
    open_note_search,
    search_notes,
    # submit_message_comment,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


# SEARCH_KEYWORD = "徒步"
SEARCH_KEYWORD = "骑行"
# SEARCH_COMMENT_TEXT = "自动化添加评论"


@pytest.mark.full
def test_user_can_search_and_open_note(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("open-note-search", lambda: open_note_search(driver, timeout=12))
    step("search-notes", lambda: search_notes(driver, SEARCH_KEYWORD, timeout=12))
    step("open-first-search-result", lambda: open_first_note_search_result(driver, timeout=12))
    snapshot = step("browse-note-detail", lambda: browse_note_detail(driver, timeout=20))

    assert snapshot.title, "Expected the searched note detail to expose a title"
    assert snapshot.body, "Expected the searched note detail to expose content"

    # like_counts = step("like-note", lambda: like_note(driver, timeout=15))
    # favorite_counts = step("favorite-note", lambda: favorite_note(driver, timeout=15))
    # step("add-note-comment", lambda: submit_message_comment(driver, SEARCH_COMMENT_TEXT, timeout=20))
    # assert like_counts[0] != like_counts[1], "Expected the like state/count to change after tapping like"
    # assert favorite_counts[0] != favorite_counts[1], "Expected the favorite state/count to change after tapping favorite"
