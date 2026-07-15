from datetime import datetime

import pytest

from velowind_appium.modules import (
    browse_note_detail,
    browse_note_feed,
    favorite_note,
    like_note,
    message_detail_is_visible,
    submit_message_comment,
    tap_note_card_at_ordinal,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


def _open_home_note(driver, ios_config, step, *, ordinal: int):
    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("browse-note-feed", lambda: browse_note_feed(driver, timeout=20))

    def _open_selected_card():
        opened = tap_note_card_at_ordinal(
            driver,
            ordinal=ordinal,
            page_source=driver.page_source,
            verify_open=lambda: message_detail_is_visible(driver),
            timeout=3,
        )
        if not opened:
            raise AssertionError(f"Unable to open home note card at ordinal {ordinal}")

    step(f"open-home-note-{ordinal}", _open_selected_card)
    return step("browse-note-detail", lambda: browse_note_detail(driver, timeout=20))


@pytest.mark.full
def test_user_can_comment_on_first_home_note(driver, ios_config, step):
    snapshot = _open_home_note(driver, ios_config, step, ordinal=1)
    assert snapshot.title, "Expected the first home note detail to expose a title"

    comment_text = f"自动化评论{datetime.now():%m%d%H%M%S}"
    step("add-note-comment", lambda: submit_message_comment(driver, comment_text, timeout=20))


@pytest.mark.full
def test_user_can_like_and_favorite_second_home_note(driver, ios_config, step):
    snapshot = _open_home_note(driver, ios_config, step, ordinal=2)
    assert snapshot.title, "Expected the second home note detail to expose a title"

    like_counts = step("like-note", lambda: like_note(driver, timeout=15))
    favorite_counts = step("favorite-note", lambda: favorite_note(driver, timeout=15))

    assert like_counts[0] != like_counts[1], "Expected the like state/count to change after tapping like"
    assert favorite_counts[0] != favorite_counts[1], "Expected the favorite state/count to change after tapping favorite"
